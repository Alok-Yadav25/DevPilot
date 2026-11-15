"""Run published evaluation cases through the real website/API pipeline, without approval or PRs."""

import argparse
import json
import re
from pathlib import Path

from app.agent.state import TestResult
from app.config import Settings
from app.db.models import EvalCaseRow, EvalResultRow, RunRow
from app.db.session import make_engine, make_sessions
from app.evaluation import catalog, seed_catalog
from app.policy import RunPolicy
from verify_live import verify


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--case", choices=[c["id"] for c in catalog()])
    parser.add_argument("--output", type=Path, default=Path(".devpilot/evaluation-results.json"))
    args = parser.parse_args()
    settings = Settings()
    entries = json.loads(args.manifest.read_text())
    definitions = {c["id"]: c for c in catalog()}
    seen = set()
    for entry in entries:
        if entry["case_id"] not in definitions or entry["case_id"] in seen:
            parser.error("Manifest contains an unknown or duplicate case ID.")
        seen.add(entry["case_id"])
        RunPolicy(settings).request(
            entry["repo_url"], definitions[entry["case_id"]]["bug_description"]
        )
        if not re.fullmatch(r"[a-f0-9]{40}", entry["expected_commit_sha"]):
            parser.error("Every case requires its published immutable commit SHA.")
    engine = make_engine(settings)
    sessions = make_sessions(engine)
    observations = []
    try:
        with sessions.begin() as db:
            seed_catalog(db)
        for entry in entries:
            if args.case and entry["case_id"] != args.case:
                continue
            case = definitions[entry["case_id"]]
            observation = verify(args.api, entry["repo_url"], case["bug_description"])
            run = observation["run"]
            result = run.get("attempts", [])[-1].get("test_result") if run.get("attempts") else None
            passed = (
                run["status"] == "ready_for_review"
                and run.get("commit_sha") == entry["expected_commit_sha"]
                and bool(result and TestResult.model_validate(result).passed)
                and bool(run.get("test_evidence"))
            )
            reason = (
                "" if passed else run.get("reason", "Pipeline did not produce a tested repair.")
            )
            if run.get("commit_sha") != entry["expected_commit_sha"]:
                reason = "Commit differs from the manifest. Restore the pinned benchmark revision."
            with sessions.begin() as db:
                if db.get(RunRow, run["id"]) is None:
                    raise RuntimeError(
                        "DATABASE_URL must point to the same database as the API worker."
                    )
                case_row = db.get(EvalCaseRow, case["id"])
                assert case_row
                case_row.repo = entry["repo_url"]
                db.add(
                    EvalResultRow(
                        case_id=case["id"],
                        run_id=run["id"],
                        result="passed" if passed else "failed",
                        attempts=len(run["attempts"]),
                        duration_seconds=observation["duration_seconds"],
                        failure_reason=reason,
                        commit_sha=run.get("commit_sha", ""),
                        model=run.get("model", ""),
                        evidence={
                            "source": "real_api",
                            "remote_runs": run.get("test_evidence", []),
                            "observed_at": observation["observed_at"],
                        },
                    )
                )
            observations.append(
                {
                    "case_id": case["id"],
                    "result": "passed" if passed else "failed",
                    "failure_reason": reason,
                    **observation,
                }
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(observations, indent=2) + "\n")
            print(f"{case['id']}: {'passed' if passed else 'failed'}; run {run['id']}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
