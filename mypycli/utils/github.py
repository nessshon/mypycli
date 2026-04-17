from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlparse

from git import Git, GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import BadName
from packaging.version import InvalidVersion, Version

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path


class GitError(Exception):
    """Raised when a git operation fails (invalid repo, network, missing ref, etc.)."""


@dataclass(frozen=True)
class RepoInfo:
    """Immutable snapshot of a repository's HEAD state and refs.

    :param commit: Full HEAD commit SHA.
    :param commit_short: Seven-character abbreviated HEAD SHA.
    :param branch: Active branch name, or ``None`` if HEAD is detached.
    :param tag: Tag pointing at HEAD, or ``None`` if HEAD is untagged.
    :param tags: All tag names in the repository.
    :param branches: All local branch names.
    """

    commit: str
    commit_short: str
    branch: str | None
    tag: str | None
    tags: list[str] = field(default_factory=list)
    branches: list[str] = field(default_factory=list)

    @property
    def version(self) -> str:
        """Human-readable version string: the tag if any, else ``branch@short_sha``, else short SHA."""
        if self.tag:
            return self.tag
        if self.branch:
            return f"{self.branch}@{self.commit_short}"
        return self.commit_short

    @property
    def latest_version(self) -> str | None:
        """Highest stable tag by PEP 440 ordering, or ``None`` if no stable tag exists."""
        parsed = [(t, _parse_version(t)) for t in self.tags]
        stable = [(t, v) for t, v in parsed if v is not None and not v.is_prerelease]
        if not stable:
            return None
        return max(stable, key=lambda x: x[1])[0]

    @property
    def latest_prerelease(self) -> str | None:
        """Highest pre-release tag by PEP 440 ordering, or ``None`` if none exist."""
        parsed = [(t, _parse_version(t)) for t in self.tags]
        pre = [(t, v) for t, v in parsed if v is not None and v.is_prerelease]
        if not pre:
            return None
        return max(pre, key=lambda x: x[1])[0]


class BaseGitRepo(ABC):
    """Abstract interface shared by local and remote git repository wrappers."""

    @property
    @abstractmethod
    def url(self) -> str:
        """Canonical HTTPS URL of the repository."""

    @property
    @abstractmethod
    def author(self) -> str:
        """Repository owner (user or organization)."""

    @property
    @abstractmethod
    def repo_name(self) -> str:
        """Repository name without the ``.git`` suffix."""

    @property
    @abstractmethod
    def info(self) -> RepoInfo:
        """Fresh RepoInfo snapshot of the current repository state."""


class RemoteGitRepo(BaseGitRepo):
    """GitHub repository accessed over the network without a local clone.

    :param author: Repository owner (user or organization).
    :param repo: Repository name without the ``.git`` suffix.
    :param branch: Default branch or tag used by subsequent operations like ``clone``; ``None`` means upstream default.
    """

    def __init__(self, author: str, repo: str, *, branch: str | None = None) -> None:
        self._author = author
        self._repo_name = repo
        self._branch = branch

    @classmethod
    def from_url(cls, url: str, *, branch: str | None = None) -> RemoteGitRepo:
        """Construct a RemoteGitRepo from an HTTPS/SSH URL or ``user/repo`` shorthand.

        :param url: Git URL (``https://``, ``git@host:owner/repo``) or ``owner/repo`` shorthand (assumed GitHub).
        :param branch: Default branch or tag to associate with the remote.
        :raises GitError: If the URL cannot be parsed into owner and repo.
        """
        try:
            author, repo, _ = _parse_git_url(url)
        except ValueError as e:
            raise GitError(f"Invalid git URL: {url} ({e})") from e
        return cls(author, repo, branch=branch)

    @property
    def author(self) -> str:
        return self._author

    @property
    def repo_name(self) -> str:
        return self._repo_name

    @property
    def url(self) -> str:
        return f"https://github.com/{self._author}/{self._repo_name}"

    @property
    def branch(self) -> str | None:
        """Branch or tag passed at construction, used as the default ref for operations."""
        return self._branch

    @property
    def info(self) -> RepoInfo:
        """Fetch a RepoInfo snapshot via ``git ls-remote`` (requires network access).

        :raises GitError: If the remote is unreachable, not found, or ls-remote fails.
        """
        try:
            output: str = Git().ls_remote(self.url)
        except GitCommandError as e:
            stderr = str(e).lower()
            if "not found" in stderr or "does not exist" in stderr:
                raise GitError(f"Repository not found: {self.url} ({e})") from e
            if "could not resolve" in stderr:
                raise GitError(f"Network error: {self.url} ({e})") from e
            raise GitError(f"Failed to read remote: {self.url} ({e})") from e

        return _parse_ls_remote(output)

    def clone(
        self,
        path: str | Path,
        *,
        ref: str | None = None,
        depth: int | None = None,
    ) -> LocalGitRepo:
        """Clone the remote into ``path`` and return a LocalGitRepo for the new working copy.

        :param path: Destination directory; must not already exist.
        :param ref: Branch or tag to check out; when ``None`` falls back to the instance's ``branch``.
        :param depth: Shallow clone depth; ``None`` performs a full clone.
        :raises GitError: If the destination exists, the ref is not found, or the clone fails.
        """
        str_path = str(path)
        target_ref = ref if ref is not None else self._branch

        options: list[str] = []
        if target_ref is not None:
            options.append(f"--branch={target_ref}")
        if depth is not None:
            options.append(f"--depth={depth}")

        try:
            Repo.clone_from(self.url, str_path, multi_options=options or None)
        except GitCommandError as e:
            stderr = str(e).lower()
            if "already exists" in stderr:
                raise GitError(f"Path already exists: {str_path} ({e})") from e
            if "not found" in stderr or "did not match" in stderr:
                raise GitError(f"Ref not found: {target_ref} ({e})") from e
            raise GitError(f"Clone failed: {self.url} ({e})") from e

        return LocalGitRepo(path)


