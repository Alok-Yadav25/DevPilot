import contextlib
import io
import json
import socket
import tarfile
import threading
import time
from pathlib import Path
from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound
from docker.types import LogConfig, Ulimit

from app.agent.state import TestResult
from app.errors import DevPilotError
from app.github.clone import inspect_tree
from app.security import Redactor, sensitive_path


def archive_files(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        directories: set[str] = set()
        for name in files:
            for parent in reversed(Path(name).parents):
                if str(parent) == "." or parent.as_posix() in directories:
                    continue
                info = tarfile.TarInfo(parent.as_posix())
                info.type = tarfile.DIRTYPE
                info.uid = info.gid = 10001
                info.mode = 0o700
                archive.addfile(info)
                directories.add(parent.as_posix())
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.uid = info.gid = 10001
            info.mode = 0o600
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def repo_archive(root: Path, max_bytes: int, max_files: int, redactor: Redactor) -> bytes:
    inspect_tree(root, max_bytes, max_files)
    files: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if sensitive_path(relative) or not path.is_file():
            continue
        content = path.read_bytes()
        text = content.decode("utf-8", errors="replace")
        if redactor.contains_secret(text):
            raise DevPilotError(
                "Repository contains secret-like content; remove it before sandboxing."
            )
        files[f"repo/{relative}"] = content
    return archive_files(files)


class DockerRunner:
    def __init__(
        self,
        image: str,
        timeout: int,
        redactor: Redactor,
        max_bytes: int = 100 * 1024 * 1024,
        max_files: int = 10_000,
        client: Any = None,
        cancel: threading.Event | None = None,
    ) -> None:
        self.image = image
        self.timeout = timeout
        self.redactor = redactor
        self.max_bytes = max_bytes
        self.max_files = max_files
        self.client = client
        self.cancel = cancel or threading.Event()

    def preflight(self) -> None:
        try:
            if self.client is None:
                self.client = docker.from_env(timeout=5)
            self.client.ping()
            self.client.images.get(self.image)
        except ImageNotFound as exc:
            raise DevPilotError(
                f"Sandbox image '{self.image}' is missing. "
                "Run: docker build -t devpilot-sandbox:py311 sandbox-image"
            ) from exc
        except DockerException as exc:
            raise DevPilotError(
                "Docker is unavailable. Start Docker Desktop or connect to your sandbox VM. "
                "Repository code will never fall back to host execution."
            ) from exc

    def close(self) -> None:
        if self.client is not None:
            self.client.close()

    @staticmethod
    def container_options() -> dict[str, Any]:
        return {
            "user": "10001:10001",
            "network_mode": "none",
            "network_disabled": True,
            "read_only": True,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "pids_limit": 128,
            "nano_cpus": 1_000_000_000,
            "mem_limit": "512m",
            "memswap_limit": "512m",
            "tmpfs": {
                "/work": "rw,nosuid,nodev,size=160m,uid=10001,gid=10001,mode=0700",
                "/tmp": "rw,nosuid,nodev,size=256m,uid=10001,gid=10001,mode=0700",
            },
            "environment": {
                "HOME": "/tmp",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                "PIP_NO_INDEX": "1",
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PIP_CONFIG_FILE": "/dev/null",
            },
            "ulimits": [
                Ulimit(name="nofile", soft=256, hard=256),
                Ulimit(name="core", soft=0, hard=0),
            ],
            "log_config": LogConfig(type="json-file", config={"max-size": "1m", "max-file": "1"}),
            "labels": {"devpilot.sandbox": "true"},
            "working_dir": "/work",
            "init": True,
            "stdin_open": True,
            # The SDK otherwise copies Docker client proxy variables into containers.
            "use_config_proxy": False,
        }

    def run(self, workdir: Path, timeout: float | None = None) -> TestResult:
        if self.client is None:
            self.preflight()
        seconds = min(self.timeout, timeout if timeout is not None else self.timeout)
        if seconds <= 0:
            return TestResult(exit_code=124, timed_out=True)
        started = time.monotonic()
        deadline = started + seconds
        container = None
        watchdog = None
        input_stream = None
        timed_out = threading.Event()
        try:
            archive = repo_archive(workdir, self.max_bytes, self.max_files, self.redactor)
            container = self.client.containers.create(
                self.image,
                command=["python", "-I", "/opt/devpilot/runner.py"],
                **self.container_options(),
            )

            def kill_at_deadline() -> None:
                timed_out.set()
                with contextlib.suppress(DockerException):
                    container.kill()

            watchdog = threading.Timer(max(0.01, deadline - time.monotonic()), kill_at_deadline)
            watchdog.daemon = True
            watchdog.start()
            input_stream = container.attach_socket(params={"stdin": 1, "stream": 1})
            container.start()
            # Docker's archive/cp API cannot reliably write into a read-only root
            # with tmpfs. Stream input to the trusted non-root entrypoint instead.
            connection = getattr(input_stream, "_sock", input_stream)
            connection.settimeout(max(0.01, min(30, deadline - time.monotonic())))
            connection.sendall(archive)
            connection.shutdown(socket.SHUT_WR)
            input_stream.close()
            input_stream = None
            while True:
                if self.cancel.is_set():
                    container.kill()
                    return TestResult(exit_code=130, infrastructure_error="Cancelled by operator.")
                container.reload()
                if container.status in {"exited", "dead"}:
                    break
                if time.monotonic() >= deadline:
                    kill_at_deadline()
                    break
                time.sleep(0.1)
            container.reload()
            raw_output = container.logs(tail=250).decode("utf-8", errors="replace")
            report_lines = [
                line for line in raw_output.splitlines() if line.startswith("DEVPILOT_RESULT=")
            ]
            output = self.redactor(
                "\n".join(
                    line
                    for line in raw_output.splitlines()
                    if not line.startswith("DEVPILOT_RESULT=")
                )
            )[-16000:]
            if timed_out.is_set():
                return TestResult(exit_code=124, timed_out=True, output_tail=output)
            state = container.attrs.get("State", {})
            if state.get("OOMKilled"):
                return TestResult(
                    exit_code=137,
                    output_tail=output,
                    infrastructure_error="Sandbox memory limit exceeded (512 MiB).",
                )
            try:
                result = self._read_report(report_lines[-1] if report_lines else "")
            except DevPilotError as exc:
                result = TestResult(
                    exit_code=state.get("ExitCode", 1), infrastructure_error=str(exc)
                )
            result.output_tail = output
            result.duration_seconds = round(time.monotonic() - started, 3)
            if not result.infrastructure_error and state.get("ExitCode", 1) != result.exit_code:
                result.infrastructure_error = "Sandbox exit code did not match the pytest report."
            return result
        except (DockerException, OSError) as exc:
            if timed_out.is_set():
                return TestResult(exit_code=124, timed_out=True)
            raise DevPilotError(
                "Docker sandbox operation failed. Check the Docker daemon."
            ) from exc
        finally:
            if watchdog is not None:
                watchdog.cancel()
            if input_stream is not None:
                with contextlib.suppress(OSError):
                    input_stream.close()
            if container is not None:
                # On daemon failure, labeled containers can be pruned after recovery.
                with contextlib.suppress(DockerException):
                    container.remove(force=True)

    def _read_report(self, line: str) -> TestResult:
        try:
            # tmpfs vanishes when the container exits. Docker's bounded log retains
            # the structured report without any writable host mount.
            if not line or len(line) > 1024 * 1024:
                raise ValueError("missing or oversized sandbox report")
            payload = json.loads(line.removeprefix("DEVPILOT_RESULT="))
            return TestResult.model_validate(payload)
        except ValueError as exc:
            raise DevPilotError(
                "Sandbox produced no valid test report. Check its truncated logs."
            ) from exc
