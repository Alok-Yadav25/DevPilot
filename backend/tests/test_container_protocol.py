"""Test the trusted input parser only; never invoke runner.main or fixture code."""

import importlib.util
import io
import tarfile
from pathlib import Path
from typing import Any

import pytest
from app.sandbox.docker_runner import archive_files


@pytest.fixture
def trusted_parser() -> Any:
    path = Path(__file__).resolve().parents[2] / "sandbox-image" / "runner.py"
    spec = importlib.util.spec_from_file_location("trusted_container_protocol", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.extract_input


def test_tar_stdin_protocol_preserves_regular_files(tmp_path: Path, trusted_parser: Any) -> None:
    contents = {"repo/module.py": b"# source data, never imported\n", "repo/tests/data": b"abc"}
    trusted_parser(io.BytesIO(archive_files(contents)), tmp_path)
    assert (tmp_path / "repo/module.py").read_bytes() == contents["repo/module.py"]
    assert (tmp_path / "repo/tests/data").read_bytes() == b"abc"


@pytest.mark.parametrize("path", ["../escape", "/absolute", "wrong-root/file", "repo/../../escape"])
def test_parser_rejects_escaping_paths(tmp_path: Path, trusted_parser: Any, path: str) -> None:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        member = tarfile.TarInfo(path)
        archive.addfile(member, io.BytesIO())
    with pytest.raises(ValueError, match="invalid input path"):
        trusted_parser(io.BytesIO(stream.getvalue()), tmp_path)


def test_parser_rejects_links(tmp_path: Path, trusted_parser: Any) -> None:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        member = tarfile.TarInfo("repo/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "/etc/passwd"
        archive.addfile(member)
    with pytest.raises(ValueError, match="only regular"):
        trusted_parser(io.BytesIO(stream.getvalue()), tmp_path)
