"""Opt-in real API driver. Writes evidence; never substitutes mocked outcomes."""

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from app.config import Settings
from app.security import Redactor


def verify(base: str, repo: str, issue: str, decision: str = "none", timeout: int = 1800) -> dict:
    settings = Settings()
    if os.environ.get("GROQ_KEY_ROTATION_CONFIRMED") != "1":
        raise RuntimeError("Set GROQ_KEY_ROTATION_CONFIRMED=1 only after revoking the old key.")
    if not settings.api_access_token.get_secret_value():
        raise RuntimeError("Configure API_ACCESS_TOKEN in the local environment first.")
    started = time.monotonic()
    with httpx.Client(
        base_url=base.rstrip("/") + "/",
        timeout=120,
        headers={"Authorization": "Bearer " + settings.api_access_token.get_secret_value()},
    ) as client:
        response = client.post(
            "api/runs",
            headers={"Idempotency-Key": uuid4().hex},
            json={"repo_url": repo, "issue_text": issue, "dry_run": decision != "draft_pr"},
        )
        response.raise_for_status()
        run_id = response.json()["id"]
        decided = False
        while time.monotonic() - started < timeout:
            response = client.get(f"api/runs/{run_id}")
            response.raise_for_status()
            run = response.json()
            status = run["status"]
            if decision == "cancel" and status in {"queued", "running"} and not decided:
                client.post(f"api/runs/{run_id}/cancel", json={}).raise_for_status()
                decided = True
            if status == "ready_for_review":
                if decision == "none":
                    break
                if not decided and decision in {"approve_dry", "draft_pr", "reject"}:
                    action = "reject" if decision == "reject" else "approve"
                    data = (
                        {"diff_sha256": hashlib.sha256(run["final_diff"].encode()).hexdigest()}
                        if action == "approve"
                        else {}
                    )
                    client.post(f"api/runs/{run_id}/{action}", json=data).raise_for_status()
                    decided = True
            elif status not in {"queued", "running", "publishing"}:
                break
            time.sleep(3)
        else:
            raise TimeoutError(
                f"Verification timed out. Inspect run {run_id}; it was not cancelled."
            )
        evidence = {
            "observed_at": datetime.now(UTC).isoformat(),
            "duration_seconds": round(time.monotonic() - started, 2),
            "driver": "real_api_no_mocks",
            "decision": decision,
            "run": run,
        }
        return json.loads(Redactor(settings.secrets())(json.dumps(evidence)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument(
        "--decision",
        choices=["none", "approve_dry", "draft_pr", "reject", "cancel"],
        default="none",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = verify(args.api, args.repo, args.issue, args.decision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        json.dumps(
            {
                "run_id": evidence["run"]["id"],
                "status": evidence["run"]["status"],
                "evidence": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
