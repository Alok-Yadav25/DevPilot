import time

import httpx
import pytest
from app.agent.llm import GroqClient
from app.errors import DevPilotError, RunTimeout


def test_models_are_verified_and_completion_is_cached() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("models"):
            return httpx.Response(200, json={"data": [{"id": "current-model"}]})
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "a patch"}}]}
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.com/"
    ) as http:
        llm = GroqClient("key", "current-model", lambda _: None, http)
        llm.preflight()
        assert llm.complete("system", "issue", time.monotonic() + 10) == "a patch"
        assert llm.complete("system", "issue", time.monotonic() + 10) == "a patch"
        assert calls == ["/models", "/chat/completions"]


def test_stale_model_is_actionable() -> None:
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": []})),
            base_url="https://api.groq.com/",
        ) as http,
        pytest.raises(DevPilotError, match="devpilot models"),
    ):
        GroqClient("key", "retired-model", lambda _: None, http).preflight()


def test_rate_limit_never_waits_past_deadline() -> None:
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(429, headers={"retry-after": "1000"})
            ),
            base_url="https://api.groq.com/",
        ) as http,
        pytest.raises(RunTimeout),
    ):
        GroqClient("key", "model", lambda _: None, http).complete("s", "p", time.monotonic() + 1)


def test_429_retries_and_exposes_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    waiting: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"retry-after": "1"})
        return httpx.Response(
            200,
            headers={"x-ratelimit-remaining-requests": "2"},
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "ok"}}],
            },
        )

    monkeypatch.setattr("app.agent.llm.time.sleep", lambda _: None)
    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.groq.com/"
    ) as http:
        llm = GroqClient("key", "model", waiting.append, http)
        assert llm.complete("s", "p", time.monotonic() + 10) == "ok"
        assert calls == 2 and waiting
        assert llm.limits["x-ratelimit-remaining-requests"] == "2"
