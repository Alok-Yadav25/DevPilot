from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from app.config import Settings
from app.errors import DevPilotError
from app.policy import RunPolicy
from conftest import seed_repo


@pytest.mark.parametrize(
    "url,metadata,expected",
    [
        (
            "https://github.com/owner/repo",
            {"private": False, "size": 1, "language": "Python"},
            None,
        ),
        ("https://github.com/owner/repo", {"private": True}, "Private"),
        ("https://evil.example/owner/repo", {}, "HTTPS GitHub"),
        ("https://github.com/owner/repo", {"private": False, "size": 999999}, "size limit"),
        ("https://github.com/other/repo", {}, "not allowlisted"),
        (
            "https://github.com/owner/repo",
            {"private": False, "language": "JavaScript"},
            "Python/pytest",
        ),
        ("https://github.com/owner/repo;id", {}, "HTTPS GitHub"),
        ("https://github.com/owner/../repo", {}, "HTTPS GitHub"),
    ],
)
def test_policy_table(url, metadata, expected):
    calls = []

    def handler(req):
        calls.append(req)
        assert "authorization" not in req.headers
        return httpx.Response(200, json=metadata)

    settings = Settings(_env_file=None, allowed_target_repos="owner/repo")
    with httpx.Client(
        base_url="https://api.github.com/", transport=httpx.MockTransport(handler)
    ) as client:
        policy = RunPolicy(settings, client)
        if expected:
            with pytest.raises(DevPilotError, match=expected):
                policy.remote(url, "Repair this bug")
        else:
            assert policy.remote(url, "Repair this bug").endswith("repo.git")
        if "owner/repo" not in url or any(c in url for c in [";", "../"]):
            assert not calls


def test_checkout_setup_file_count_and_attempt_limits(tmp_path: Path):
    settings = Settings(_env_file=None, allowed_target_repos="owner/repo")
    policy = RunPolicy(settings)
    with pytest.raises(DevPilotError, match="pytest"):
        policy.checkout(tmp_path)
    root = seed_repo(tmp_path / "repo")
    policy.checkout(root)
    settings.max_repo_files = 1
    with pytest.raises(DevPilotError, match="file-count"):
        policy.checkout(root)
    with pytest.raises(DevPilotError, match="Maximum patch attempts"):
        policy.request("https://github.com/owner/repo", "Repair this bug", 3)


def test_configured_owner_and_python_version(tmp_path):
    policy = RunPolicy(Settings(_env_file=None, allowed_target_owner="owner"))
    assert policy.request("https://github.com/owner/repo", "Repair this bug")
    (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python=">=3.12"\n')
    with pytest.raises(DevPilotError, match="Python 3.11"):
        policy.checkout(tmp_path)


@pytest.mark.parametrize("status", [403, 429])
def test_shared_metadata_quota_uses_bounded_anonymous_clone(tmp_path, status):
    settings = Settings(
        _env_file=None,
        allowed_target_repos="owner/repo",
        work_root=tmp_path / "work",
        sandbox_github_token="sandbox-private",
        target_github_token="target-private",
    )
    with (
        httpx.Client(
            base_url="https://api.github.com/",
            transport=httpx.MockTransport(lambda request: httpx.Response(status)),
        ) as client,
        patch("app.policy.Cloner") as cloner,
    ):
        cloner.return_value.clone.side_effect = lambda url, root: seed_repo(root)
        policy = RunPolicy(settings, client)
        assert policy.remote("https://github.com/owner/repo", "Repair this bug").endswith(
            "repo.git"
        )
        cloner.assert_called_once_with(
            50 * 1024 * 1024, settings.max_repo_files, settings.clone_timeout_seconds
        )
        assert not list(settings.work_root.iterdir())


@pytest.mark.parametrize("problem", ["inaccessible", "oversized", "unsupported"])
def test_metadata_fallback_keeps_policy_and_cleanup(tmp_path, problem):
    settings = Settings(
        _env_file=None, allowed_target_repos="owner/repo", work_root=tmp_path / "work"
    )

    def clone(url, root):
        if problem == "inaccessible":
            raise DevPilotError("Clone failed")
        if problem == "oversized":
            root.mkdir()
            (root / "large").write_bytes(b"x" * 2000)
            settings.max_repo_bytes = 1024
        else:
            root.mkdir()

    expected = {
        "inaccessible": "Anonymous repository access failed",
        "oversized": "size or file-count",
        "unsupported": "pytest",
    }[problem]
    with (
        httpx.Client(
            base_url="https://api.github.com/",
            transport=httpx.MockTransport(lambda request: httpx.Response(429)),
        ) as client,
        patch("app.policy.Cloner") as cloner,
    ):
        cloner.return_value.clone.side_effect = clone
        with pytest.raises(DevPilotError, match=expected):
            RunPolicy(settings, client).remote("https://github.com/owner/repo", "Repair this bug")
        assert not list(settings.work_root.iterdir())
