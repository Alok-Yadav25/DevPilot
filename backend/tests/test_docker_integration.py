"""Opt-in real Docker tests. No downloaded repository code is run on the host."""

import os
from pathlib import Path

import pytest
from app.agent.graph import Agent
from app.config import Settings
from app.sandbox.docker_runner import DockerRunner
from app.security import Redactor
from conftest import CASES, Case, FixtureCloner, ScriptedLLM

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(
        os.environ.get("DEVPILOT_DOCKER_TESTS") != "1",
        reason="Opt in with DEVPILOT_DOCKER_TESTS=1; requires Docker and built image",
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_real_pytest_baseline_and_repair_on_three_repos(tmp_path: Path, case: Case) -> None:
    settings = Settings(_env_file=None, work_root=tmp_path / "work")
    sandbox = DockerRunner(settings.sandbox_image, 120, Redactor())
    sandbox.preflight()
    report = Agent(
        settings, ScriptedLLM([case.proposal()]), sandbox, cloner=FixtureCloner(case)
    ).run(
        "https://github.com/fixtures/" + case.name,
        case.issue,
        [case.failed],
    )
    assert report.status == "ready_for_review", report.model_dump_json(indent=2)
    assert report.baseline_result.exit_code == 1
    assert report.attempts[0].test_result.passed


def test_real_isolation(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("")
    (tmp_path / "test_isolation.py").write_text("""
import os
import socket
from pathlib import Path
import pytest

def test_isolation():
    assert os.getuid() == 10001
    assert "GROQ_API_KEY" not in os.environ
    assert "GITHUB_TOKEN" not in os.environ
    with pytest.raises(OSError):
        Path("/root-file").write_text("blocked")
    with socket.socket() as s:
        s.settimeout(1)
        with pytest.raises(OSError):
            s.connect(("1.1.1.1", 443))
    assert "NoNewPrivs:\\t1" in Path("/proc/self/status").read_text()
    assert Path("/sys/fs/cgroup/memory.max").read_text().strip() == "536870912"
""")
    runner = DockerRunner("devpilot-sandbox:py311", 120, Redactor())
    runner.preflight()
    assert runner.run(tmp_path).passed


def test_real_timeout(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("")
    (tmp_path / "test_sleep.py").write_text("import time\ndef test_slow():\n    time.sleep(60)\n")
    runner = DockerRunner("devpilot-sandbox:py311", 5, Redactor())
    runner.preflight()
    assert runner.run(tmp_path).timed_out
