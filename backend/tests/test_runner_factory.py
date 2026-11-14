from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.config import Settings
from app.errors import DevPilotError
from app.sandbox.factory import ReplayRunner, make_runner, validate_runner_settings
from pydantic import SecretStr


def actions_settings(**overrides):
    return Settings(
        _env_file=None,
        sandbox_repo="owner/sandbox",
        allowed_target_repos="owner/target",
        sandbox_github_token=SecretStr("fake-sandbox-token"),
        target_github_token=SecretStr("fake-target-token"),
        **overrides,
    )


def test_production_defaults_to_actions_and_refuses_incomplete_setup():
    settings = Settings(_env_file=None)
    assert settings.runner_mode == "github_actions" and settings.app_env == "production"
    with pytest.raises(DevPilotError, match="SANDBOX_REPO"):
        validate_runner_settings(settings)


def test_production_cannot_select_local_runner():
    with pytest.raises(DevPilotError, match="APP_ENV=local"):
        make_runner(Settings(_env_file=None, runner_mode="docker"))


def test_factory_selects_actions_without_loading_local_sdk():
    with patch("app.sandbox.github_actions.GitHubActionsRunner") as constructor:
        constructor.return_value.close = AsyncMock()
        runner = make_runner(actions_settings())
        assert runner.runner is constructor.return_value
        assert constructor.call_args.args[1] == "fake-sandbox-token"
        runner.close()


def test_factory_selects_local_only_explicitly():
    with patch("app.sandbox.docker_runner.DockerRunner", return_value=MagicMock()) as constructor:
        assert (
            make_runner(Settings(_env_file=None, runner_mode="docker", app_env="local"))
            is constructor.return_value
        )


def test_replay_never_executes_code(tmp_path):
    runner = make_runner(Settings(_env_file=None, runner_mode="replay"))
    assert isinstance(runner, ReplayRunner)
    runner.preflight()
    with pytest.raises(DevPilotError, match="Select a recorded run"):
        runner.run(tmp_path)


def test_same_credential_cannot_authorize_both_repositories():
    settings = actions_settings()
    settings.target_github_token = settings.sandbox_github_token
    with pytest.raises(DevPilotError, match="different"):
        validate_runner_settings(settings)
