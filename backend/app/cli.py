import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.agent.graph import Agent
from app.agent.llm import GroqClient
from app.agent.state import Event, RunReport
from app.config import Settings
from app.errors import DevPilotError
from app.github.clone import cleanup_stale, validate_repo_url
from app.policy import RunPolicy
from app.sandbox.factory import Runner, make_runner
from app.security import Redactor


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="DevPilot — Python/pytest CLI. Sandbox branches only; no target pushes or PRs."
    )
    commands = result.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Repair an allowlisted public Python repository")
    run.add_argument("repo", help="https://github.com/owner/repo")
    issue = run.add_mutually_exclusive_group(required=True)
    issue.add_argument("--issue", help="Bug description or failing pytest node ID")
    issue.add_argument("--issue-file", type=Path, help="Read the bug description from a local file")
    run.add_argument(
        "--expected-failure",
        action="append",
        default=[],
        metavar="PYTEST_NODE_ID",
        help="Exact failing node ID; repeat for multiple. Unrelated failures stop the run.",
    )
    run.add_argument(
        "--json-events", action="store_true", help="Emit newline-delimited JSON events"
    )
    commands.add_parser("doctor", help="Check selected runner, API key and current model")
    commands.add_parser("models", help="List current models from the authenticated Groq API")
    commands.add_parser("cleanup", help="Delete expired, unlocked agent workspaces")
    return result


def export_report(report: RunReport, root: Path, redactor: Redactor) -> Path:
    target = root / report.id
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    files = {
        "report.json": report.model_dump_json(indent=2),
        "events.jsonl": "\n".join(e.model_dump_json() for e in report.events) + "\n",
    }
    if report.final_diff:
        files["patch.diff"] = report.final_diff
    for name, content in files.items():
        path = target / name
        with path.open("x", encoding="utf-8") as stream:
            os.chmod(path, 0o600)
            stream.write(redactor(content))
    return target


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    redact = Redactor()
    llm = None
    sandbox: Runner | None = None
    agent: Agent | None = None
    try:
        settings = Settings()
        redact = Redactor(settings.secrets())
        if args.command == "cleanup":
            print(f"Removed {cleanup_stale(settings.work_root)} expired workspaces.")
            return 0

        def show(event: Event) -> None:
            if getattr(args, "json_events", False):
                print(event.model_dump_json(), flush=True)
            else:
                stamp = event.timestamp.strftime("%H:%M:%S")
                print(f"{stamp} UTC  {event.node:15} {event.type:7} {event.message}", flush=True)

        def sandbox_waiting(message: str) -> None:
            if agent:
                agent.emit("sandbox", "waiting", message)
            else:
                show(Event(node="sandbox", type="waiting", message=redact(message)))

        settings.max_repo_bytes = min(settings.max_repo_bytes, settings.max_repo_mb * 1024 * 1024)
        # Validate input before spending any API budget.
        if settings.runner_mode == "replay" and args.command == "doctor":
            print("Ready: replay runner; no provider calls or repository execution.")
            return 0
        if settings.runner_mode == "replay" and args.command == "run":
            raise DevPilotError(
                "Replay mode cannot create a live run. Choose a recording in the website."
            )
        if args.command == "run":
            validate_repo_url(args.repo)
            issue_text = args.issue_file.read_text() if args.issue_file else args.issue
            RunPolicy(settings).request(args.repo, issue_text)
            if not issue_text.strip() or len(issue_text) > 16000:
                raise DevPilotError("The issue must contain 1–16,000 characters.")
        if args.command != "models":
            sandbox = make_runner(settings, sandbox_waiting)
            sandbox.preflight()
        key = settings.groq_api_key.get_secret_value()
        if not key:
            raise DevPilotError(
                "GROQ_API_KEY is missing. Copy .env.example to .env and set your free Groq key."
            )

        def waiting(message: str) -> None:
            if agent:
                agent.emit("llm", "waiting", message)
            else:
                print(redact(message), file=sys.stderr)

        llm = GroqClient(key, settings.groq_model, waiting)
        if args.command == "models":
            print("\n".join(llm.models()))
            return 0
        llm.preflight()
        if args.command == "doctor":
            print(f"Ready: {settings.runner_mode} runner; Groq model {settings.groq_model}.")
            return 0
        assert sandbox is not None
        # Public-only CLI clones never receive any repository token.
        from app.github.clone import Cloner

        agent = Agent(
            settings,
            llm,
            sandbox,
            show,
            cloner=Cloner(
                settings.max_repo_bytes, settings.max_repo_files, settings.clone_timeout_seconds
            ),
        )
        report = agent.run(args.repo, issue_text, args.expected_failure)
        output = export_report(report, settings.artifact_root, redact)
        summary: dict[str, Any] = {
            "status": report.status,
            "reason": report.reason,
            "artifacts": str(output.resolve()),
            "attempts": len(report.attempts),
        }
        print(json.dumps(summary), file=sys.stderr if args.json_events else sys.stdout)
        return 0 if report.status == "ready_for_review" else 2
    except (DevPilotError, ValidationError, OSError) as exc:
        print(redact(f"DevPilot: {exc}"), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("DevPilot: cancelled.", file=sys.stderr)
        return 130
    finally:
        if llm is not None:
            llm.close()
        if sandbox is not None:
            sandbox.close()


if __name__ == "__main__":
    sys.exit(main())
