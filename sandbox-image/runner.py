"""Trusted container entrypoint. NEVER execute this file on the host.

Dependency build hooks, project imports and pytest plugins all run inside the same
networkless sandbox. The report is evidence for review, not a security attestation:
malicious code in the container can tamper with its own test process and report.
"""

import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO


def write_result(
    exit_code: int,
    outcomes: dict[str, str],
    error: str = "",
    failure_details: dict[str, str] | None = None,
) -> None:
    print(
        "DEVPILOT_RESULT="
        + json.dumps(
            {
                "exit_code": exit_code,
                "outcomes": outcomes,
                "infrastructure_error": error,
                "failure_details": failure_details or {},
            }
        ),
        flush=True,
    )


class Reporter:
    def __init__(self) -> None:
        self.outcomes: dict[str, str] = {}
        self.failures: dict[str, str] = {}

    def pytest_runtest_logreport(self, report: Any) -> None:
        nodeid = str(report.nodeid)
        outcome = str(report.outcome)
        when = str(report.when)
        if outcome == "failed":
            self.outcomes[nodeid] = "failed"
            crash = getattr(report.longrepr, "reprcrash", None)
            self.failures[nodeid] = str(getattr(crash, "message", report.longrepr))[-2000:]
        elif self.outcomes.get(nodeid) != "failed" and (when == "call" or outcome == "skipped"):
            self.outcomes[nodeid] = outcome

    def pytest_collectreport(self, report: Any) -> None:
        if getattr(report, "failed", False):
            self.outcomes[str(report.nodeid)] = "collection_error"
            self.failures[str(report.nodeid)] = str(report.longrepr)[-2000:]


def extract_input(stream: BinaryIO, root: Path) -> None:
    """Consume the controller's tar stream without executing any repository code."""
    size = count = 0
    with tarfile.open(fileobj=stream, mode="r|") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.parts[0] != "repo"
            ):
                raise ValueError("invalid input path")
            destination = root.joinpath(*path.parts)
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True, mode=0o700)
            elif member.isfile():
                size += member.size
                count += 1
                if size > 100 * 1024 * 1024 or count > 10000:
                    raise ValueError("input archive exceeds limits")
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("invalid input file")
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with destination.open("xb") as output:
                    output.write(source.read())
            else:
                raise ValueError("only regular files and directories are accepted")


def main() -> int:
    extract_input(sys.stdin.buffer, Path("/work"))
    repo = Path("/work/repo")
    os.chdir(repo)
    # No index, URLs, VCS sources or recursive requirement files. Reject rather than
    # attempting to fetch anything. Package hooks still run only inside Docker.
    requirements = repo / "requirements.txt"
    if requirements.exists():
        for line in requirements.read_text().splitlines():
            line = line.strip()
            if (
                line
                and not line.startswith("#")
                and (line.startswith("-") or "://" in line or "@" in line)
            ):
                message = (
                    "Unsupported requirements entry. Use plain packages in the offline wheelhouse."
                )
                print(message, flush=True)
                write_result(4, {}, message)
                return 4
        install_args = ["-r", "requirements.txt"]
    else:
        install_args = []
    subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", "/tmp/venv"], check=True
    )
    python = "/tmp/venv/bin/python"
    pip = [
        python,
        "-m",
        "pip",
        "install",
        "--no-index",
        "--find-links=/opt/wheels",
        "--no-build-isolation",
        "--disable-pip-version-check",
    ]
    if install_args:
        result = subprocess.run([*pip, *install_args], check=False)
        if result.returncode:
            message = "Dependencies unavailable offline. Add reviewed wheels to the sandbox image."
            write_result(4, {}, message)
            return 4
    # Run this trusted script again in the venv so dependencies/plugins are visible.
    return subprocess.call([python, "-I", "/opt/devpilot/runner.py", "--pytest"])


def run_pytest() -> int:
    repo = Path("/work/repo")
    os.chdir(repo)
    sys.path.insert(0, str(repo))
    # Install a pyproject package only when it declares a build backend. A config-only
    # pyproject can use PYTHONPATH (including src/) without pretending to be a package.
    import tomllib

    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        metadata = tomllib.loads(pyproject.read_text())
        if "build-system" in metadata:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-index",
                    "--find-links=/opt/wheels",
                    "--no-build-isolation",
                    "--disable-pip-version-check",
                    ".",
                ],
                check=False,
            )
            if result.returncode:
                message = (
                    "Project or build dependencies unavailable offline; prepare reviewed wheels."
                )
                write_result(4, {}, message)
                return 4
    if (repo / "src").is_dir():
        sys.path.insert(0, str(repo / "src"))
    import pytest

    reporter = Reporter()
    exit_code = int(
        pytest.main(
            ["-q", "--tb=short", "--color=no", "-o", "cache_dir=/tmp/pytest-cache"],
            plugins=[reporter],
        )
    )
    write_result(exit_code, reporter.outcomes, failure_details=reporter.failures)
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(run_pytest() if "--pytest" in sys.argv else main())
    except Exception as error:
        write_result(4, {}, f"Sandbox setup failed: {type(error).__name__}")
        raise
