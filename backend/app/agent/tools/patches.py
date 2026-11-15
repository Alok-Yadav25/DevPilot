import difflib
import re
import subprocess
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from app.errors import PatchRejected
from app.github.clone import git_env
from app.security import Redactor, sensitive_path


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=240)
    search: str = Field(min_length=1, max_length=16000)
    replace: str = Field(max_length=16000)


class PatchProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: list[Change] = Field(min_length=1, max_length=20)


def protected_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        sensitive_path(name)
        or path.suffix != ".py"
        or any(part.lower().startswith("test") for part in path.parts)
        or path.name.lower() in {"conftest.py", "setup.py", "noxfile.py", "fabfile.py"}
        or path.stem.lower().endswith("_test")
    )


def run_git(workdir: Path, *args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=workdir,
        env=git_env(),
        input=input_text,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode:
        raise PatchRejected("git rejected the patch: " + result.stderr[-2000:])
    return result.stdout


def reset_to_baseline(workdir: Path) -> None:
    # No checkout/reset hooks. Only our validated .py changes ever reach this worktree.
    run_git(
        workdir, "-c", "core.hooksPath=/dev/null", "restore", "--source=HEAD", "--worktree", "."
    )


class PatchValidator:
    def __init__(self, redactor: Redactor, max_lines: int = 200, max_files: int = 5) -> None:
        self.redactor = redactor
        self.max_lines = max_lines
        self.max_files = max_files

    def apply(self, workdir: Path, proposal: PatchProposal) -> str:
        originals: dict[str, str] = {}
        updated: dict[str, str] = {}
        for change in proposal.changes:
            path = PurePosixPath(change.path)
            if (
                path.is_absolute()
                or ".." in path.parts
                or str(path) != change.path
                or "\\" in change.path
                or not re.fullmatch(r"[A-Za-z0-9_./-]+", change.path)
                or protected_path(change.path)
            ):
                raise PatchRejected(f"Protected or invalid path: {change.path}")
            target = workdir.joinpath(*path.parts)
            if any(parent.is_symlink() for parent in [target, *target.parents]):
                raise PatchRejected("Symlink paths cannot be patched.")
            if not target.is_file() or target.stat().st_size > 128_000:
                raise PatchRejected("Only existing, small Python source files may be changed.")
            if change.path not in originals:
                originals[change.path] = target.read_text(encoding="utf-8")
                updated[change.path] = originals[change.path]
            source = updated[change.path]
            if source.count(change.search) != 1:
                raise PatchRejected(f"Search must match exactly once in {change.path}.")
            if change.search.strip() == source.strip():
                raise PatchRejected(
                    "Whole-file replacements are forbidden; use a smaller exact block."
                )
            updated[change.path] = source.replace(change.search, change.replace, 1)
        if len(updated) > self.max_files:
            raise PatchRejected(f"Patch exceeds the {self.max_files}-file limit.")
        diff = "".join(
            "".join(
                difflib.unified_diff(
                    originals[name].splitlines(keepends=True),
                    updated[name].splitlines(keepends=True),
                    fromfile=f"a/{name}",
                    tofile=f"b/{name}",
                )
            )
            for name in sorted(updated)
        )
        if not diff or len(diff.encode()) > 48_000:
            raise PatchRejected("Patch must change code and stay under 48 KB.")
        if any(not text.endswith("\n") for text in [*originals.values(), *updated.values()]):
            raise PatchRejected(
                "v1 requires newline-terminated source files and replacement blocks."
            )
        count = 0
        for name in updated:
            matcher = difflib.SequenceMatcher(
                a=originals[name].splitlines(),
                b=updated[name].splitlines(),
                autojunk=False,
            )
            for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
                if tag != "equal":
                    count += old_end - old_start + new_end - new_start
        if count > self.max_lines:
            raise PatchRejected(f"Patch exceeds the {self.max_lines} changed-line limit.")
        if self.redactor(diff) != diff:
            raise PatchRejected("Patch contains secret-like content; it cannot be exported safely.")
        # Check the exact exported diff, then apply atomically through trusted git.
        run_git(workdir, "apply", "--check", "--whitespace=error", "-", input_text=diff)
        run_git(workdir, "apply", "--whitespace=error", "-", input_text=diff)
        return diff