class LocalGitRepo(BaseGitRepo):
    """Wrapper around an on-disk git working tree with an ``origin`` remote.

    :param path: Path to an existing git working tree.
    :raises GitError: If the path does not exist, is not a git repository, or lacks an ``origin`` remote.
    """

    def __init__(self, path: str | Path) -> None:
        try:
            self._repo = Repo(str(path))
        except NoSuchPathError as e:
            raise GitError(f"Path not found: {path} ({e})") from e
        except InvalidGitRepositoryError as e:
            raise GitError(f"Not a git repository: {path} ({e})") from e

        self._path = str(self._repo.working_dir)
        try:
            self._repo.remote("origin")
        except ValueError as e:
            raise GitError(f"No origin remote in: {self._path}") from e

    @cached_property
    def author(self) -> str:
        return _parse_git_url(self.url)[0]

    @cached_property
    def repo_name(self) -> str:
        return _parse_git_url(self.url)[1]

    @property
    def url(self) -> str:
        return str(self._repo.remote("origin").url)

    @cached_property
    def remote(self) -> RemoteGitRepo:
        """RemoteGitRepo companion derived from the origin URL; cached until origin changes."""
        return RemoteGitRepo(self.author, self.repo_name)

    @property
    def info(self) -> RepoInfo:
        """Build a RepoInfo from local git state without contacting the remote.

        When HEAD has multiple tags, picks the highest PEP 440 version, else the lexicographically last.
        """
        repo = self._repo
        head = repo.head.commit

        branch: str | None = None
        if not repo.head.is_detached:
            branch = repo.active_branch.name

        head_tags = [t.name for t in repo.tags if t.commit == head]
        tag: str | None = None
        if head_tags:
            parsed = [(t, _parse_version(t)) for t in head_tags]
            versioned = [(t, v) for t, v in parsed if v is not None]
            tag = max(versioned, key=lambda x: x[1])[0] if versioned else sorted(head_tags)[-1]

        return RepoInfo(
            commit=head.hexsha,
            commit_short=head.hexsha[:7],
            branch=branch,
            tag=tag,
            tags=sorted(t.name for t in repo.tags),
            branches=[h.name for h in repo.heads],
        )

    def fetch(self) -> None:
        """Fetch refs and objects from the ``origin`` remote.

        :raises GitError: If the fetch command fails.
        """
        try:
            self._repo.remote("origin").fetch()
        except GitCommandError as e:
            raise GitError(f"Fetch failed: {self.url} ({e})") from e

    def pull(self) -> None:
        """Pull the current branch from ``origin``.

        :raises GitError: If the fetch or merge step fails (e.g. conflicts, detached HEAD).
        """
        try:
            self._repo.remote("origin").pull()
        except GitCommandError as e:
            raise GitError(f"Pull failed ({e})") from e

    def checkout(self, ref: str) -> None:
        """Check out the given branch, tag or commit in the working tree.

        :param ref: Branch, tag, or commit to check out.
        :raises GitError: If the ref does not exist or checkout fails.
        """
        try:
            self._repo.git.checkout(ref)
        except GitCommandError as e:
            raise GitError(f"Ref not found: {ref} ({e})") from e

    def set_origin(self, url: str) -> None:
        """Set or create the ``origin`` remote URL, invalidating cached author/repo_name/remote.

        :param url: New ``origin`` remote URL.
        """
        try:
            self._repo.remote("origin").set_url(url)
        except ValueError:
            self._repo.create_remote("origin", url)

        for cached in ("remote", "author", "repo_name"):
            self.__dict__.pop(cached, None)

    def has_updates(
        self,
        *,
        by: Literal["commit", "version"] = "commit",
        include_prerelease: bool = False,
    ) -> bool:
        """Return whether ``origin`` has content newer than the local HEAD (requires network).

        :param by: ``"commit"`` compares HEAD SHAs; ``"version"`` compares the local
            HEAD tag to the latest remote tag by PEP 440.
        :param include_prerelease: When ``by="version"``, also consider pre-release
            tags as candidates for the remote version.
        :returns: ``False`` if ``by="version"`` and the local HEAD is not on a
            parseable version tag, or if no comparable remote tag exists.
        """
        if by == "version":
            local_version = _parse_version(self.info.tag or "")
            if local_version is None:
                return False
            remote_info = self.remote.info
            candidates = [remote_info.latest_version]
            if include_prerelease:
                candidates.append(remote_info.latest_prerelease)
            remote_versions = [v for v in (_parse_version(c or "") for c in candidates) if v is not None]
            if not remote_versions:
                return False
            return max(remote_versions) > local_version
        return self.info.commit != self.remote.info.commit

    def update(self, ref: str | None = None) -> None:
        """Fetch from origin then either pull the current branch or check out ``ref``.

        :param ref: Branch or tag to check out after fetch; when ``None``, pulls the current branch instead.
        :raises GitError: If any of fetch, pull, or checkout fails.
        """
        self.fetch()
        if ref is None:
            self.pull()
        else:
            self.checkout(ref)

    def commit_date(self, ref: str = "HEAD") -> datetime:
        """Return the authored commit datetime for ``ref``, fetching it shallowly from origin if missing locally.

        :param ref: Branch, tag, or commit to resolve.
        :raises GitError: If the ref cannot be resolved locally or on origin.
        """
        try:
            return self._repo.commit(ref).committed_datetime
        except (BadName, ValueError):
            pass

        try:
            self._repo.git.fetch("origin", ref, depth=1)
            return self._repo.commit("FETCH_HEAD").committed_datetime
        except (BadName, ValueError, GitCommandError) as e:
            raise GitError(f"Unknown ref: {ref} ({e})") from e


