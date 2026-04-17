from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import PropertyMock, patch

import pytest
from git import Repo

from mypycli.utils.github import (
    GitError,
    LocalGitRepo,
    RemoteGitRepo,
    RepoInfo,
    _parse_git_url,
    _parse_ls_remote,
)

if TYPE_CHECKING:
    from pathlib import Path


def _init_repo(tmp_path: Path, *, origin: str = "https://github.com/test/repo") -> Repo:
    repo = Repo.init(str(tmp_path))
    repo.create_remote("origin", origin)
    (tmp_path / "file.txt").write_text("hello")
    repo.index.add(["file.txt"])
    repo.index.commit("initial")
    return repo


def _info(
    *, tags: list[str] | None = None, commit: str = "a" * 40, branch: str | None = "main", tag: str | None = None
) -> RepoInfo:
    return RepoInfo(commit=commit, commit_short=commit[:7], branch=branch, tag=tag, tags=tags or [])


class TestRepoInfoVersion:
    def test_tag_wins_over_branch(self) -> None:
        assert _info(tag="v2.0.0").version == "v2.0.0"

    def test_branch_with_short_sha(self) -> None:
        assert _info(commit="abc1234" + "0" * 33, branch="main").version == "main@abc1234"

    def test_detached_head_shows_short_sha(self) -> None:
        assert _info(commit="abc1234" + "0" * 33, branch=None).version == "abc1234"


class TestRepoInfoLatestVersion:
    def test_picks_highest_stable(self) -> None:
        assert _info(tags=["v1.0.0", "v1.1.0-rc1", "v1.2.0", "v0.9.0"]).latest_version == "v1.2.0"

    def test_excludes_prerelease(self) -> None:
        assert _info(tags=["v1.0.0", "v2.0.0-rc1"]).latest_version == "v1.0.0"

    def test_none_when_all_prerelease(self) -> None:
        assert _info(tags=["v1.0.0-rc1", "v2.0.0-beta"]).latest_version is None

    def test_ignores_non_semver_tags(self) -> None:
        assert _info(tags=["hotfix-2024", "v1.0.0", "deploy-prod", "release"]).latest_version == "v1.0.0"

    def test_semver_not_lexicographic(self) -> None:
        assert _info(tags=["v2.0.0", "v10.0.0"]).latest_version == "v10.0.0"


class TestRepoInfoLatestPrerelease:
    def test_picks_highest_prerelease(self) -> None:
        assert _info(tags=["v2.0.0-rc1", "v2.0.0-rc2", "v1.0.0"]).latest_prerelease == "v2.0.0-rc2"

    def test_none_when_no_prereleases(self) -> None:
        assert _info(tags=["v1.0.0", "v2.0.0"]).latest_prerelease is None


class TestParseGitUrl:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://github.com/user/repo", ("user", "repo", "HEAD")),
            ("https://github.com/user/repo.git", ("user", "repo", "HEAD")),
            ("git@github.com:user/repo.git", ("user", "repo", "HEAD")),
            ("user/repo", ("user", "repo", "HEAD")),
            ("https://github.com/u/r/tree/dev", ("u", "r", "dev")),
            ("https://github.com/u/r/tree/feature/auth", ("u", "r", "feature/auth")),
            ("  user/repo  ", ("user", "repo", "HEAD")),
        ],
    )
    def test_accepted(self, url: str, expected: tuple[str, str, str]) -> None:
        assert _parse_git_url(url) == expected

    @pytest.mark.parametrize("url", ["", "https://github.com/only-user"])
    def test_rejected(self, url: str) -> None:
        with pytest.raises(ValueError):
            _parse_git_url(url)


