import json
from pathlib import Path

from app.agent.state import Event, RunReport, TestResult
from app.cli import export_report, main
from app.security import Redactor


def test_secret_and_terminal_redaction() -> None:
    redact = Redactor(["my-secret"])
    text = redact("\x1b[31mmy-secret https://token@github.com/a/b gsk_1234567890123\x00")
    assert "my-secret" not in text and "token@" not in text and "gsk_" not in text
    assert "\x1b" not in text and "\x00" not in text


def test_report_and_events_are_private_and_redacted(tmp_path: Path) -> None:
    report = RunReport(
        id="run1", repo_url="https://github.com/owner/repo", issue_text="secret-value"
    )
    report.events.append(Event(node="clone", type="start", message="secret-value"))
    target = export_report(report, tmp_path, Redactor(["secret-value"]))
    assert "secret-value" not in (target / "report.json").read_text()
    assert json.loads((target / "report.json").read_text())["id"] == "run1"
    assert (target / "report.json").stat().st_mode & 0o777 == 0o600


def test_empty_test_suite_never_passes() -> None:
    assert not TestResult(exit_code=0).passed


def test_cli_rejects_non_github_before_docker(capsys: object) -> None:
    assert main(["run", "file:///tmp/repo", "--issue", "bug"]) == 2
