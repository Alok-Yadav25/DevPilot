import contextlib
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit

from git import Repo

from app.errors import DevPilotError, RunCancelled, UnsuitableRepository


def validate_repo_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}", parsed.path)
    ):
        raise DevPilotError("Use an HTTPS GitHub repository URL: https://github.com/owner/repo")
    name = parsed.path.rsplit("/", 1)[1]
    if name.removesuffix(".git") in {"", ".", ".."}:
        raise DevPilotError("Invalid GitHub repository name.")
    return "https://github.com" + parsed.path.removesuffix(".git") + ".git"


def inspect_tree(root: Path, max_bytes: int, max_files: int, *, strict: bool = True) -> None:
    size = count = 0
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except FileNotFoundError:
            continue
        for entry in entries:
            try:
                info = entry.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode):
                if strict:
                    raise UnsuitableRepository(
                        "Symlinks are unsupported in v1; use a repo without them."
                    )
                continue
            if stat.S_ISDIR(info.st_mode):
                stack.append(Path(entry.path))
            elif stat.S_ISREG(info.st_mode):
                count += 1
                size += info.st_size
            elif strict:
                raise UnsuitableRepository("Special files are unsupported in v1.")
            if count > max_files or size > max_bytes:
                raise UnsuitableRepository(
                    "Repository exceeds the configured size or file-count limit."
                )


def git_env(token: str = "") -> dict[str, str]:
    # Do not inherit credential helpers, filters, proxy overrides, or Git config injection.
    env = {k: os.environ[k] for k in ("PATH", "HOME", "SYSTEMROOT") if k in os.environ}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_LFS_SKIP_SMUDGE="1",
    )
    config = {
        "core.hooksPath": os.devnull,
        "core.fsmonitor": "false",
        "credential.helper": "",
        "protocol.allow": "never",
        "protocol.https.allow": "always",
        "http.followRedirects": "false",
    }
    if token:
        import base64

        encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        config["http.https://github.com/.extraHeader"] = f"Authorization: Basic {encoded}"
    env["GIT_CONFIG_COUNT"] = str(len(config))
    for index, (key, val) in enumerate(config.items()):
        env[f"GIT_CONFIG_KEY_{index}"] = key
        env[f"GIT_CONFIG_VALUE_{index}"] = val
    return env


class Cloner:
    def __init__(self, max_bytes: int, max_files: int, timeout: float, token: str = "") -> None:
        self.max_bytes = max_bytes
        self.max_files = max_files
        self.timeout = timeout
        self.token = token
        self.cancel = threading.Event()

    def clone(self, url: str, destination: Path) -> str:
        url = validate_repo_url(url)
        # Invoke the trusted git binary with a clean environment. GitPython's execute
        # merges os.environ; Popen lets us exclude inherited Git config and secrets.
        process = subprocess.Popen(
            ["git", "clone", "--depth", "1", "--single-branch", "--", url, str(destination)],
            env=git_env(self.token),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        def drain() -> None:
            assert process.stderr is not None
            while process.stderr.read(4096):
                pass  # Never persist clone output: it may contain transport credentials.

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        deadline = time.monotonic() + self.timeout
        try:
            while process.poll() is None:
                if self.cancel.is_set():
                    raise RunCancelled("Clone cancelled by the operator.")
                if time.monotonic() >= deadline:
                    raise DevPilotError("Clone timed out. Try a smaller repository.")
                if destination.exists():
                    inspect_tree(destination, self.max_bytes, self.max_files, strict=False)
                time.sleep(0.1)
            reader.join(timeout=2)
            if process.returncode:
                # Git output can contain credential headers; never surface it.
                raise DevPilotError(
                    "Clone failed. Check the URL and your repository token permissions."
                )
            inspect_tree(destination, self.max_bytes, self.max_files)
            with Repo(destination) as repo:
                repo.remotes.origin.set_url(url)
                return repo.head.commit.hexsha
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
            reader.join(timeout=2)
            for stream in (process.stdout, process.stderr, process.stdin):
                if stream:
                    stream.close()

    def clone_pinned(self, url: str, destination: Path, sha: str) -> str:
        if not re.fullmatch(r"[a-f0-9]{40}", sha):
            raise DevPilotError("Recovery requires the original immutable commit SHA.")
        self.clone(url, destination)
        for arguments in (["fetch", "--depth", "1", "origin", sha], ["checkout", "--detach", sha]):
            result = subprocess.run(
                ["git", *arguments],
                cwd=destination,
                env=git_env(),
                capture_output=True,
                timeout=self.timeout,
            )
            if result.returncode:
                raise DevPilotError(
                    "The pinned commit is unavailable. Check repo access and retention."
                )
        inspect_tree(destination, self.max_bytes, self.max_files)
        return sha


@contextlib.contextmanager
def workspace(root: Path, run_id: str) -> Iterator[Path]:
    import fcntl

    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory = Path(tempfile.mkdtemp(prefix=f"run-{run_id}-", dir=root))
    with (directory / ".lease").open("w") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        try:
            yield directory / "repo"
        finally:
            shutil.rmtree(directory)


def cleanup_stale(root: Path, max_age_seconds: float = 86400) -> int:
    """Only our expired, unlocked workspaces; active runs hold a lease."""
    import fcntl

    removed = 0
    if not root.exists():
        return removed
    for directory in root.glob("run-*"):
        if directory.is_symlink() or not directory.is_dir():
            continue
        if time.time() - directory.stat().st_mtime < max_age_seconds:
            continue
        try:
            with (directory / ".lease").open("a") as lease:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                shutil.rmtree(directory)
                removed += 1
        except (BlockingIOError, FileNotFoundError):
            continue
    return removed
