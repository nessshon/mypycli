from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import requests

from mypycli.utils.system import run

GITHUB_API_URL = "https://api.github.com"

_GITHUB_URL_RE = re.compile(
    r"^(?:https?://github\.com/|git@github\.com:)?"
    r"(?P<author>[A-Za-z0-9-]+)/"
    r"(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?"
    r"(?:/tree/(?P<branch>\S+?))?/?$"
)


class GitError(Exception):
    pass


class RepoRef(NamedTuple):
    author: str
    repo: str
    branch: str | None


@dataclass(frozen=True)
class RemoteCommit:
    commit: str
    date: datetime

    @property
    def commit_short(self) -> str:
        return self.commit[:7]


def parse_github_url(url: str) -> RepoRef:
    match = _GITHUB_URL_RE.match(url.strip())
    if match is None:
        raise GitError(f"parse_github_url: cannot parse {url!r}")
    return RepoRef(match["author"], match["repo"], match["branch"])


def validate_repo(author: str, repo: str) -> bool:
    result = run(["git", "ls-remote", f"https://github.com/{author}/{repo}"], timeout=30)
    return result.returncode == 0


class GitRepo:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @classmethod
    def clone(cls, url: str, path: str | Path, branch: str | None = None, *, force: bool = False) -> GitRepo:
        path = Path(path)
        if force and path.exists():
            try:
                shutil.rmtree(path)
            except OSError as e:
                raise GitError(f"clone: cannot remove {path}: {e}") from e
        args = ["git", "clone", url, str(path)]
        if branch is not None:
            args += ["--branch", branch]
        result = run(args, timeout=600)
        if result.returncode != 0:
            raise GitError(f"git clone {url} failed: {result.stderr.strip()}")
        return cls(path)

    def _git(self, *args: str, timeout: float = 10) -> str:
        result = run(["git", "-C", self.path, *args], timeout=timeout)
        if result.returncode != 0:
            raise GitError(f"git {args[0]} failed in {self.path}: {result.stderr.strip()}")
        return result.stdout.strip()

    @property
    def commit(self) -> str:
        return self._git("rev-parse", "HEAD")

    @property
    def commit_short(self) -> str:
        return self._git("rev-parse", "--short", "HEAD")

    @property
    def branch(self) -> str | None:
        name = self._git("rev-parse", "--abbrev-ref", "HEAD")
        return None if name == "HEAD" else name

    @property
    def url(self) -> str:
        return self._git("remote", "get-url", "origin")

    @property
    def author(self) -> str:
        return parse_github_url(self.url).author

    @property
    def repo(self) -> str:
        return parse_github_url(self.url).repo

    def remote_commit(self) -> str:
        branch = self._required_branch()
        output = self._git("ls-remote", "origin", f"refs/heads/{branch}", timeout=30)
        if not output:
            raise GitError(f"remote_commit: branch {branch!r} not found on origin of {self.path}")
        return output.split()[0]

    def remote_commit_info(self) -> RemoteCommit:
        branch = self._required_branch()
        parsed = parse_github_url(self.url)
        api_url = f"{GITHUB_API_URL}/repos/{parsed.author}/{parsed.repo}/branches/{branch}"

        try:
            response = requests.get(api_url, timeout=10)
        except requests.RequestException as e:
            raise GitError(f"remote_commit_info: request failed: {e}") from e

        if response.status_code == 403:
            raise GitError("remote_commit_info: GitHub API rate limit exceeded")
        if response.status_code != 200:
            raise GitError(f"remote_commit_info: GitHub API returned {response.status_code} for {api_url}")

        data = response.json()
        raw_date = data["commit"]["commit"]["committer"]["date"]
        date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        return RemoteCommit(commit=data["commit"]["sha"], date=date)

    def has_updates(self) -> bool:
        return self.commit != self.remote_commit()

    def pull(self) -> None:
        self._git("pull", "--ff-only", timeout=300)

    def checkout(self, branch: str) -> None:
        self._git("fetch", "origin", "--prune", timeout=300)
        self._git("checkout", "-B", branch, f"origin/{branch}", timeout=60)

    def set_origin(self, url: str) -> None:
        result = run(["git", "-C", self.path, "remote", "set-url", "origin", url])
        if result.returncode != 0:
            self._git("remote", "add", "origin", url)

    def ensure_safe_directory(self) -> None:
        path = str(self.path.resolve())
        result = run(["git", "config", "--global", "--get-all", "safe.directory"])
        existing = result.stdout.splitlines() if result.returncode == 0 else []
        if path not in existing and "*" not in existing:
            run(["git", "config", "--global", "--add", "safe.directory", path], check=True)

    def _required_branch(self) -> str:
        branch = self.branch
        if branch is None:
            raise GitError(f"detached HEAD in {self.path}: cannot resolve remote branch")
        return branch
