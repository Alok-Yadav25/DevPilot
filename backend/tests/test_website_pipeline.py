"""API-to-Actions integration with mocked provider HTTP; no live-service claim."""

import base64
import io
import json
import time
import zipfile
from unittest.mock import patch

import httpx
from app.config import Settings
from app.main import create_app
from app.sandbox.github_actions import GitHubActionsRunner
from conftest import CASES, FixtureCloner, ScriptedLLM
from fastapi.testclient import TestClient
from git import Repo


def test_website_run_uses_actions_transport_and_stops_for_approval(tmp_path):
    case = CASES[0]

    class PublicCloner(FixtureCloner):
        def clone(self, url, destination):
            sha = super().clone(url, destination)
            with Repo(destination) as repo:
                repo.create_remote("origin", url)
            return sha

    class Model(ScriptedLLM):
        limits = {}

        def preflight(self):
            pass

        def close(self):
            pass

    calls, patches, jobs = [], {}, {}

    def handler(req):
        calls.append(req)
        path = req.url.path
        if path.endswith("/target") or path.endswith("/sandbox"):
            return httpx.Response(200, json={"private": False})
        if path.endswith("/run-tests.yml"):
            return httpx.Response(200, json={"state": "active"})
        if "/git/ref/" in path:
            return httpx.Response(200, json={"object": {"sha": "a" * 40}})
        if req.method == "PUT":
            data = json.loads(req.content)
            patches[data["branch"]] = base64.b64decode(data["content"]).decode()
            return httpx.Response(201, json={})
        if path.endswith("dispatches"):
            data = json.loads(req.content)
            number = len(jobs) + 1
            jobs[number] = patches[data["ref"]]
            return httpx.Response(200, json={"workflow_run_id": number})
        if path.endswith("/artifacts"):
            number = int(path.split("/")[-2])
            return httpx.Response(200, json={"artifacts": [{"id": number, "name": "results"}]})
        if path.endswith("/zip"):
            number = int(path.split("/")[-2])
            result = case.success() if jobs[number] else case.baseline()
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w") as archive:
                archive.writestr(
                    "results.json", json.dumps({"applied": True, **result.model_dump()})
                )
                archive.writestr("pytest.log", result.output_tail)
                archive.writestr("install.log", "")
            return httpx.Response(200, content=out.getvalue())
        if "/actions/runs/" in path:
            return httpx.Response(200, json={"status": "completed", "conclusion": "success"})
        return httpx.Response(204)

    def transport(*args, **kwargs):
        return GitHubActionsRunner(
            *args,
            **kwargs,
            client=httpx.AsyncClient(
                base_url="https://api.github.com/", transport=httpx.MockTransport(handler)
            ),
        )

    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/db",
        database_auto_create=True,
        work_root=tmp_path / "work",
        sandbox_repo="owner/sandbox",
        allowed_target_repos="owner/target",
        sandbox_github_token="fake-sandbox",
        target_github_token="fake-target",
        groq_api_key="fake-groq",
        api_access_token="fake-api",
    )
    headers = {"Authorization": "Bearer fake-api"}
    with (
        patch(
            "app.service.RunPolicy.readiness", return_value="https://github.com/owner/target.git"
        ),
        patch("app.policy.RunPolicy.remote", return_value="https://github.com/owner/target.git"),
        patch("app.agent.graph.Cloner", return_value=PublicCloner()),
        patch("app.service.GroqClient", return_value=Model([case.proposal()])),
        patch("app.sandbox.github_actions.GitHubActionsRunner", side_effect=transport),
        patch("app.service.GitHubClient") as publication,TestClient(create_app(settings)) as client
    ):
        response = client.post(
            "/api/runs",
            headers=headers,
            json={"repo_url": "https://github.com/owner/target", "issue_text": case.issue},
        )
        assert response.status_code == 202, response.text
        run_id = response.json()["id"]
        for _ in range(100):
            run = client.get(f"/api/runs/{run_id}", headers=headers).json()
            if run["status"] not in {"queued", "running"}:
                break
            time.sleep(0.05)
        assert run["status"] == "ready_for_review", run.get("reason")
        assert run["final_diff"] and len(run["test_evidence"]) == 3
        assert len(jobs) == 3 and sum(bool(p) for p in jobs.values()) == 1
        assert client.get("/api/replays").json()[0]["id"] == run_id
        publication.assert_not_called()
    assert not any(c.method == "POST" and c.url.path.endswith("/pulls") for c in calls)