class TestParseLsRemote:
    def test_basic_refs(self) -> None:
        output = (
            "abc123\tHEAD\n"
            "abc123\trefs/heads/main\n"
            "def456\trefs/heads/dev\n"
            "789abc\trefs/tags/v1.0.0\n"
            "012def\trefs/tags/v2.0.0\n"
        )
        info = _parse_ls_remote(output)
        assert info.commit == "abc123"
        assert info.branch == "main"
        assert info.tag is None
        assert set(info.tags) == {"v1.0.0", "v2.0.0"}
        assert set(info.branches) == {"main", "dev"}

    def test_detects_tag_at_head(self) -> None:
        output = "789abc\tHEAD\n789abc\trefs/heads/main\n789abc\trefs/tags/v1.0.0\n"
        assert _parse_ls_remote(output).tag == "v1.0.0"

    def test_annotated_tag_dereferenced(self) -> None:
        output = "aaa111\tHEAD\naaa111\trefs/heads/main\ntagobject\trefs/tags/v1.0.0\naaa111\trefs/tags/v1.0.0^{}\n"
        assert _parse_ls_remote(output).tag == "v1.0.0"

    def test_picks_highest_semver_at_head(self) -> None:
        output = "abc\tHEAD\nabc\trefs/tags/v1.0.0\nabc\trefs/tags/v2.0.0\n"
        assert _parse_ls_remote(output).tag == "v2.0.0"

    def test_empty_output(self) -> None:
        info = _parse_ls_remote("")
        assert info.commit == ""
        assert info.tags == []
        assert info.branches == []


class TestRemoteGitRepo:
    def test_url_from_author_repo(self) -> None:
        assert RemoteGitRepo("user", "repo").url == "https://github.com/user/repo"

    def test_from_url(self) -> None:
        remote = RemoteGitRepo.from_url("https://github.com/nessshon/tonutils")
        assert (remote.author, remote.repo_name) == ("nessshon", "tonutils")

    def test_from_invalid_url_raises_git_error(self) -> None:
        with pytest.raises(GitError, match="Invalid git URL"):
            RemoteGitRepo.from_url("not-a-url")


class TestLocalGitRepoConstruction:
    def test_invalid_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(GitError, match="Path not found"):
            LocalGitRepo(tmp_path / "nonexistent")

    def test_not_git_repo_raises(self, tmp_path: Path) -> None:
        with pytest.raises(GitError, match="Not a git repository"):
            LocalGitRepo(tmp_path)

    def test_no_origin_raises(self, tmp_path: Path) -> None:
        repo = Repo.init(str(tmp_path))
        (tmp_path / "f.txt").write_text("x")
        repo.index.add(["f.txt"])
        repo.index.commit("init")
        with pytest.raises(GitError, match="No origin remote"):
            LocalGitRepo(tmp_path)


