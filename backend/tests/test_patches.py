from pathlib import Path

import pytest
from app.agent.tools.patches import Change, PatchProposal, PatchValidator, reset_to_baseline
from app.errors import PatchRejected
from app.security import Redactor
from conftest import CASES


def test_valid_diff_is_checked_applied_and_reset(repo: Path) -> None:
    source = (repo / "slugify.py").read_text()
    diff = PatchValidator(Redactor()).apply(
        repo, PatchProposal.model_validate_json(CASES[0].proposal())
    )
    assert '-    return "_".join' in diff
    assert '+    return "-".join' in diff
    assert (repo / "slugify.py").read_text() != source
    reset_to_baseline(repo)
    assert (repo / "slugify.py").read_text() == source


@pytest.mark.parametrize(
    "name",
    [
        "tests/test_slugify.py",
        "test_module.py",
        "module_test.py",
        "TestThing.py",
        "conftest.py",
        "setup.py",
        "pyproject.toml",
        ".env",
        "../source.py",
        "/tmp/source.py",
        "sub/../slugify.py",
        "sub\\slugify.py",
        "./slugify.py",
    ],
)
def test_protected_and_traversal_paths_rejected(repo: Path, name: str) -> None:
    proposal = PatchProposal(changes=[Change(path=name, search="x", replace="y")])
    with pytest.raises(PatchRejected):
        PatchValidator(Redactor()).apply(repo, proposal)


def test_ambiguous_search_rejected(repo: Path) -> None:
    with pytest.raises(PatchRejected, match="exactly once"):
        PatchValidator(Redactor()).apply(
            repo,
            PatchProposal(
                changes=[
                    Change(path="slugify.py", search="\n", replace=""),
                ]
            ),
        )


def test_no_whole_file_rewrites(repo: Path) -> None:
    with pytest.raises(PatchRejected, match="Whole-file"):
        PatchValidator(Redactor()).apply(
            repo,
            PatchProposal(
                changes=[
                    Change(
                        path="slugify.py",
                        search=(repo / "slugify.py").read_text(),
                        replace="pass\n",
                    ),
                ]
            ),
        )


def test_size_limit_and_secrets(repo: Path) -> None:
    proposal = PatchProposal.model_validate_json(CASES[0].proposal())
    with pytest.raises(PatchRejected, match="changed-line"):
        PatchValidator(Redactor(), max_lines=1).apply(repo, proposal)
    proposal.changes[0].replace = 'return "gsk_123456789012345678901234567890".join'
    with pytest.raises(PatchRejected, match="secret"):
        PatchValidator(Redactor()).apply(repo, proposal)


def test_multi_file_validation_is_atomic(repo: Path) -> None:
    source = (repo / "slugify.py").read_text()
    proposal = PatchProposal.model_validate_json(CASES[0].proposal())
    proposal.changes.append(Change(path="missing.py", search="bad", replace="good"))
    with pytest.raises(PatchRejected):
        PatchValidator(Redactor()).apply(repo, proposal)
    assert (repo / "slugify.py").read_text() == source


def test_symlink_rejected(repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "external.py"
    outside.write_text("x = 1\n")
    (repo / "linked.py").symlink_to(outside)
    with pytest.raises(PatchRejected, match="Symlink"):
        PatchValidator(Redactor()).apply(
            repo,
            PatchProposal(
                changes=[
                    Change(path="linked.py", search="1", replace="2"),
                ]
            ),
        )
    assert outside.read_text() == "x = 1\n"


def test_header_like_source_lines_cannot_bypass_size_limit(repo: Path) -> None:
    old = "+++value\n" * 110
    new = "---value\n" * 110
    (repo / "unary.py").write_text('"""Source, not a diff header."""\n' + old)
    with pytest.raises(PatchRejected, match="changed-line"):
        PatchValidator(Redactor()).apply(
            repo,
            PatchProposal(
                changes=[
                    Change(path="unary.py", search=old, replace=new),
                ]
            ),
        )
