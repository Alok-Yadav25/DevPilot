import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from app.agent.state import Attempt, Event, RunReport, TestResult
from app.config import Settings
from app.db.models import EvalResultRow, RunRow
from app.main import create_app
from fastapi.testclient import TestClient
from pydantic import SecretStr

TOKEN = "test-only-worker-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        runner_mode="replay",
        database_url=SecretStr(f"sqlite:///{tmp_path}/db.sqlite"),
        database_auto_create=True,
        api_access_token=SecretStr(TOKEN),
        work_root=tmp_path / "work",
        requests_per_minute=100,
    )
    with TestClient(create_app(settings)) as app:
        yield app


def reviewed(client: TestClient, run_id: str = "test-run", dry: bool = True) -> str:
    diff = "--- a/module.py\n+++ b/module.py\n@@ -1 +1 @@\n-old\n+new\n"
    report = RunReport(
        id=run_id,
        repo_url="https://github.com/owner/repo",
        issue_text="Fix a real bug",
        status="ready_for_review",
        final_diff=diff,
        commit_sha="a" * 40,
        review="Small patch. Review edge cases.",
        attempts=[
            Attempt(
                attempt_no=1,
                patch=diff,
                test_result=TestResult(exit_code=0, outcomes={"test_a": "passed"}),
            )
        ],
    )
    with client.app.state.sessions.begin() as db:
        db.add(
            RunRow(
                id=run_id,
                repo_url=report.repo_url,
                issue_text=report.issue_text,
                status="ready_for_review",
                dry_run=dry,
                final_diff=diff,
                report=report.model_dump(mode="json"),
                source_snapshot={"module.py": "new\n"},
            )
        )
    return hashlib.sha256(diff.encode()).hexdigest()


def test_protected_endpoints_require_token(client: TestClient) -> None:
    assert client.get("/api/runs").status_code == 401
    assert client.get("/api/eval").status_code == 401
    assert client.get("/api/runs", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/runs", headers=HEADERS).json() == []


def test_health_is_honest_when_worker_missing(client: TestClient) -> None:
    health = client.get("/api/health").json()
    assert health["database"] is True
    assert health["runner"] == "replay" and health["runner_healthy"] is True
    assert health["ready"] is True


def test_eval_catalog_has_no_fabricated_results(client: TestClient) -> None:
    data = client.get("/api/eval", headers=HEADERS).json()
    assert data["total_cases"] == 25 and len(data["results"]) == 25
    assert data["executed"] == 0 and data["success_rate"] is None
    assert all(c["status"] == "not_run" for c in data["results"])


def test_approval_is_bound_to_exact_diff_and_is_one_shot(client: TestClient) -> None:
    digest = reviewed(client)
    assert (
        client.post(
            "/api/runs/test-run/approve", headers=HEADERS, json={"diff_sha256": "0" * 64}
        ).status_code
        == 409
    )
    with patch("app.service.publish_reviewed_patch") as publish:
        response = client.post(
            "/api/runs/test-run/approve", headers=HEADERS, json={"diff_sha256": digest}
        )
        assert response.status_code == 200
        publish.assert_not_called()  # dry-run approval cannot publish
    assert client.get("/api/runs/test-run", headers=HEADERS).json()["status"] == "completed"
    assert (
        client.post(
            "/api/runs/test-run/approve", headers=HEADERS, json={"diff_sha256": digest}
        ).status_code
        == 200
    )


def test_rejection_prevents_later_publication(client: TestClient) -> None:
    digest = reviewed(client)
    assert client.post("/api/runs/test-run/reject", headers=HEADERS).status_code == 200
    assert (
        client.post(
            "/api/runs/test-run/approve", headers=HEADERS, json={"diff_sha256": digest}
        ).status_code
        == 409
    )
    with client.app.state.sessions() as db:
        assert db.get(RunRow, "test-run").source_snapshot == {}


def test_live_approval_needs_github_key(client: TestClient) -> None:
    digest = reviewed(client, dry=False)
    assert (
        client.post(
            "/api/runs/test-run/approve", headers=HEADERS, json={"diff_sha256": digest}
        ).status_code
        == 409
    )
    assert client.get("/api/runs/test-run", headers=HEADERS).json()["status"] == "ready_for_review"


def test_sse_resumes_without_duplicates(client: TestClient) -> None:
    reviewed(client)
    service = client.app.state.service
    service.add_event("test-run", Event(node="clone", type="start", message="one"))
    service.add_event("test-run", Event(node="clone", type="end", message="two"))
    response = client.get("/api/runs/test-run/events", headers=HEADERS)
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"message": "one"' in response.text and '"message": "two"' in response.text
    response = client.get("/api/runs/test-run/events", headers={**HEADERS, "Last-Event-ID": "1"})
    assert '"message": "one"' not in response.text and '"message": "two"' in response.text
    assert (
        client.get(
            "/api/runs/test-run/events", headers={**HEADERS, "Last-Event-ID": "bad"}
        ).status_code
        == 400
    )


def test_events_redact_tokens_before_storage(client: TestClient) -> None:
    reviewed(client)
    client.app.state.service.add_event(
        "test-run", Event(node="worker", type="error", message=TOKEN)
    )
    response = client.get("/api/runs/test-run", headers=HEADERS)
    assert TOKEN not in response.text and "REDACTED" in response.text


def test_non_github_input_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/runs",
        headers=HEADERS,
        json={"repo_url": "file:///private", "issue_text": "Fix the bug please"},
    )
    assert response.status_code == 422


