from pathlib import Path

import pytest
from app.agent.tools.retrieval import check_python_project, locate
from app.errors import UnsuitableRepository
from app.security import Redactor


def test_project_preflight_is_static_and_rejects_wrong_python(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"\n')
    with pytest.raises(UnsuitableRepository, match="3.11"):
        check_python_project(tmp_path)


def test_project_needs_a_dependency_manifest(tmp_path: Path) -> None:
    with pytest.raises(UnsuitableRepository, match="requirements.txt"):
        check_python_project(tmp_path)


def test_retrieval_selects_traceback_file_and_redacts_context(repo: Path) -> None:
    (repo / "extra.py").write_text('TOKEN = "secret-test-value"\n')
    files, context = locate(
        repo, "Fix slugify separator", "slugify.py:4", Redactor(["secret-test-value"])
    )
    assert files[0] == "slugify.py"
    assert "secret-test-value" not in context
    assert ".git/" not in context
    assert len(context) < 40000
