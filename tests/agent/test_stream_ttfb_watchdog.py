"""Regression tests for the generic streaming first-event watchdog."""

from __future__ import annotations

import sys
import time
import types
from types import SimpleNamespace
from unittest.mock import patch

import httpx

# Stub optional heavy imports so run_agent imports cleanly in isolation.
sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())


def _make_agent(tmp_path, monkeypatch, *, fallback_model):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / ".env").write_text("", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("{}\n", encoding="utf-8")

    from run_agent import AIAgent

    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key",
            provider="openrouter",
            base_url="https://integrate.api.nvidia.com/v1",
            model="deepseek-v4",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=fallback_model,
            platform="cli",
        )

    agent.api_mode = "chat_completions"
    agent._interrupt_requested = False
    monkeypatch.setattr(agent, "_emit_status", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_buffer_status", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_replace_primary_openai_client", lambda *a, **k: None)
    return agent


def _chunk(*, content=None, finish_reason=None):
    delta = SimpleNamespace(
        content=content,
        reasoning_content=None,
        reasoning=None,
        tool_calls=None,
    )
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model="deepseek-v4", usage=None)


class _HangingStream:
    response = None

    def __init__(self, stop_flag):
        self._stop_flag = stop_flag

    def __iter__(self):
        deadline = time.time() + 30
        while time.time() < deadline and not self._stop_flag["flag"]:
            time.sleep(0.02)
        raise httpx.RemoteProtocolError("connection closed")


class _DelayedFirstEventStream:
    response = None

    def __init__(self, delay_seconds):
        self._delay_seconds = delay_seconds

    def __iter__(self):
        time.sleep(self._delay_seconds)
        yield _chunk(content="hello")
        yield _chunk(finish_reason="stop")


class _EarlyKeepaliveThenContentStream:
    response = None

    def __init__(self, post_keepalive_delay):
        self._post_keepalive_delay = post_keepalive_delay

    def __iter__(self):
        yield SimpleNamespace(choices=[], model="deepseek-v4", usage=None)
        time.sleep(self._post_keepalive_delay)
        yield _chunk(content="hello")
        yield _chunk(finish_reason="stop")


def _install_stream_clients(agent, stream_factories):
    closes = []
    streams = iter(stream_factories)

    def _make_client(**kwargs):
        stream = next(streams)
        return SimpleNamespace(
            _stream=stream,
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_kwargs: stream)
            ),
        )

    def _close(client, reason=None):
        closes.append(reason)
        stop_flag = getattr(getattr(client, "_stream", None), "_stop_flag", None)
        if stop_flag is not None:
            stop_flag["flag"] = True

    agent._create_request_openai_client = _make_client
    agent._abort_request_openai_client = _close
    agent._close_request_openai_client = _close
    return closes


def test_generic_stream_ttfb_kills_hanging_attempt_and_retries(
    tmp_path, monkeypatch
):
    agent = _make_agent(
        tmp_path,
        monkeypatch,
        fallback_model=[{"provider": "openrouter", "model": "gemma4:31b"}],
    )
    monkeypatch.setenv("HERMES_STREAM_TTFB_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("HERMES_STREAM_RETRIES", "1")

    stop_flag = {"flag": False}
    closes = _install_stream_clients(
        agent,
        [_HangingStream(stop_flag), _DelayedFirstEventStream(0.05)],
    )

    t0 = time.time()
    resp = agent._interruptible_streaming_api_call(
        {"model": agent.model, "messages": []}
    )
    elapsed = time.time() - t0

    assert resp.choices[0].message.content == "hello"
    assert "stream_ttfb_kill" in closes
    assert elapsed < 15, f"generic stream TTFB watchdog took {elapsed:.1f}s"


def test_generic_stream_ttfb_stays_disabled_without_fallback(
    tmp_path, monkeypatch
):
    agent = _make_agent(tmp_path, monkeypatch, fallback_model=None)
    monkeypatch.setenv("HERMES_STREAM_TTFB_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("HERMES_STREAM_RETRIES", "0")

    closes = _install_stream_clients(agent, [_DelayedFirstEventStream(1.3)])

    resp = agent._interruptible_streaming_api_call(
        {"model": agent.model, "messages": []}
    )

    assert resp.choices[0].message.content == "hello"
    assert "stream_ttfb_kill" not in closes


def test_generic_stream_ttfb_does_not_kill_after_first_event(
    tmp_path, monkeypatch
):
    agent = _make_agent(
        tmp_path,
        monkeypatch,
        fallback_model=[{"provider": "openrouter", "model": "gemma4:31b"}],
    )
    monkeypatch.setenv("HERMES_STREAM_TTFB_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("HERMES_STREAM_RETRIES", "0")

    closes = _install_stream_clients(
        agent, [_EarlyKeepaliveThenContentStream(1.3)]
    )

    resp = agent._interruptible_streaming_api_call(
        {"model": agent.model, "messages": []}
    )

    assert resp.choices[0].message.content == "hello"
    assert "stream_ttfb_kill" not in closes