def test_missing_groq_does_not_start_fake_run(client: TestClient) -> None:
    response = client.post(
        "/api/runs",
        headers=HEADERS,
        json={"repo_url": "https://github.com/owner/repo", "issue_text": "Fix the bug please"},
    )
    assert response.status_code == 503
    assert client.get("/api/runs", headers=HEADERS).json() == []


def test_large_bodies_rejected_before_parsing(client: TestClient) -> None:
    assert client.post("/api/runs", headers=HEADERS, content=b"x" * 65000).status_code == 413


def test_eval_counts_failures_in_denominator(client: TestClient) -> None:
    reviewed(client, "eval-one")
    reviewed(client, "eval-two")
    with client.app.state.sessions.begin() as db:
        db.add(
            EvalResultRow(
                case_id="case-01",
                run_id="eval-one",
                result="passed",
                attempts=1,
                duration_seconds=10,
            )
        )
        db.add(
            EvalResultRow(
                case_id="case-02",
                run_id="eval-two",
                result="failed",
                attempts=3,
                duration_seconds=30,
            )
        )
    result = client.get("/api/eval", headers=HEADERS).json()
    assert result["executed"] == 2 and result["failed"] == 1 and result["success_rate"] == 50
    assert result["average_attempts"] == 2


def test_restart_preserves_approval_wait(client: TestClient) -> None:
    reviewed(client)
    with patch.object(client.app.state.service.executor, "submit") as submit:
        client.app.state.service.recover_interrupted()
        submit.assert_not_called()
    run = client.get("/api/runs/test-run", headers=HEADERS).json()
    assert run["status"] == "ready_for_review" and run["review"]


def test_publication_uses_only_target_token(client: TestClient):
    from pydantic import SecretStr

    digest = reviewed(client, dry=False)
    service = client.app.state.service
    service.settings.target_github_token = SecretStr("fake-target-scoped")
    service.settings.sandbox_github_token = SecretStr("fake-sandbox-scoped")
    with client.app.state.sessions.begin() as db:
        row = db.get(RunRow, "test-run")
        row.status, row.approved_diff_sha256 = "publishing", digest
    with (
        patch("app.service.GitHubClient") as github,
        patch(
            "app.service.publish_reviewed_patch",
            return_value="https://github.com/owner/repo/pull/1",
        ),
    ):
        service.publish("test-run")
        github.assert_called_once_with("fake-target-scoped")


def test_lightweight_health_does_not_call_runner(client: TestClient):
    with patch("app.api.health.make_runner") as factory:
        assert client.get("/api/health?lightweight=true").json() == {"status": "awake"}
        factory.assert_not_called()


def test_retried_run_request_returns_one_durable_job(client: TestClient):
    service = client.app.state.service
    service.settings.groq_api_key = SecretStr("fake-groq-key-for-controller-test")
    payload = {"repo_url": "https://github.com/owner/repo", "issue_text": "Repair this bug"}
    headers = {**HEADERS, "Idempotency-Key": "a" * 32}
    with (
        patch("app.service.RunPolicy.readiness", return_value="https://github.com/owner/repo.git"),
        patch.object(service.executor, "submit") as submit,
    ):
        first = client.post("/api/runs", headers=headers, json=payload)
        second = client.post("/api/runs", headers=headers, json=payload)
        assert first.status_code == second.status_code == 202
        assert first.json()["id"] == second.json()["id"]
        submit.assert_called_once()
        different = client.post(
            "/api/runs", headers=headers, json={**payload, "issue_text": "A different bug"}
        )
        assert different.status_code == 409
