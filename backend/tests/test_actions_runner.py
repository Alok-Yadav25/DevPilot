import asyncio
import io
import json
import zipfile

import httpx
import pytest
from app.errors import DevPilotError, RunTimeout
from app.sandbox.github_actions import GitHubActionsRunner, parse_artifact, repository
from app.security import Redactor


def artifact() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "results.json",
            json.dumps(
                {"applied": True, "exit_code": 0, "outcomes": {"tests/test_x.py::test_x": "passed"}}
            ),
        )
        archive.writestr("pytest.log", "sensitive-key\n" + "x" * 5000)
        archive.writestr("install.log", "")
    return output.getvalue()


def runner(handler) -> GitHubActionsRunner:
    return GitHubActionsRunner(
        "owner/devpilot-sandbox",
        "test-token",
        {"owner/target"},
        Redactor(["sensitive-key"]),
        lambda _: None,
        client=httpx.AsyncClient(
            base_url="https://api.github.com/", transport=httpx.MockTransport(handler)
        ),
    )


def test_permission_failure_names_operation_without_response_secrets():
    async def exercise():
        r = runner(lambda request: httpx.Response(403, json={"message": "sensitive-key"}))
        try:
            await r.preflight()
        except DevPilotError as exc:
            message = str(exc)
            assert "GET repos/owner/devpilot-sandbox" in message
            assert "Contents/Actions write" in message
            assert "sensitive-key" not in message
        else:
            pytest.fail("A denied sandbox request must fail")
        finally:
            await r.close()

    asyncio.run(exercise())


def test_dispatch_empty_baseline_and_cleanup() -> None:
    calls = []

    def handler(request):
        calls.append(request)
        p = request.url.path
        if p == "/repos/owner/target":
            return httpx.Response(200, json={"private": False})
        if "/git/ref/" in p:
            return httpx.Response(200, json={"object": {"sha": "a" * 40}})
        if p.endswith("dispatches"):
            assert "return_run_details" not in json.loads(request.content)
            return httpx.Response(200, json={"workflow_run_id": 42})
        if p.endswith("/runs/42"):
            return httpx.Response(200, json={"status": "completed", "conclusion": "success"})
        if p.endswith("/artifacts"):
            return httpx.Response(200, json={"artifacts": [{"id": 9, "name": "results"}]})
        if p.endswith("/zip"):
            return httpx.Response(200, content=artifact())
        return httpx.Response(204)

    async def exercise():
        r = runner(handler)
        try:
            result = await r.run_tests("baseline-1", "owner/target", "a" * 40, "")
            assert result.passed and len(result.output_tail) == 4000
        finally:
            await r.close()

    asyncio.run(exercise())
    patch = next(c for c in calls if c.method == "PUT")
    assert json.loads(patch.content)["content"] == ""
    assert calls[-1].method == "DELETE"
    assert all("devpilot-sandbox" in c.url.path for c in calls if c.method != "GET")


@pytest.mark.parametrize(
    "repo", ["https://evil.test/x/y", "owner/x;id", "../repo", "owner/-bad", "owner/repo extra"]
)
def test_repo_validation(repo):
    with pytest.raises(DevPilotError):
        repository(repo)


def test_allowlist_and_immutable_commit_before_network():
    def forbidden(request):
        raise AssertionError("No request expected")

    async def exercise():
        r = runner(forbidden)
        try:
            for target, ref in [("stranger/repo", "a" * 40), ("owner/target", "main")]:
                with pytest.raises(DevPilotError):
                    await r.run_tests("job", target, ref, "")
        finally:
            await r.close()

    asyncio.run(exercise())


def test_missing_artifact_retries_once_and_deletes_branch():
    calls = []

    def handler(req):
        calls.append(req)
        path = req.url.path
        if path == "/repos/owner/target":
            return httpx.Response(200, json={"private": False})
        if "/git/ref/" in path:
            return httpx.Response(200, json={"object": {"sha": "a" * 40}})
        if path.endswith("dispatches"):
            return httpx.Response(200, json={"workflow_run_id": 1})
        if path.endswith("/runs/1"):
            return httpx.Response(200, json={"status": "completed", "conclusion": "success"})
        if path.endswith("artifacts"):
            return httpx.Response(200, json={"artifacts": []})
        return httpx.Response(204)

    async def exercise():
        r = runner(handler)

        async def no_wait(seconds):
            pass

        r.pause = no_wait
        try:
            with pytest.raises(DevPilotError, match="artifact missing"):
                await r.run_tests("job", "owner/target", "a" * 40, "")
        finally:
            await r.close()

    asyncio.run(exercise())
    assert sum(c.url.path.endswith("artifacts") for c in calls) == 2
    assert calls[-1].method == "DELETE"


