import hashlib
import random
import threading
import time
from collections.abc import Callable
from typing import Any, Protocol

import httpx

from app.errors import DevPilotError, RunCancelled, RunTimeout

REQUEST_QUEUE = threading.Lock()


class LLM(Protocol):
    model: str

    def complete(self, system: str, prompt: str, deadline: float) -> str: ...


class GroqClient:
    def __init__(
        self,
        key: str,
        model: str,
        waiting: Callable[[str], None],
        client: httpx.Client | None = None,
        cancel: threading.Event | None = None,
    ) -> None:
        self.model = model
        self.waiting = waiting
        self.client = client or httpx.Client(
            base_url="https://api.groq.com/openai/v1/",
            headers={"Authorization": f"Bearer {key}"},
            timeout=45,
        )
        self._queue = REQUEST_QUEUE
        self.cancel = cancel or threading.Event()
        self._cache: dict[str, str] = {}
        self.limits: dict[str, str] = {}

    def close(self) -> None:
        self.client.close()

    def preflight(self) -> None:
        try:
            response = self.client.get("models")
            response.raise_for_status()
            available = {m["id"] for m in response.json()["data"]}
            if self.model not in available:
                raise DevPilotError(
                    f"GROQ_MODEL '{self.model}' is unavailable. "
                    "Run devpilot models and update .env."
                )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise DevPilotError(
                "Cannot check Groq models. Verify GROQ_API_KEY and your connection."
            ) from exc

    def models(self) -> list[str]:
        try:
            response = self.client.get("models")
            response.raise_for_status()
            return sorted(m["id"] for m in response.json()["data"])
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise DevPilotError(
                "Cannot list Groq models. Check GROQ_API_KEY and network access."
            ) from exc

    def complete(self, system: str, prompt: str, deadline: float) -> str:
        announced = False
        while True:
            if self.cancel.is_set():
                raise RunCancelled("Model request cancelled by the operator.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RunTimeout("Run timed out waiting for the Groq request queue.")
            if self._queue.acquire(timeout=min(0.2, remaining)):
                break
            if not announced:
                self.waiting("Waiting in the Groq request queue.")
                announced = True
        try:
            return self._complete(system, prompt, deadline)
        finally:
            self._queue.release()

    def _complete(self, system: str, prompt: str, deadline: float) -> str:
        key = hashlib.sha256((self.model + system + prompt).encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]
        for attempt in range(5):
            if self.cancel.is_set():
                raise RunCancelled("Model request cancelled by the operator.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RunTimeout("Run timed out waiting for Groq.")
            try:
                response = self.client.post(
                    "chat/completions",
                    timeout=min(45, remaining),
                    json={
                        "model": self.model,
                        "temperature": 0,
                        "max_completion_tokens": 4096,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                self.limits = {
                    k: v for k, v in response.headers.items() if k.startswith("x-ratelimit-")
                }
                if response.status_code == 429 or response.status_code >= 500:
                    self._backoff(
                        attempt,
                        response.headers.get("retry-after"),
                        deadline,
                        response.status_code == 429,
                    )
                    continue
                response.raise_for_status()
                body: Any = response.json()
                choice = body["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise DevPilotError(
                        "Groq response was incomplete. Use a smaller issue/context."
                    )
                content = choice["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("empty completion")
                if len(self._cache) >= 32:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[key] = content
                return content
            except (httpx.TimeoutException, httpx.NetworkError):
                self._backoff(attempt, None, deadline)
            except (httpx.HTTPStatusError, ValueError, KeyError, IndexError) as exc:
                raise DevPilotError(
                    "Groq request failed. Check the key, model, and free-tier limits."
                ) from exc
        raise DevPilotError(
            "Groq is still rate limited or unavailable after 5 requests. Retry later."
        )

    def _backoff(
        self, attempt: int, retry_after: str | None, deadline: float, rate_limited: bool = False
    ) -> None:
        try:
            delay = max(1, float(retry_after)) if retry_after else 2**attempt + random.random()
        except ValueError:
            delay = 2**attempt + random.random()
        if delay >= deadline - time.monotonic():
            raise RunTimeout("Groq requested a wait beyond this run's time budget. Retry later.")
        reason = "rate limited" if rate_limited else "unavailable"
        self.waiting(f"Groq {reason}; waiting {delay:.1f}s (retry {attempt + 1}/5).")
        until = time.monotonic() + delay
        while time.monotonic() < until:
            if self.cancel.is_set():
                raise RunCancelled("Cancelled while waiting for the Groq rate limit.")
            time.sleep(min(1, until - time.monotonic()))
