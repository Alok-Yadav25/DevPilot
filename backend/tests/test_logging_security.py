import io
import json
import logging
from pathlib import Path

from app.config import Settings
from app.logging import RedactingFormatter
from app.main import create_app
from app.security import Redactor
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr


def fake_tokens() -> list[str]:
    # Assemble dummies at runtime: these are not real credentials or scanner exceptions.
    return [
        "gsk_" + "A1b2" * 14,
        "github_pat_" + "C3d4" * 20,
        "ghp_" + "E5f6" * 9,
        "fake-worker-session-credential",
    ]


def test_logger_redacts_arguments_json_and_exception_tracebacks() -> None:
    tokens = fake_tokens()
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(RedactingFormatter(Redactor(tokens)))
    logger = logging.Logger("devpilot-security-test")
    logger.addHandler(handler)
    logger.warning("key=%s Authorization: Bearer %s", tokens[0], tokens[3])
    logger.error(json.dumps({"Authorization": "Bearer " + tokens[1]}))
    try:
        raise RuntimeError("Transport failed with " + tokens[2])
    except RuntimeError:
        logger.exception("Failure while processing %s", tokens[0])
    text = output.getvalue()
    assert all(token not in text for token in tokens)
    assert "[REDACTED]" in text and "Traceback" in text and "Transport failed" in text


def test_database_and_authenticated_clone_urls_are_redacted() -> None:
    text = Redactor()(
        "postgresql+psycopg://user:db-pass@db.example/db "
        "https://user:git-pass@github.com/owner/repo"
    )
    assert "db-pass" not in text and "git-pass" not in text


def test_api_redacts_validation_http_and_unhandled_errors(tmp_path: Path) -> None:
    key = fake_tokens()[0]
    config = Settings(
        _env_file=None,
        runner_mode="replay",
        groq_api_key=SecretStr(key),
        database_url=SecretStr(f"sqlite:///{tmp_path}/test.db"),
        database_auto_create=True,
        api_access_token=SecretStr("test-access"),
        work_root=tmp_path / "work",
    )
    app = create_app(config)

    @app.get("/test-http-error")
    def error() -> None:
        raise HTTPException(409, {"error": "failed " + key, "Authorization": "Bearer " + key})

    @app.get("/test-internal-error")
    def crash() -> None:
        raise RuntimeError(key)

    with TestClient(app, raise_server_exceptions=False) as client:
        invalid = client.post(
            "/api/runs",
            headers={"Authorization": "Bearer test-access"},
            json={"repo_url": key, "issue_text": "Fix a failure"},
        )
        assert invalid.status_code == 422
        assert key not in invalid.text and "REDACTED" in invalid.text
        failure = client.get("/test-http-error")
        assert failure.status_code == 409 and key not in failure.text
        assert int(failure.headers["content-length"]) == len(failure.content)
        crash_response = client.get("/test-internal-error")
        assert crash_response.status_code == 500 and key not in crash_response.text


def test_env_examples_have_no_provider_credentials() -> None:
    import re

    for path in (Path(".env.example"), Path("frontend/.env.example")):
        text = path.read_text()
        assert not re.search(r"(?:gsk_|ghp_|github_pat_)[A-Za-z0-9_]{15,}", text)
        for line in text.splitlines():
            if line.startswith(
                (
                    "GROQ_API_KEY=",
                    "GITHUB_TOKEN=",
                    "TARGET_GITHUB_TOKEN=",
                    "SANDBOX_GITHUB_TOKEN=",
                    "API_ACCESS_TOKEN=",
                )
            ):
                assert not line.split("=", 1)[1].strip()