class TestLocalGitRepoInfo:
    def test_basic_fields(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        info = LocalGitRepo(tmp_path).info
        assert len(info.commit) == 40
        assert info.commit_short == info.commit[:7]
        assert info.branch is not None
        assert info.tag is None

    def test_detects_tag_at_head(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        repo.create_tag("v1.0.0")
        assert LocalGitRepo(tmp_path).info.tag == "v1.0.0"

    def test_tags_list_and_latest_version(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        repo.create_tag("v1.0.0")
        (tmp_path / "file.txt").write_text("v2")
        repo.index.add(["file.txt"])
        repo.index.commit("second")
        repo.create_tag("v2.0.0")
        info = LocalGitRepo(tmp_path).info
        assert set(info.tags) == {"v1.0.0", "v2.0.0"}
        assert info.latest_version == "v2.0.0"

    def test_author_and_repo_from_origin(self, tmp_path: Path) -> None:
        _init_repo(tmp_path, origin="https://github.com/nessshon/tonutils")
        local = LocalGitRepo(tmp_path)
        assert (local.author, local.repo_name) == ("nessshon", "tonutils")


class TestLocalGitRepoCheckout:
    def test_switches_to_branch(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        repo.create_head("dev")
        local = LocalGitRepo(tmp_path)
        local.checkout("dev")
        assert local.info.branch == "dev"

    def test_tag_creates_detached_head(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        repo.create_tag("v1.0.0")
        (tmp_path / "file.txt").write_text("v2")
        repo.index.add(["file.txt"])
        repo.index.commit("second")
        local = LocalGitRepo(tmp_path)
        local.checkout("v1.0.0")
        info = local.info
        assert info.branch is None
        assert info.tag == "v1.0.0"

    def test_invalid_ref_raises(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        with pytest.raises(GitError, match="Ref not found"):
            LocalGitRepo(tmp_path).checkout("nonexistent-ref")


class TestLocalGitRepoCommitDate:
    def test_head_returns_tz_aware_datetime(self, tmp_path: Path) -> None:
        from datetime import datetime

        _init_repo(tmp_path)
        date = LocalGitRepo(tmp_path).commit_date()
        assert isinstance(date, datetime)
        assert date.tzinfo is not None

    def test_local_tag_matches_head(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path)
        repo.create_tag("v1.0.0")
        local = LocalGitRepo(tmp_path)
        assert local.commit_date("v1.0.0") == local.commit_date("HEAD")

    def test_unknown_ref_raises(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        with pytest.raises(GitError, match="Unknown ref"):
            LocalGitRepo(tmp_path).commit_date("nonexistent-ref")


class TestLocalGitRepoSetOrigin:
    def test_replaces_url_and_invalidates_caches(self, tmp_path: Path) -> None:
        _init_repo(tmp_path, origin="https://github.com/old/repo")
        local = LocalGitRepo(tmp_path)
        assert local.author == "old"
        assert local.remote.author == "old"

        local.set_origin("https://github.com/new/repo")
        assert local.url == "https://github.com/new/repo"
        assert local.author == "new"
        assert local.remote.author == "new"


class TestHasUpdates:
    @pytest.fixture
    def make_local(self, tmp_path: Path):
        def _factory(local_tag: str | None = None) -> LocalGitRepo:
            repo = _init_repo(tmp_path)
            if local_tag:
                repo.create_tag(local_tag)
            return LocalGitRepo(tmp_path)

        return _factory

    def _mock_remote(self, local: LocalGitRepo, *, tags: list[str], commit: str = "remote_commit"):
        remote_info = RepoInfo(
            commit=commit,
            commit_short=commit[:7],
            branch="main",
            tag=None,
            tags=tags,
        )
        return patch.object(type(local.remote), "info", new_callable=PropertyMock, return_value=remote_info)

    def test_commit_mode_detects_diff(self, make_local) -> None:
        local = make_local()
        with self._mock_remote(local, tags=[], commit="different_sha"):
            assert local.has_updates(by="commit") is True

    def test_commit_mode_no_diff(self, make_local) -> None:
        local = make_local()
        with self._mock_remote(local, tags=[], commit=local.info.commit):
            assert local.has_updates(by="commit") is False

    def test_version_mode_newer_stable(self, make_local) -> None:
        local = make_local(local_tag="v1.0.0")
        with self._mock_remote(local, tags=["v1.0.0", "v2.0.0"]):
            assert local.has_updates(by="version") is True

    def test_version_mode_same_version(self, make_local) -> None:
        local = make_local(local_tag="v1.0.0")
        with self._mock_remote(local, tags=["v1.0.0"]):
            assert local.has_updates(by="version") is False

    def test_version_mode_local_not_on_tag_returns_false(self, make_local) -> None:
        local = make_local(local_tag=None)
        with self._mock_remote(local, tags=["v1.0.0", "v2.0.0"]):
            assert local.has_updates(by="version") is False

    def test_version_mode_ignores_prerelease_by_default(self, make_local) -> None:
        local = make_local(local_tag="v1.0.0")
        with self._mock_remote(local, tags=["v1.0.0", "v2.0.0-rc1"]):
            assert local.has_updates(by="version") is False

    def test_include_prerelease_considers_rc(self, make_local) -> None:
        local = make_local(local_tag="v1.0.0")
        with self._mock_remote(local, tags=["v1.0.0", "v2.0.0-rc1"]):
            assert local.has_updates(by="version", include_prerelease=True) is True

    def test_include_prerelease_picks_max_of_stable_and_rc(self, make_local) -> None:
        local = make_local(local_tag="v1.5.0")
        with self._mock_remote(local, tags=["v1.5.0", "v2.0.0", "v1.0.0-rc1"]):
            assert local.has_updates(by="version", include_prerelease=True) is True
