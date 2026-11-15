"""Migrate durable state before starting the single production API process."""

import logging
import os

from alembic import command
from alembic.config import Config

from app.config import Settings
from app.errors import DevPilotError
from app.logging import configure_redacted_logging
from app.sandbox.factory import validate_runner_settings


def launch(settings: Settings | None = None) -> None:
    config = settings or Settings()
    configure_redacted_logging(config.secrets())
    try:
        validate_runner_settings(config)
        if config.app_env == "production" and not config.database_url.get_secret_value().startswith(
            "postgresql+psycopg://"
        ):
            raise DevPilotError("Production requires a PostgreSQL DATABASE_URL.")
        if not config.api_access_token.get_secret_value():
            raise DevPilotError("Set API_ACCESS_TOKEN before starting the hosted API.")
        port = int(os.environ.get("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise DevPilotError("PORT must be between 1 and 65535.")
        command.upgrade(Config("alembic.ini"), "head")
    except Exception:
        logging.getLogger("app.serve").exception("API startup failed")
        raise SystemExit(1) from None
    os.execvp(
        "uvicorn",
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port), "--workers", "1"],
    )


if __name__ == "__main__":
    launch()
