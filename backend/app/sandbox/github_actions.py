"""A bounded GitHub Actions transport. No target-repository writes occur here."""

import asyncio
import base64
import hashlib
import io
import json
import re
import threading
import time
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from app.agent.state import TestResult
from app.errors import DevPilotError, RunCancelled, RunTimeout, WorkerPaused
from app.security import Redactor

REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*")


def repository(value: str) -> str:
    if not REPO.fullmatch(value) or any(p in {".", ".."} for p in value.split("/")):
        raise DevPilotError("Use a GitHub owner/repository name without a URL or shell syntax.")
    return value


class GitHubActionsRunner:
    def __init__(
        self,
        sandbox_repo: str,
        token: str,
        allowed: set[str],
        redactor: Redactor,
        waiting: Callable[[str], None],
        timeout: float = 900,
        default_branch: str = "main",
        cancel: threading.Event | None = None,
        client: httpx.AsyncClient | None = None,
        allowed_owner: str = "",
    ) -> None:
        self.repo = repository(sandbox_repo)
        self.allowed = {repository(r).lower() for r in allowed}
        self.allowed_owner = allowed_owner.lower()
        if self.allowed_owner and not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,38}", self.allowed_owner):
            raise DevPilotError("Invalid ALLOWED_TARGET_OWNER.")
        if not token or not (self.allowed or self.allowed_owner):
            raise DevPilotError("Set SANDBOX_GITHUB_TOKEN and ALLOWED_TARGET_REPOS first.")
        self.redact, self.waiting, self.timeout = redactor, waiting, timeout
        self.default_branch = default_branch
        self.cancel = cancel or threading.Event()
        self.client = client or httpx.AsyncClient(
            base_url="https://api.github.com/",
            follow_redirects=False,
            timeout=30,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
        )
        self.limits: dict[str, str] = {}
        self.deadline = 0.0
        self.pause_requested = threading.Event()
        self.jobs: dict[str, dict] = {}
        self.on_job: Callable[[str, dict], None] = lambda job_id, job: None

    async def close(self) -> None:
        await self.client.aclose()

    def check(self) -> float:
        if self.pause_requested.is_set():
            raise WorkerPaused("Worker paused; remote job preserved for recovery.")
        if self.cancel.is_set():
            raise RunCancelled("GitHub sandbox cancelled by the operator.")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RunTimeout("GitHub Actions sandbox exceeded its queue/run time budget.")
        return remaining

    async def pause(self, seconds: float) -> None:
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            await asyncio.sleep(min(0.25, max(0, until - time.monotonic()), self.check()))

    async def request(
        self, method: str, path: str, body: dict | None = None, missing_ok: bool = False
    ) -> httpx.Response:
        for attempt in range(4):
            try:
                response = await self.client.request(
                    method, path, json=body, timeout=min(30, self.check())
                )
            except httpx.HTTPError as exc:
                # Never blindly retry mutations: the server may already have accepted them.
                raise DevPilotError(
                    "GitHub request failed; inspect Actions before retrying."
                ) from exc
            self.limits = {
                k: v for k, v in response.headers.items() if k.startswith("x-ratelimit-")
            }
            throttled = response.status_code == 429 or (
                response.status_code == 403
                and (
                    response.headers.get("x-ratelimit-remaining") == "0"
                    or "retry-after" in response.headers
                )
            )
            if throttled and attempt < 3:
                try:
                    delay = float(response.headers.get("retry-after", str(2**attempt)))
                except ValueError:
                    delay = 2**attempt
                delay = max(1, delay)
                if delay >= self.check():
                    raise RunTimeout("GitHub rate limit reset exceeds the sandbox budget.")
                self.waiting(f"GitHub rate limited; waiting {delay:.0f}s.")
                await self.pause(delay)
                continue
            if response.status_code == 404 and missing_ok:
                return response
            if response.status_code >= 400:
                raise DevPilotError(
                    f"GitHub sandbox HTTP {response.status_code}; "
                    "check permissions, workflow and quotas."
                )
            return response
        raise DevPilotError("GitHub sandbox request budget exhausted.")

    async def preflight(self) -> None:
        self.deadline = time.monotonic() + 30
        info = (await self.request("GET", f"repos/{self.repo}")).json()
        if info.get("private", True):
            raise DevPilotError("The sandbox repository must be public for the free-hosting plan.")
        await self.request("GET", f"repos/{self.repo}/actions/workflows/run-tests.yml")

    async def run_tests(self, job_id: str, target_repo: str, ref: str, diff: str) -> TestResult:
        repository(target_repo)
        if (
            target_repo.lower() not in self.allowed
            and target_repo.split("/")[0].lower() != self.allowed_owner
        ):
            raise DevPilotError("Repository is not in ALLOWED_TARGET_REPOS.")
        if not re.fullmatch(r"[a-f0-9]{40}", ref):
            raise DevPilotError("Sandbox runs require the immutable cloned commit SHA.")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", job_id):
            raise DevPilotError("Invalid sandbox job ID.")
        if len(diff.encode()) > 48000 or self.redact.contains_secret(diff):
            raise DevPilotError("Patch is oversized or contains secret-like content.")
        existing = dict(self.jobs.get(job_id, {}))
        signature = hashlib.sha256(f"{target_repo}@{ref}\n{diff}".encode()).hexdigest()
        if existing and existing.get("signature") != signature:
            raise DevPilotError("Stored sandbox job does not match the pinned repo and patch.")
        if existing.get("result"):
            return TestResult.model_validate(existing["result"])
        job = existing or {"signature": signature, "started_at": datetime.now(UTC).isoformat()}

        def save(**changes: object) -> None:
            job.update(changes)
            self.jobs[job_id] = dict(job)
            self.on_job(job_id, dict(job))

        save()
        elapsed = (datetime.now(UTC) - datetime.fromisoformat(job["started_at"])).total_seconds()
        self.deadline = time.monotonic() + self.timeout - elapsed
        root, branch = f"repos/{self.repo}", f"patch/{job_id}"
        created, run_id, completed = bool(job.get("branch_created")), job.get("run_id"), False
        started = time.monotonic()
        preserve = False
        try:
            info = (await self.request("GET", f"repos/{target_repo}")).json()
            if info.get("private", True):
                raise DevPilotError("Only public target repositories are supported.")
            if not run_id and job.get("dispatch_intent"):
                # A lost response is ambiguous. Reconcile by stable run-name; never redispatch.
                for _retry in range(3):
                    runs = (
                        (
                            await self.request(
                                "GET",
                                f"{root}/actions/workflows/run-tests.yml/runs?branch={branch}&event=workflow_dispatch&per_page=100",
                            )
                        )
                        .json()
                        .get("workflow_runs", [])
                    )
                    match = next(
                        (r for r in runs if r.get("display_title") == f"run-tests {job_id}"), None
                    )
                    if match:
                        run_id = int(match["id"])
                        save(run_id=run_id, status=match["status"])
                        break
                    await self.pause(3)
                if not run_id:
                    raise DevPilotError(
                        "Dispatch outcome is uncertain. Inspect Actions before retrying. "
                        "No duplicate was dispatched."
                    )
            if not run_id:
                if not created:
                    base = (
                        await self.request("GET", f"{root}/git/ref/heads/{self.default_branch}")
                    ).json()["object"]["sha"]
                    if existing:
                        found = await self.request(
                            "GET", f"{root}/git/ref/heads/{branch}", missing_ok=True
                        )
                        created = found.status_code == 200
                    if not created:
                        await self.request(
                            "POST", f"{root}/git/refs", {"ref": f"refs/heads/{branch}", "sha": base}
                        )
                        created = True
                    save(branch_created=True)
                if not job.get("patch_uploaded"):
                    body = {
                        "message": f"sandbox {job_id}",
                        "branch": branch,
                        "content": base64.b64encode(diff.encode()).decode(),
                    }
                    if existing:
                        prior = await self.request(
                            "GET", f"{root}/contents/patch.diff?ref={branch}", missing_ok=True
                        )
                        if prior.status_code == 200:
                            content = prior.json()
                            if base64.b64decode(content["content"]).decode() == diff:
                                save(patch_uploaded=True)
                            else:
                                raise DevPilotError(
                                    "Existing sandbox branch patch differs. Inspect it manually."
                                )
                    if not job.get("patch_uploaded"):
                        await self.request("PUT", f"{root}/contents/patch.diff", body)
                        save(patch_uploaded=True)
                save(dispatch_intent=True)
                dispatch = await self.request(
                    "POST",
                    f"{root}/actions/workflows/run-tests.yml/dispatches",
                    {
                        "ref": branch,
                        "return_run_details": True,
                        "inputs": {"job_id": job_id, "target_repo": target_repo, "target_ref": ref},
                    },
                )
                try:
                    run_id = int(dispatch.json()["workflow_run_id"])
                except (ValueError, KeyError, TypeError) as exc:
                    raise DevPilotError(
                        "No dispatch run ID; inspect Actions before retrying."
                    ) from exc
                save(run_id=run_id, status="queued")
            while True:
                run = (await self.request("GET", f"{root}/actions/runs/{run_id}")).json()
                save(run_id=run_id, status=run["status"])
                if run["status"] == "completed":
                    completed = True
                    if run.get("conclusion") != "success":
                        raise DevPilotError(
                            f"Workflow finished as {run.get('conclusion', 'unknown')}; "
                            "inspect Actions."
                        )
                    break
                self.waiting(
                    f"Waiting for GitHub runner: {run['status']} "
                    f"({int(time.monotonic() - started)}s)."
                )
                await self.pause(6)
            artifact = None
            for retry in range(2):
                entries = (
                    await self.request("GET", f"{root}/actions/runs/{run_id}/artifacts")
                ).json()["artifacts"]
                artifact = next(
                    (a for a in entries if a["name"] == "results" and not a.get("expired")), None
                )
                if artifact:
                    break
                if retry == 0:
                    self.waiting("Results artifact not visible yet; retrying once.")
                    await self.pause(5)
            if not artifact:
                raise DevPilotError(
                    "Results artifact missing; the workflow may have failed during setup."
                )
            result = await self.download(f"{root}/actions/artifacts/{int(artifact['id'])}/zip")
            result.duration_seconds = round(time.monotonic() - started, 3)
            save(result=result.model_dump(mode="json"), status="completed")
            return result
        except WorkerPaused:
            preserve = True
            raise
        except (KeyError, ValueError, TypeError, httpx.HTTPError) as exc:
            raise DevPilotError(
                "Invalid GitHub sandbox response; inspect the workflow and artifact."
            ) from exc
        finally:
            # Cleanup has its own short budget; do not let cancellation skip it.
            async def cleanup(method: str, path: str) -> None:
                try:
                    response = await self.client.request(method, path, timeout=10)
                    if response.status_code not in {202, 204, 404}:
                        self.waiting("Sandbox cleanup needs attention in GitHub Actions.")
                except httpx.HTTPError:
                    self.waiting(
                        "Sandbox cleanup could not reach GitHub; remove the patch branch manually."
                    )

            if run_id and not completed and not self.pause_requested.is_set() and not preserve:
                await cleanup("POST", f"{root}/actions/runs/{run_id}/cancel")
            if created and not self.pause_requested.is_set() and not preserve:
                await cleanup("DELETE", f"{root}/git/refs/heads/{branch}")

    async def cancel_pending(self) -> None:
        for job_id, job in self.jobs.items():
            if job.get("run_id") and not job.get("result"):
                response = await self.client.post(
                    f"repos/{self.repo}/actions/runs/{int(job['run_id'])}/cancel"
                )
                if response.status_code not in {202, 409, 404}:
                    raise DevPilotError(
                        "Remote cancellation failed. Cancel the Actions run manually."
                    )
            if job.get("branch_created") and re.fullmatch(r"[A-Za-z0-9-]{1,64}", job_id):
                response = await self.client.delete(
                    f"repos/{self.repo}/git/refs/heads/patch/{job_id}"
                )
                if response.status_code not in {204, 404}:
                    raise DevPilotError(
                        "Patch branch cleanup failed. Delete the sandbox branch manually."
                    )

    async def download(self, path: str) -> TestResult:
        response = await self.request("GET", path)
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location", "")
            url = urlsplit(location)
            if url.scheme != "https" or url.username or url.password or not url.hostname:
                raise DevPilotError("Invalid artifact redirect.")
            # Separate client: never forward the GitHub bearer token to artifact storage.
            async with (
                httpx.AsyncClient(timeout=min(30, self.check())) as public,
                public.stream("GET", location) as stream,
            ):
                stream.raise_for_status()
                data = bytearray()
                async for chunk in stream.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        raise DevPilotError("Artifact exceeds the 2 MB download limit.")
            content = bytes(data)
        else:
            content = response.content
        return parse_artifact(content, self.redact)


def parse_artifact(content: bytes, redact: Redactor) -> TestResult:
    try:
        if len(content) > 2_000_000:
            raise ValueError("oversized archive")
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if (
                len(archive.infolist()) > 10
                or sum(f.file_size for f in archive.infolist()) > 2_000_000
            ):
                raise ValueError("oversized expanded archive")
            data = json.loads(archive.read("results.json"))
            log = archive.read("pytest.log").decode(errors="replace")[-4000:]
            install = archive.read("install.log").decode(errors="replace")[-4000:]
        if not isinstance(data, dict) or data.get("applied") is not True:
            raise ValueError("patch was not applied")
        result = TestResult.model_validate(data)
        result.output_tail = redact(log or install)[-4000:]
        return TestResult.model_validate_json(redact(result.model_dump_json()))
    except (ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise DevPilotError(
            "Invalid sandbox artifact: require results.json, pytest.log and install.log."
        ) from exc
