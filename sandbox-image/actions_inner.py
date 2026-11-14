"""Trusted code embedded in the Actions image; runs ONLY inside its container."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def tail(path: str) -> str:
    with open(path, "rb") as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 4000))
        return stream.read().decode(errors="replace")


def main() -> None:
    payload = json.loads(sys.stdin.buffer.readline(64000))
    target, ref = payload["target_repo"], payload["target_ref"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", target):
        raise ValueError("invalid repository")
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise ValueError("immutable SHA required")
    result = {"applied": False, "exit_code": 4, "outcomes": {}, "failure_details": {}}
    Path("/tmp/install.log").touch()
    Path("/tmp/pytest.log").touch()
    try:
        # Git, package hooks, conftest and pytest all execute in this container.
        with open("/tmp/install.log", "w") as log:
            subprocess.run(["git", "init", "/work/repo"], check=True, stdout=log, stderr=log)
            os.chdir("/work/repo")
            subprocess.run(
                ["git", "fetch", "--depth", "1", f"https://github.com/{target}.git", ref],
                check=True,
                stdout=log,
                stderr=log,
            )
            subprocess.run(
                ["git", "-c", "advice.detachedHead=false", "checkout", "--detach", "FETCH_HEAD"],
                check=True,
                stdout=log,
                stderr=log,
            )
            paths = list(Path(".").rglob("*"))
            if any(p.is_symlink() for p in paths):
                raise ValueError("symlink repositories are unsupported")
            if (
                len(paths) > 10000
                or sum(p.stat().st_size for p in paths if p.is_file()) > 50 * 1024 * 1024
            ):
                raise ValueError("repo exceeds limits")
            diff = payload["diff"]
            if diff:
                Path("/tmp/patch.diff").write_text(diff)
                subprocess.run(
                    ["git", "apply", "--check", "/tmp/patch.diff"],
                    check=True,
                    stdout=log,
                    stderr=log,
                )
                changes = subprocess.check_output(
                    ["git", "apply", "--numstat", "/tmp/patch.diff"], text=True
                ).splitlines()
                count = 0
                if len(changes) > 5:
                    raise ValueError("patch exceeds file limit")
                for entry in changes:
                    added, deleted, name = entry.split("\t")
                    path = Path(name)
                    if (
                        path.suffix != ".py"
                        or path.is_absolute()
                        or ".." in path.parts
                        or any(
                            p.startswith(".") or p.lower().startswith("test") for p in path.parts
                        )
                        or path.name in {"conftest.py", "setup.py", "noxfile.py", "fabfile.py"}
                        or path.stem.lower().endswith("_test")
                    ):
                        raise ValueError("protected patch path")
                    count += int(added) + int(deleted)
                if count > 200:
                    raise ValueError("patch exceeds changed-line limit")
                subprocess.run(
                    ["git", "apply", "/tmp/patch.diff"], check=True, stdout=log, stderr=log
                )
            result["applied"] = True  # Empty baseline patch is a valid no-op.
            pip = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--target=/tmp/deps",
            ]
            if Path("requirements.txt").is_file():
                subprocess.run([*pip, "-r", "requirements.txt"], check=True, stdout=log, stderr=log)
            elif not Path("pyproject.toml").is_file():
                raise ValueError("requires requirements.txt or pyproject.toml")
            if Path("pyproject.toml").is_file():
                import tomllib

                if "build-system" in tomllib.loads(Path("pyproject.toml").read_text()):
                    subprocess.run([*pip, "."], check=True, stdout=log, stderr=log)
        # Dependency preparation needs public downloads. The trusted host disconnects
        # every container network before allowing any pytest import or test hook.
        print("DEVPILOT_TEST_READY", flush=True)
        if sys.stdin.buffer.readline(64) != b"continue\n":
            raise RuntimeError("Network isolation was not acknowledged by the host")
        sys.path[:0] = ["/tmp/deps", "/work/repo", "/work/repo/src"]
        import pytest

        class Reporter:
            def pytest_runtest_logreport(self, report):
                if report.failed:
                    result["outcomes"][report.nodeid] = "failed"
                    crash = getattr(report.longrepr, "reprcrash", None)
                    result["failure_details"][report.nodeid] = str(
                        getattr(crash, "message", report.longrepr)
                    )[-1000:]
                elif result["outcomes"].get(report.nodeid) != "failed" and (
                    report.when == "call" or report.skipped
                ):
                    result["outcomes"][report.nodeid] = report.outcome

            def pytest_collectreport(self, report):
                if report.failed:
                    result["outcomes"][report.nodeid] = "collection_error"

        # Redirect even native fd writes into bounded tmpfs logs, not the host.
        with open("/tmp/pytest.log", "w") as log:
            saved = os.dup(1), os.dup(2)
            os.dup2(log.fileno(), 1)
            os.dup2(log.fileno(), 2)
            try:
                result["exit_code"] = int(
                    pytest.main(
                        ["-q", "--tb=short", "--color=no", "-o", "cache_dir=/tmp/cache"],
                        plugins=[Reporter()],
                    )
                )
            finally:
                sys.stdout.flush()
                sys.stderr.flush()
                os.dup2(saved[0], 1)
                os.dup2(saved[1], 2)
                os.close(saved[0])
                os.close(saved[1])
    except Exception as exc:
        result["infrastructure_error"] = (
            f"Sandbox setup failed ({type(exc).__name__}). Inspect install.log."
        )
    print(
        json.dumps(
            {
                "results": result,
                "pytest_log": tail("/tmp/pytest.log"),
                "install_log": tail("/tmp/install.log"),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
