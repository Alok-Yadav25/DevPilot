from unittest.mock import patch

import pytest
from app.config import Settings
from app.serve import launch
from pydantic import SecretStr


def settings(**overrides: object) -> Settings:
    values: dict = dict(
        _env_file=None,
        app_env="production",
        runner_mode="replay",
        api_access_token="local-test-worker-access",
        database_url="postgresql+psycopg://worker:example@db.invalid/devpilot",
    )
    return Settings(**(values | overrides))


@pytest.mark.parametrize("prefix", ["postgres://", "postgresql://", "postgresql+psycopg://"])
def test_neon_connection_uri_uses_installed_driver(prefix: str) -> None:
    uri = prefix + "worker:example@db.invalid/devpilot?sslmode=require"
    assert settings(database_url=SecretStr(uri)).database_url.get_secret_value() == (
        "postgresql+psycopg://worker:example@db.invalid/devpilot?sslmode=require"
    )


def test_migration_finishes_before_api_exec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "10000")
    order: list[str] = []
    with (
        patch(
            "app.serve.command.upgrade", side_effect=lambda *args: order.append("migrate")
        ) as migrate,
        patch("app.serve.os.execvp", side_effect=lambda *args: order.append("serve")) as execute,
    ):
        launch(settings())
    assert order == ["migrate", "serve"]
    assert migrate.call_args.args[1] == "head"
    assert execute.call_args.args[1][-5:] == ["0.0.0.0", "--port", "10000", "--workers", "1"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"api_access_token": ""},
        {"database_url": "sqlite:///temporary.db"},
        {"runner_mode": "github_actions"},
    ],
)
def test_incomplete_production_settings_fail_before_database_mutation(overrides: dict) -> None:
    with (
        patch("app.serve.command.upgrade") as migrate,
        patch("app.serve.os.execvp") as execute,
        pytest.raises(SystemExit),
    ):
        launch(settings(**overrides))
    migrate.assert_not_called()
    execute.assert_not_called()


def test_failed_migration_never_starts_api() -> None:
    with (
        patch("app.serve.command.upgrade", side_effect=RuntimeError("migration failed")),
        patch("app.serve.os.execvp") as execute,
        pytest.raises(SystemExit),
    ):
        launch(settings())
    execute.assert_not_called()