def _parse_version(tag: str) -> Version | None:
    """Parse a tag as a PEP 440 Version, stripping an optional ``v``/``V`` prefix; ``None`` on failure.

    :param tag: Tag name to parse.
    """
    try:
        return Version(tag.lstrip("vV"))
    except InvalidVersion:
        return None


def _parse_git_url(url: str) -> tuple[str, str, str]:
    """Parse a git URL into ``(author, repo, branch)``, supporting HTTPS, ``git@`` and ``owner/repo`` shorthand.

    Branch is extracted from a ``/tree/<ref>`` suffix when present, otherwise defaults to ``"HEAD"``.

    :param url: Git URL or ``owner/repo`` shorthand to parse.
    :raises ValueError: If the URL is an unsupported scheme or missing owner/repo.
    """
    url = url.strip()
    if url.startswith("git@"):
        url = "https://" + url[4:].replace(":", "/", 1)
    if "/" in url and "://" not in url and not url.startswith(("http", "https")):
        url = f"https://github.com/{url}"
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Unsupported URL format: {url}")

    parts = [p for p in urlparse(url).path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"URL missing author/repo: {url}")

    author = parts[0]
    repo = parts[1].removesuffix(".git")
    branch = "/".join(parts[3:]) if len(parts) >= 4 and parts[2] == "tree" else "HEAD"
    return author, repo, branch


def _parse_ls_remote(output: str) -> RepoInfo:
    """Build a RepoInfo from ``git ls-remote`` text output, resolving annotated tag ``^{}`` peels.

    :param output: Raw text output from ``git ls-remote``.
    """
    refs: dict[str, str] = {}
    for line in output.strip().splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            refs[parts[1]] = parts[0]

    head_sha = refs.get("HEAD", "")

    tags: list[str] = []
    tag_shas: dict[str, str] = {}
    for ref, sha in refs.items():
        if ref.startswith("refs/tags/") and not ref.endswith("^{}"):
            name = ref.removeprefix("refs/tags/")
            deref_sha = refs.get(f"{ref}^{{}}", sha)
            tags.append(name)
            tag_shas[name] = deref_sha

    branches: list[str] = []
    branch_shas: dict[str, str] = {}
    for ref, sha in refs.items():
        if ref.startswith("refs/heads/"):
            name = ref.removeprefix("refs/heads/")
            branches.append(name)
            branch_shas[name] = sha

    head_tag: str | None = None
    head_matches = [t for t, s in tag_shas.items() if s == head_sha]
    if head_matches:
        parsed = [(t, _parse_version(t)) for t in head_matches]
        versioned = [(t, v) for t, v in parsed if v is not None]
        head_tag = max(versioned, key=lambda x: x[1])[0] if versioned else sorted(head_matches)[-1]

    head_branch: str | None = None
    for name, sha in branch_shas.items():
        if sha == head_sha:
            head_branch = name
            break

    return RepoInfo(
        commit=head_sha,
        commit_short=head_sha[:7],
        branch=head_branch,
        tag=head_tag,
        tags=sorted(tags),
        branches=sorted(branches),
    )
