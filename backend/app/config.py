from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "production"] = "production"
    retention_seconds: int = Field(default=86400, ge=3600)
    max_queued_runs: int = Field(default=20, ge=1, le=100)
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-120b"
    github_token: SecretStr = SecretStr("")
    target_github_token: SecretStr = SecretStr("")
    sandbox_github_token: SecretStr = SecretStr("")
    sandbox_repo: str = ""
    sandbox_default_branch: str = "main"
    allowed_target_repos: str = ""
    runner_mode: Literal["github_actions", "docker", "replay"] = "github_actions"
    max_repo_mb: int = Field(default=50, ge=1, le=50)
    actions_timeout_seconds: int = Field(default=900, ge=30, le=1800)
    sandbox_image: str = "devpilot-sandbox:py311"
    test_timeout_seconds: int = Field(default=120, ge=5, le=120)
    run_timeout_seconds: int = Field(default=900, ge=10, le=1800)
    clone_timeout_seconds: int = Field(default=90, ge=1, le=120)
    max_attempts: int = Field(default=3, ge=1, le=3)
    max_repo_bytes: int = Field(default=100 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    max_repo_files: int = Field(default=10_000, ge=1, le=10_000)
    max_patch_lines: int = Field(default=200, ge=1, le=200)
    max_patch_files: int = Field(default=5, ge=1, le=5)
    work_root: Path = Path(".devpilot/workspaces")
    artifact_root: Path = Path(".devpilot/runs")
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://devpilot:devpilot@127.0.0.1:5432/devpilot"
    )
    database_auto_create: bool = False
    api_access_token: SecretStr = SecretStr("")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "CORS_ORIGINS", "cors_origins"),
    )
    max_concurrent_runs: int = Field(default=1, ge=1, le=3)
    requests_per_minute: int = Field(default=30, ge=1, le=120)

    def secrets(self) -> list[str]:
        return [
            self.groq_api_key.get_secret_value(),
            self.github_token.get_secret_value(),
            self.api_access_token.get_secret_value(),
            self.sandbox_github_token.get_secret_value(),
            self.target_github_token.get_secret_value(),
            self.database_url.get_secret_value(),
        ]
