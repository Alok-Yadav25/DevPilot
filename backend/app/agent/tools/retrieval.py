import re
import tomllib
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet

from app.errors import UnsuitableRepository
from app.security import Redactor, sensitive_path


def check_python_project(root: Path) -> None:
    requirements = root / "requirements.txt"
    pyproject = root / "pyproject.toml"
    if not requirements.is_file() and not pyproject.is_file():
        raise UnsuitableRepository(
            "v1 requires requirements.txt or pyproject.toml and a pytest suite."
        )
    if pyproject.exists():
        try:
            config = tomllib.loads(pyproject.read_text())
            requires = config.get("project", {}).get("requires-python", "")
            if requires and not any(
                f"3.11.{micro}" in SpecifierSet(requires) for micro in range(100)
            ):
                raise UnsuitableRepository("This project does not support Python 3.11.")
        except (tomllib.TOMLDecodeError, InvalidSpecifier) as exc:
            raise UnsuitableRepository(
                "pyproject.toml has invalid Python project metadata."
            ) from exc


def locate(root: Path, issue: str, test_output: str, redactor: Redactor) -> tuple[list[str], str]:
    """Local text retrieval only; never import or execute repository modules."""
    clues = issue + "\n" + test_output
    tokens = {s.lower() for s in re.findall(r"[A-Za-z_][A-Za-z_0-9]{3,}", clues)}
    stop_words = {"error", "failed", "test", "assert", "return", "python", "line", "file"}
    tokens -= stop_words
    candidates: list[tuple[int, str, list[str], list[int]]] = []
    for file in sorted(root.rglob("*.py")):
        name = file.relative_to(root).as_posix()
        if sensitive_path(name) or file.is_symlink() or file.stat().st_size > 128_000:
            continue
        try:
            lines = file.read_text().splitlines()
        except (UnicodeError, OSError):
            continue
        matches = [i for i, line in enumerate(lines) if any(t in line.lower() for t in tokens)]
        score = min(len(matches), 20) + (40 if name in clues else 0)
        score += 8 if file.stem.lower() in clues.lower() else 0
        if not any(p.lower().startswith("test") for p in file.relative_to(root).parts):
            score += 2
        candidates.append((score, name, lines, matches))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    tree = [
        p.relative_to(root).as_posix()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not sensitive_path(p.relative_to(root).as_posix())
    ][:160]
    chunks = ["FILE TREE (truncated):\n" + "\n".join(tree)]
    names: list[str] = []
    budget = 30000
    for _, name, lines, matches in candidates[:8]:
        indexes: set[int] = set()
        for center in matches[:8] or [0]:
            indexes.update(range(max(0, center - 12), min(len(lines), center + 25)))
        excerpt = "\n".join(f"{i + 1:4}: {lines[i]}" for i in sorted(indexes))[:6000]
        excerpt = redactor(excerpt)
        if len(excerpt) > budget:
            break
        names.append(name)
        chunks.append(f"FILE {name}:\n{excerpt}")
        budget -= len(excerpt)
    if not names:
        raise UnsuitableRepository("No readable Python source found within the context limits.")
    return names, "\n\n".join(chunks)


def failing_output(output: str) -> str:
    start = output.find("FAILURES")
    if start < 0:
        start = output.find("ERRORS")
    return (output[start:] if start >= 0 else output)[-10000:]
