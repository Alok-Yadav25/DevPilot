"""One public Python/pytest policy for API, worker, CLI and patch retries."""

from pathlib import Path
from uuid import uuid4

import httpx

from app.agent.tools.retrieval import check_python_project
from app.config import Settings
from app.errors import DevPilotError, UnsuitableRepository
from app.github.clone import Cloner, inspect_tree, validate_repo_url, workspace


class RunPolicy:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings, self.client = settings, client

    def request(self, url: str, issue: str, attempt: int = 0) -> str:
        normalized = validate_repo_url(url.rstrip("/"))
        repo = normalized.removeprefix("https://github.com/").removesuffix(".git")
        allowed = {
            r.strip().lower() for r in self.settings.allowed_target_repos.split(",") if r.strip()
        }
        owned = self.settings.allowed_target_owner.strip().lower()
        if repo.lower() not in allowed and (not owned or repo.split("/")[0].lower() != owned):
            raise DevPilotError(
                "Repository is not allowlisted. Set ALLOWED_TARGET_REPOS or ALLOWED_TARGET_OWNER."
            )
        if not 8 <= len(issue.strip()) <= 16000:
            raise DevPilotError("Provide a bug description between 8 and 16,000 characters.")
        if not 0 <= attempt < self.settings.max_attempts:
            raise DevPilotError(
                "Maximum patch attempts reached. Review this run before starting another."
            )
        return normalized

    def remote(self, url: str, issue: str, attempt: int = 0) -> str:
        normalized = self.request(url, issue, attempt)
        repo = normalized.removeprefix("https://github.com/").removesuffix(".git")
        own = self.client is None
        client = self.client or httpx.Client(
            base_url="https://api.github.com/", timeout=15, follow_redirects=False
        )
        try:
            # Neither scoped token is used to inspect public targets.
            response = client.get(f"repos/{repo}")
            if response.status_code == 404:
                raise DevPilotError(
                    "Public repository not found. Check the URL; private repos are unsupported."
                )
            if response.status_code in {403, 429}:
                raise DevPilotError("GitHub metadata is rate limited. Wait for reset and retry.")
            response.raise_for_status()
            info = response.json()
            if info.get("private") is not False:
                raise UnsuitableRepository(
                    "Private repositories are unsupported. Choose an allowlisted public repo."
                )
            if int(info.get("size", 0)) * 1024 > min(
                self.settings.max_repo_bytes, self.settings.max_repo_mb * 1024 * 1024
            ):
                raise UnsuitableRepository(
                    "Repository exceeds the size limit. Choose a smaller repo."
                )
            if info.get("language") not in {"Python", None}:
                raise UnsuitableRepository(
                    "Only Python/pytest projects are supported. Choose a Python repo."
                )
            return normalized
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise DevPilotError(
                "Could not check public repository metadata. Check GitHub availability and retry."
            ) from exc
        finally:
            if own:
                client.close()

    def checkout(self, root: Path) -> None:
        inspect_tree(
            root,
            min(self.settings.max_repo_bytes, self.settings.max_repo_mb * 1024 * 1024),
            self.settings.max_repo_files,
        )
        check_python_project(root)
        if not any(
            p.name.startswith("test") or p.stem.endswith("_test") for p in root.rglob("*.py")
        ):
            raise UnsuitableRepository(
                "No pytest tests found. Add a reproducible pytest suite before running."
            )

    def readiness(self, url: str, issue: str = "Repository readiness check") -> str:
        normalized = self.remote(url, issue)
        with workspace(self.settings.work_root, "readiness-" + uuid4().hex[:12]) as root:
            Cloner(
                min(self.settings.max_repo_bytes, self.settings.max_repo_mb * 1024 * 1024),
                self.settings.max_repo_files,
                self.settings.clone_timeout_seconds,
            ).clone(normalized, root)
            self.checkout(root)
        return normalized
