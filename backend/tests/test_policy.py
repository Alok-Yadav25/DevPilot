from pathlib import Path

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
