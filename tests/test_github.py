import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from mypycli.utils.github import (
    GitError,
    GitRepo,
    RemoteCommit,
    RepoRef,
    parse_github_url,
)


def git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@test", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture()
def remote_and_clone(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin"
    origin.mkdir()
    git("init", "--bare", "--initial-branch=master", ".", cwd=origin)

    seed = tmp_path / "seed"
    seed.mkdir()
    git("init", "--initial-branch=master", ".", cwd=seed)
    (seed / "file.txt").write_text("one")
    git("add", ".", cwd=seed)
    git("commit", "-m", "first", cwd=seed)
    git("remote", "add", "origin", str(origin), cwd=seed)
    git("push", "-u", "origin", "master", cwd=seed)

    clone = tmp_path / "clone"
    git("clone", str(origin), str(clone), cwd=tmp_path)
    return origin, clone


class TestParseGithubUrl:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://github.com/igroman787/mytonprovider", RepoRef("igroman787", "mytonprovider", None)),
            ("https://github.com/xssnick/tonutils-storage.git", RepoRef("xssnick", "tonutils-storage", None)),
            ("https://github.com/a/b/tree/dev", RepoRef("a", "b", "dev")),
            ("https://github.com/a/b/tree/feature/x", RepoRef("a", "b", "feature/x")),
            ("git@github.com:nessshon/mypycli.git", RepoRef("nessshon", "mypycli", None)),
            ("author/repo", RepoRef("author", "repo", None)),
            ("https://github.com/a/b/", RepoRef("a", "b", None)),
        ],
    )
    def test_valid(self, url: str, expected: RepoRef) -> None:
        assert parse_github_url(url) == expected

    @pytest.mark.parametrize(
        "url",
        ["", "just-a-name", "https://github.com/only-author", "http://gitlab.com/a b", "gitlab.com/repo"],
    )
    def test_invalid(self, url: str) -> None:
        with pytest.raises(GitError):
            parse_github_url(url)


class TestRemoteCommit:
    def test_commit_short(self) -> None:
        info = RemoteCommit(commit="a1b2c3d4e5f60718293a4b5c6d7e8f9012345678", date=datetime(2026, 1, 1))
        assert info.commit_short == "a1b2c3d"


class TestGitRepo:
    def test_commit_and_branch(self, remote_and_clone: tuple[Path, Path]) -> None:
        _origin, clone = remote_and_clone
        repo = GitRepo(clone)

        assert len(repo.commit) == 40
        assert repo.commit.startswith(repo.commit_short)
        assert repo.branch == "master"

    def test_url_author_repo(self, remote_and_clone: tuple[Path, Path]) -> None:
        origin, clone = remote_and_clone
        assert GitRepo(clone).url == str(origin)

    def test_not_a_repo(self, tmp_path: Path) -> None:
        with pytest.raises(GitError):
            _ = GitRepo(tmp_path).commit

    def test_detached_head(self, remote_and_clone: tuple[Path, Path]) -> None:
        _origin, clone = remote_and_clone
        git("checkout", "--detach", cwd=clone)
        repo = GitRepo(clone)

        assert repo.branch is None
        with pytest.raises(GitError):
            repo.remote_commit()

    def test_has_updates_false_when_in_sync(self, remote_and_clone: tuple[Path, Path]) -> None:
        _origin, clone = remote_and_clone
        repo = GitRepo(clone)

        assert repo.remote_commit() == repo.commit
        assert repo.has_updates() is False

    def test_has_updates_and_pull(self, remote_and_clone: tuple[Path, Path]) -> None:
        origin, clone = remote_and_clone
        other = origin.parent / "other"
        git("clone", str(origin), str(other), cwd=origin.parent)
        (other / "file.txt").write_text("two")
        git("commit", "-am", "second", cwd=other)
        git("push", cwd=other)

        repo = GitRepo(clone)
        assert repo.has_updates() is True

        repo.pull()
        assert repo.has_updates() is False
        assert repo.commit == GitRepo(other).commit

    def test_switch_to_fork_with_diverged_history(self, remote_and_clone: tuple[Path, Path]) -> None:
        origin, clone = remote_and_clone
        fork = origin.parent / "fork"
        git("clone", str(origin), str(fork), cwd=origin.parent)
        git("checkout", "-b", "dev", cwd=fork)
        (fork / "file.txt").write_text("fork change")
        git("commit", "-am", "diverged", cwd=fork)

        repo = GitRepo(clone)
        repo.set_origin(str(fork))
        repo.checkout("dev")

        assert repo.url == str(fork)
        assert repo.branch == "dev"
        assert repo.commit == GitRepo(fork).commit

    def test_checkout_another_branch_same_origin(self, remote_and_clone: tuple[Path, Path]) -> None:
        origin, clone = remote_and_clone
        other = origin.parent / "other2"
        git("clone", str(origin), str(other), cwd=origin.parent)
        git("checkout", "-b", "beta", cwd=other)
        (other / "beta.txt").write_text("beta")
        git("add", ".", cwd=other)
        git("commit", "-m", "beta commit", cwd=other)
        git("push", "-u", "origin", "beta", cwd=other)

        repo = GitRepo(clone)
        repo.checkout("beta")
        assert repo.branch == "beta"
        assert repo.commit == GitRepo(other).commit

    def test_checkout_missing_branch_raises(self, remote_and_clone: tuple[Path, Path]) -> None:
        _origin, clone = remote_and_clone
        with pytest.raises(GitError):
            GitRepo(clone).checkout("no-such-branch")

    def test_clone(self, remote_and_clone: tuple[Path, Path]) -> None:
        origin, clone = remote_and_clone
        dest = origin.parent / "fresh"
        repo = GitRepo.clone(str(origin), dest)

        assert repo.path == dest
        assert repo.commit == GitRepo(clone).commit
        assert repo.branch == "master"

    def test_clone_bad_url_raises(self, tmp_path: Path) -> None:
        with pytest.raises(GitError):
            GitRepo.clone(str(tmp_path / "no-such-origin"), tmp_path / "dest")

    def test_clone_force_replaces_existing(self, remote_and_clone: tuple[Path, Path]) -> None:
        origin, _clone = remote_and_clone
        dest = origin.parent / "dest"
        dest.mkdir()
        (dest / "stale.txt").write_text("old")

        repo = GitRepo.clone(str(origin), dest, force=True)
        assert not (dest / "stale.txt").exists()
        assert repo.branch == "master"
