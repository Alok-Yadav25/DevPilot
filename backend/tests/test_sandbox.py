import io
import tarfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.errors import DevPilotError
from app.sandbox.docker_runner import DockerRunner, repo_archive
from app.security import Redactor
from docker.errors import DockerException, ImageNotFound


def mocked_runner(**kwargs: object) -> tuple[DockerRunner, MagicMock]:
    client = MagicMock()
    container = client.containers.create.return_value
    container.status = "exited"
    container.attrs = {"State": {"ExitCode": 0}}
    container.logs.return_value = (
        b'pytest output\nDEVPILOT_RESULT={"exit_code":0,"outcomes":{"test.py::test_a":"passed"}}\n'
    )
    return DockerRunner(
        "test-image", 5, Redactor(["private-value"]), client=client, **kwargs
    ), client


def test_container_has_all_required_security_controls(repo: Path) -> None:
    runner, client = mocked_runner()
    result = runner.run(repo)
    assert result.passed
    options = client.containers.create.call_args.kwargs
    assert options["network_disabled"] and options["network_mode"] == "none"
    assert options["user"] == "10001:10001" and options["read_only"]
    assert options["cap_drop"] == ["ALL"]
    assert options["security_opt"] == ["no-new-privileges:true"]
    assert options["nano_cpus"] == 1_000_000_000 and options["pids_limit"] == 128
    assert options["mem_limit"] == options["memswap_limit"] == "512m"
    assert "volumes" not in options and "mounts" not in options
    assert "GROQ_API_KEY" not in options["environment"]
    assert "GITHUB_TOKEN" not in options["environment"]
    assert options["use_config_proxy"] is False
    assert "DEVPILOT_RESULT" not in result.output_tail
    container = client.containers.create.return_value
    container.put_archive.assert_not_called()
    container.attach_socket.return_value._sock.sendall.assert_called_once()
    container.attach_socket.return_value.close.assert_called_once()
    container.remove.assert_called_once_with(force=True)


def test_staging_error_still_removes_container(repo: Path) -> None:
    runner, client = mocked_runner()
    client.containers.create.return_value.attach_socket.side_effect = DockerException(
        "private-value"
    )
    with pytest.raises(DevPilotError, match="Docker sandbox operation failed"):
        runner.run(repo)
    client.containers.create.return_value.remove.assert_called_once_with(force=True)


def test_hard_timeout_kills_and_removes_container(repo: Path) -> None:
    runner, client = mocked_runner()
    container = client.containers.create.return_value
    container.status = "running"
    result = runner.run(repo, timeout=0.02)
    assert result.timed_out and result.exit_code == 124
    container.kill.assert_called()
    container.remove.assert_called_once_with(force=True)


def test_oom_is_not_presented_as_test_failure(repo: Path) -> None:
    runner, client = mocked_runner()
    client.containers.create.return_value.attrs = {"State": {"OOMKilled": True}}
    result = runner.run(repo)
    assert "memory" in result.infrastructure_error and not result.passed


def test_missing_report_and_mismatched_exit_fail_closed(repo: Path) -> None:
    runner, client = mocked_runner()
    client.containers.create.return_value.logs.return_value = b"no report"
    result = runner.run(repo)
    assert "no valid test report" in result.infrastructure_error
    assert result.output_tail == "no report"
    client.containers.create.return_value.logs.return_value = (
        b'DEVPILOT_RESULT={"exit_code":0,"outcomes":{"test":"passed"}}\n'
    )
    client.containers.create.return_value.attrs = {"State": {"ExitCode": 1}}
    assert not runner.run(repo).passed


def test_archive_has_no_git_or_secret_files_and_owns_directories(repo: Path) -> None:
    (repo / ".env").write_text("GITHUB_TOKEN=private-value")
    payload = repo_archive(repo, 1_000_000, 1000, Redactor(["private-value"]))
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        names = archive.getnames()
        assert not any(".git" in name or ".env" in name for name in names)
        directory = archive.getmember("repo/tests")
        assert directory.isdir() and directory.uid == directory.gid == 10001


def test_archive_rejects_secrets_in_source(repo: Path) -> None:
    (repo / "source.py").write_text('TOKEN = "private-value"\n')
    with pytest.raises(DevPilotError, match="secret-like"):
        repo_archive(repo, 1_000_000, 1000, Redactor(["private-value"]))


def test_binary_assets_are_not_mistaken_for_terminal_control_secrets(repo: Path) -> None:
    (repo / "asset.bin").write_bytes(b"\x00\x01\x02\xff")
    repo_archive(repo, 1_000_000, 1000, Redactor())


def test_preflight_never_pulls_untrusted_image() -> None:
    runner, client = mocked_runner()
    client.images.get.side_effect = ImageNotFound("missing")
    with pytest.raises(DevPilotError, match="docker build"):
        runner.preflight()
    client.images.pull.assert_not_called()


def test_logs_are_redacted(repo: Path) -> None:
    runner, client = mocked_runner()
    container = client.containers.create.return_value
    container.logs.return_value = b"private-value\n" + container.logs.return_value
    result = runner.run(repo)
    assert "private-value" not in result.output_tail
    assert "[REDACTED]" in result.output_tail
