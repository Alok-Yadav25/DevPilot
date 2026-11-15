import os
from pathlib import Path
from unittest.mock import patch

import pytest
from app.errors import DevPilotError, UnsuitableRepository
from app.github.clone import (
    Cloner,
    cleanup_stale,
    git_env,
    inspect_tree,
    validate_repo_url,
    workspace,
)
from git import Repo


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/user/repo",
        "https://github.com.evil.com/user/repo",
        "https://github.com@evil.com/user/repo",
        "https://token@github.com/user/repo",
        "https://github.com/user/repo?token=secret",
        "https://github.com/user/repo#ref",
        "https://github.com/user/..",
        "file:///tmp/repo",
        "--upload-pack=evil",
        "https://github.com:443/user/repo",
        "https://github.com/user/repo/extra",
    ],
)
def test_urls_are_github_https_only(url: str) -> None:
    with pytest.raises(DevPilotError):
        validate_repo_url(url)


def test_url_normalized() -> None:
    assert validate_repo_url("https://github.com/owner/repo") == "https://github.com/owner/repo.git"
    assert validate_repo_url("https://github.com/owner/repo.git").endswith("repo.git")


def test_auth_only_in_clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "do-not-inherit")
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "malicious")
    env = git_env("a-private-token")
    assert "GROQ_API_KEY" not in env and "GIT_CONFIG_PARAMETERS" not in env
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert any("Authorization: Basic" in v for v in env.values())


def test_limits_and_symlinks(tmp_path: Path) -> None:
    (tmp_path / "data").write_bytes(b"x" * 2000)
    with pytest.raises(UnsuitableRepository, match="limit"):
        inspect_tree(tmp_path, 1000, 10)
    (tmp_path / "link").symlink_to("data")
    with pytest.raises(UnsuitableRepository, match="Symlink"):
        inspect_tree(tmp_path, 10000, 10)


def test_workspace_is_removed_after_exception(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError), workspace(tmp_path, "test") as path:
        path.mkdir()
        raise RuntimeError("interrupted")
    assert list(tmp_path.iterdir()) == []


def test_cleanup_respects_active_lease(tmp_path: Path) -> None:
    with workspace(tmp_path, "active") as path:
        os.utime(path.parent, (0, 0))
        assert cleanup_stale(tmp_path, max_age_seconds=1) == 0
    expired = tmp_path / "run-expired-123"
    expired.mkdir()
    (expired / ".lease").touch()
    os.utime(expired, (0, 0))
    assert cleanup_stale(tmp_path, max_age_seconds=1) == 1


def test_clone_transport_arguments_and_origin_scrub(repo: Path, tmp_path: Path) -> None:
    import subprocess

    actual_popen = subprocess.Popen
    seen: list[list[str]] = []

    def local_transport(command: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        seen.append(command)
        # Only the test double maps GitHub to a trusted local fixture transport.
        kwargs["env"] = {**git_env(), "GIT_CONFIG_COUNT": "0"}
        return actual_popen(
            ["git", "clone", "--depth", "1", "--single-branch", repo.as_uri(), command[-1]],
            **kwargs,
        )

    target = tmp_path / "cloned"
    with patch("app.github.clone.subprocess.Popen", side_effect=local_transport):
        sha = Cloner(1_000_000, 1000, 10, "not-in-command").clone(
            "https://github.com/owner/repo",
            target,
        )
    assert seen[0][1:6] == ["clone", "--depth", "1", "--single-branch", "--"]
    assert "not-in-command" not in str(seen)
    with Repo(target) as cloned:
        assert cloned.remotes.origin.url == "https://github.com/owner/repo.git"
        assert cloned.head.commit.hexsha == sha


def test_failed_clone_is_actionable(tmp_path: Path) -> None:
    with patch("app.github.clone.subprocess.Popen") as process:
        process.return_value.poll.return_value = 128
        process.return_value.returncode = 128
        process.return_value.stderr.read.return_value = b""
        with pytest.raises(DevPilotError, match="token permissions"):
            Cloner(10000, 100, 1).clone("https://github.com/owner/repo", tmp_path / "repo")


def test_clone_timeout_kills_transport_process_group(tmp_path: Path) -> None:
    with (
        patch("app.github.clone.subprocess.Popen") as process,
        patch("app.github.clone.os.killpg") as kill,
    ):
        process.return_value.poll.return_value = None
        process.return_value.stderr.read.return_value = b""
        with pytest.raises(DevPilotError, match="timed out"):
            Cloner(10000, 100, 0).clone("https://github.com/owner/repo", tmp_path / "repo")
        kill.assert_called_once()


def test_file_count_limit(tmp_path: Path) -> None:
    (tmp_path / "one").touch()
    (tmp_path / "two").touch()
    with pytest.raises(UnsuitableRepository, match="file-count"):
        inspect_tree(tmp_path, 10000, 1)
