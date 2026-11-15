"""Reproducible synthetic cases. Catalog entries are not results."""

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from git import Repo
from sqlalchemy.orm import Session

from app.db.models import EvalCaseRow


def catalog() -> list[dict[str, Any]]:
    return json.loads(files("app").joinpath("evaluation_cases.json").read_text())


def seed_catalog(db: Session) -> None:
    for case in catalog():
        if db.get(EvalCaseRow, case["id"]) is None:
            db.add(
                EvalCaseRow(
                    id=case["id"],
                    repo=f"synthetic/{case['id']}",
                    name=case["name"],
                    category=case["category"],
                    bug_description=case["bug_description"],
                    expected_pass=True,
                )
            )


def materialize(case: dict[str, Any], root: Path) -> None:
    root.mkdir(parents=True)
    (root / "requirements.txt").write_text("# pytest supplied by the trusted image\n")
    (root / "module.py").write_text(
        f'"""{case["name"]}."""\n\n\ndef repair(value):\n    return {case["bug"]}\n'
    )
    (root / "tests").mkdir()
    test = "import pytest\nfrom module import repair\n\n"
    test += f"@pytest.mark.parametrize('value,expected', {case['tests']!r})\n"
    test += "def test_regression(value, expected):\n    assert repair(value) == expected\n"
    (root / "tests" / "test_regression.py").write_text(test)
    with Repo.init(root) as repo:
        repo.index.add(["requirements.txt", "module.py", "tests/test_regression.py"])
        repo.index.commit("Inject a reproducible synthetic bug")