def test_timeout_cancels_job_and_removes_branch():
    calls = []

    def handler(req):
        calls.append(req)
        path = req.url.path
        if path == "/repos/owner/target":
            return httpx.Response(200, json={"private": False})
        if "/git/ref/" in path:
            return httpx.Response(200, json={"object": {"sha": "a" * 40}})
        if path.endswith("dispatches"):
            return httpx.Response(200, json={"workflow_run_id": 1})
        if path.endswith("/runs/1"):
            return httpx.Response(200, json={"status": "queued"})
        return httpx.Response(204)

    async def exercise():
        r = runner(handler)

        async def expire(seconds):
            raise RunTimeout("expired")

        r.pause = expire
        try:
            with pytest.raises(RunTimeout):
                await r.run_tests("job", "owner/target", "a" * 40, "")
        finally:
            await r.close()

    asyncio.run(exercise())
    assert calls[-2].url.path.endswith("/cancel") and calls[-1].method == "DELETE"


def test_corrupt_artifact_fails_closed():
    with pytest.raises(DevPilotError, match="Invalid sandbox artifact"):
        parse_artifact(b"bad zip", Redactor())


def test_private_target_is_rejected_before_branch_creation():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json={"private": True})

    async def exercise():
        r = runner(handler)
        try:
            with pytest.raises(DevPilotError, match="public target"):
                await r.run_tests("job", "owner/target", "a" * 40, "")
        finally:
            await r.close()

    asyncio.run(exercise())
    assert len(calls) == 1 and calls[0].method == "GET"


def test_rate_limit_backoff_is_bounded_and_observable():
    notices = []
    calls = 0

    def handler(req):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"retry-after": "1"})
        return httpx.Response(200, json={"private": False})

    async def exercise():
        import time

        r = runner(handler)
        r.waiting = notices.append
        r.deadline = time.monotonic() + 10

        async def no_wait(seconds):
            pass

        r.pause = no_wait
        try:
            await r.request("GET", "repos/owner/devpilot-sandbox")
        finally:
            await r.close()

    asyncio.run(exercise())
    assert calls == 2 and notices


def test_workflow_has_no_credential_or_host_mount_pass_through():
    from pathlib import Path

    workflow = Path("sandbox-repo/.github/workflows/run-tests.yml").read_text()
    assert "persist-credentials: false" in workflow
    assert "contents: read" in workflow and "secrets." not in workflow
    assert "--cap-drop=ALL" in workflow and "--read-only" in workflow
    assert "--volume" not in workflow and "docker.sock" not in workflow
    assert "retention-days: 1" in workflow and "ubuntu-latest" in workflow


def test_restart_reattaches_to_remote_job_without_dispatch():
    import hashlib
    from datetime import UTC, datetime

    calls = []

    def handler(req):
        calls.append(req)
        if req.url.path == "/repos/owner/target":
            return httpx.Response(200, json={"private": False})
        if req.url.path.endswith("/runs/42"):
            return httpx.Response(200, json={"status": "completed", "conclusion": "success"})
        if req.url.path.endswith("artifacts"):
            return httpx.Response(200, json={"artifacts": [{"id": 9, "name": "results"}]})
        if req.url.path.endswith("/zip"):
            return httpx.Response(200, content=artifact())
        return httpx.Response(204)

    async def exercise():
        r = runner(handler)
        r.jobs["job"] = {
            "signature": hashlib.sha256(f"owner/target@{'a' * 40}\n".encode()).hexdigest(),
            "started_at": datetime.now(UTC).isoformat(),
            "run_id": 42,
            "branch_created": True,
        }
        try:
            assert (await r.run_tests("job", "owner/target", "a" * 40, "")).passed
            assert r.jobs["job"]["result"]
        finally:
            await r.close()

    asyncio.run(exercise())
    assert not any(c.method in {"POST", "PUT"} for c in calls)


def test_generated_workflow_disconnects_before_pytest_and_is_reproducible():
    import subprocess
    from pathlib import Path

    path = Path("sandbox-repo/.github/workflows/run-tests.yml")
    before = path.read_text()
    subprocess.run(
        [__import__("sys").executable, "scripts/build_actions_workflow.py"],
        check=True,
        capture_output=True,
    )
    assert path.read_text() == before
    assert "'network', 'disconnect', 'bridge'" in before
    assert "networks != '{}'" in before
    assert "deadline = time.monotonic() + 120" in before
    assert before.index('print("DEVPILOT_TEST_READY"') < before.index("import pytest")
    assert 'if sys.stdin.buffer.readline(64) != b"continue' in before
