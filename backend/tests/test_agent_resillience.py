import asyncio
import types

import groq
import httpx
import pytest

from app.agents import base_agent_loop as loop


def err(cls, status, message="boom"):
    request = httpx.Request("POST", "http://test")
    return cls(message, response=httpx.Response(status, request=request), body=None)


def final(text):
    message = types.SimpleNamespace(content=text, tool_calls=None)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


class FakeClient:
    """Stands in for the Groq client. behaviours maps a model name to a
    function returning either a response or an exception to raise."""

    def __init__(self, behaviours):
        self.behaviours = behaviours
        self.calls = []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs["model"])
        result = self.behaviours[kwargs["model"]]()
        if isinstance(result, Exception):
            raise result
        return result


def run(fake, monkeypatch):
    async def no_sleep(_seconds):
        pass

    monkeypatch.setattr(loop, "get_client", lambda: fake)
    monkeypatch.setattr(loop, "model_chain", lambda: ["model-a", "model-b"])
    monkeypatch.setattr(loop, "_sleep", no_sleep)
    return asyncio.run(loop.run_agent("system", "hello", [], {}))


def test_rate_limit_falls_back_to_next_model(monkeypatch):
    fake = FakeClient({"model-a": lambda: err(groq.RateLimitError, 429), "model-b": lambda: final("ok")})
    assert run(fake, monkeypatch) == "ok"
    assert fake.calls == ["model-a", "model-b"]


def test_missing_model_falls_back_to_next_model(monkeypatch):
    fake = FakeClient({"model-a": lambda: err(groq.NotFoundError, 404), "model-b": lambda: final("ok")})
    assert run(fake, monkeypatch) == "ok"


def test_server_errors_are_retried_then_fall_back(monkeypatch):
    fake = FakeClient({"model-a": lambda: err(groq.InternalServerError, 500), "model-b": lambda: final("ok")})
    assert run(fake, monkeypatch) == "ok"
    assert fake.calls == ["model-a"] * (loop.MAX_SERVER_RETRIES + 1) + ["model-b"]


def test_all_models_failing_raises(monkeypatch):
    fake = FakeClient({
        "model-a": lambda: err(groq.RateLimitError, 429),
        "model-b": lambda: err(groq.RateLimitError, 429),
    })
    with pytest.raises(RuntimeError):
        run(fake, monkeypatch)


def test_repeated_malformed_tool_calls_switch_model(monkeypatch):
    bad = lambda: err(groq.BadRequestError, 400, "tool_use_failed: attempted to call tool 'json'")
    fake = FakeClient({"model-a": bad, "model-b": lambda: final("ok")})
    assert run(fake, monkeypatch) == "ok"
    assert fake.calls == ["model-a"] * (loop.MAX_MALFORMED_RETRIES + 1) + ["model-b"]


def test_other_bad_requests_are_not_swallowed(monkeypatch):
    fake = FakeClient({"model-a": lambda: err(groq.BadRequestError, 400, "invalid schema"), "model-b": lambda: final("ok")})
    with pytest.raises(groq.BadRequestError):
        run(fake, monkeypatch)

def test_decommissioned_model_falls_back(monkeypatch):
    fake = FakeClient({
        "model-a": lambda: err(groq.BadRequestError, 400, "model_decommissioned"),
        "model-b": lambda: final("ok"),
    })
    assert run(fake, monkeypatch) == "ok"