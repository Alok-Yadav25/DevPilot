import time
from typing import Any

import httpx

from app.errors import DevPilotError


class GitHubClient:
    """Minimal REST transport. Never fetch repository source file-by-file."""

    def __init__(self, token: str, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            base_url="https://api.github.com/",
            timeout=20,
            follow_redirects=False,
            headers={
                **({"Authorization": f"Bearer {token}"} if token else {}),
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
        )
        self.limits: dict[str, str] = {}

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        missing_ok: bool = False,
    ) -> Any:
        for attempt in range(3):
            try:
                response = self.client.request(method, path, json=body)
            except httpx.HTTPError as exc:
                raise DevPilotError("GitHub could not be reached. No merge was attempted.") from exc
            self.limits = {
                k: v for k, v in response.headers.items() if k.startswith("x-ratelimit-")
            }
            if response.status_code in {403, 429} and (
                response.headers.get("x-ratelimit-remaining") == "0" or response.status_code == 429
            ):
                try:
                    delay = float(response.headers.get("retry-after", "2"))
                except ValueError:
                    delay = 2
                if delay > 10 or attempt == 2:
                    raise DevPilotError(
                        "GitHub rate limit exhausted. Wait for its reset, then retry."
                    )
                time.sleep(max(1, delay))
                continue
            if response.status_code == 404 and missing_ok and method == "GET":
                return None
            if response.status_code >= 400:
                raise DevPilotError(
                    f"GitHub returned HTTP {response.status_code}. Check repository permissions "
                    "and whether the run's branch or PR already exists."
                )
            try:
                return response.json()
            except ValueError as exc:
                raise DevPilotError("GitHub returned an invalid response.") from exc
        raise DevPilotError("GitHub rate limit retry budget exhausted.")

    def close(self) -> None:
        self.client.close()
