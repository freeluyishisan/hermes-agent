import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from agent.provider_client_identity import (
    ZAI_OPENCODE_USER_AGENT,
    is_zai_endpoint,
    strip_stainless_headers,
)
from run_agent import AIAgent

_ZAI_SESSION_HEADERS = ("x-session-affinity", "X-Session-Id", "x-parent-session-id")


@pytest.fixture(autouse=True)
def _isolate_hermes_home(tmp_path, monkeypatch):
    from gateway.session_context import _UNSET, _VAR_MAP

    for var in _VAR_MAP.values():
        var.set(_UNSET)
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text("model:\n  default: glm-5.2\n")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
    yield
    monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
    for var in _VAR_MAP.values():
        var.set(_UNSET)


def _close_forwarded_http_client(mock_openai) -> None:
    http_client = (mock_openai.call_args.kwargs or {}).get("http_client")
    if http_client is not None:
        http_client.close()


def _assert_no_zai_session_headers(headers) -> None:
    for name in _ZAI_SESSION_HEADERS:
        assert name not in headers


def _make_agent(base_url: str, **kwargs) -> AIAgent:
    return AIAgent(
        api_key="zai-test-key",
        base_url=base_url,
        provider="zai",
        model="glm-5.2",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        **kwargs,
    )


@patch("run_agent.OpenAI")
def test_api_zai_coding_endpoint_gets_opencode_identity(mock_openai):
    mock_openai.return_value = MagicMock()

    agent = _make_agent(
        "https://api.z.ai/api/coding/paas/v4",
        session_id="sess-main",
        parent_session_id="sess-parent",
    )

    headers = agent._client_kwargs["default_headers"]
    assert headers["User-Agent"] == ZAI_OPENCODE_USER_AGENT
    _assert_no_zai_session_headers(headers)
    assert isinstance(mock_openai.call_args.kwargs["http_client"], httpx.Client)
    _close_forwarded_http_client(mock_openai)


@patch("run_agent.OpenAI")
def test_open_bigmodel_coding_endpoint_gets_opencode_identity(mock_openai):
    mock_openai.return_value = MagicMock()

    agent = _make_agent(
        "https://open.bigmodel.cn/api/coding/paas/v4",
        session_id="sess-cn",
    )

    headers = agent._client_kwargs["default_headers"]
    assert headers["User-Agent"] == ZAI_OPENCODE_USER_AGENT
    _assert_no_zai_session_headers(headers)
    _close_forwarded_http_client(mock_openai)


@patch("run_agent.OpenAI")
def test_non_zai_provider_headers_remain_unchanged(mock_openai):
    mock_openai.return_value = MagicMock()

    agent = AIAgent(
        api_key="test-key",
        base_url="https://api.example.com/v1",
        provider="custom",
        model="custom-model",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
    )

    assert "default_headers" not in agent._client_kwargs
    assert "http_client" in mock_openai.call_args.kwargs
    _close_forwarded_http_client(mock_openai)


@patch("run_agent.OpenAI")
def test_user_default_headers_override_zai_opencode_user_agent(mock_openai):
    mock_openai.return_value = MagicMock()

    with patch("hermes_cli.config.load_config", return_value={
        "model": {"default_headers": {"user-agent": "curl/8.7.1", "X-Extra": "1"}},
    }):
        agent = _make_agent("https://api.z.ai/api/coding/paas/v4")

    headers = agent._client_kwargs["default_headers"]
    assert headers["User-Agent"] == "curl/8.7.1"
    assert "user-agent" not in headers
    assert headers["X-Extra"] == "1"
    _assert_no_zai_session_headers(headers)
    _close_forwarded_http_client(mock_openai)


def test_is_zai_endpoint_is_exact_host_scoped():
    assert is_zai_endpoint("https://api.z.ai/api/coding/paas/v4") is True
    assert is_zai_endpoint("https://open.bigmodel.cn/api/coding/paas/v4") is True
    assert is_zai_endpoint("https://proxy.example.test/api.z.ai/api/paas/v4") is False
    assert is_zai_endpoint("https://api.z.ai.example.test/api/paas/v4") is False


def test_stainless_strip_hook_removes_all_sdk_fingerprint_headers():
    request = httpx.Request(
        "POST",
        "https://api.z.ai/api/coding/paas/v4/chat/completions",
        headers={
            "X-Stainless-Lang": "python",
            "x-stainless-package-version": "2.24.0",
            "X-Stainless-Runtime": "CPython",
            "X-Other": "keep",
        },
    )

    strip_stainless_headers(request)

    assert "X-Stainless-Lang" not in request.headers
    assert "x-stainless-package-version" not in request.headers
    assert "X-Stainless-Runtime" not in request.headers
    assert request.headers["X-Other"] == "keep"


def test_auxiliary_openai_client_applies_zai_identity(monkeypatch):
    from gateway.session_context import set_session_vars

    monkeypatch.setenv("HERMES_SESSION_ID", "stale-env-session")
    set_session_vars(session_id="sess-aux")
    monkeypatch.setenv("ZAI_API_KEY", "zai-key")

    with patch("hermes_cli.auth.detect_zai_endpoint", return_value=None), \
         patch("agent.auxiliary_client.OpenAI") as mock_openai:
        mock_openai.return_value = SimpleNamespace(
            api_key="zai-key",
            base_url="https://api.z.ai/api/coding/paas/v4",
        )
        from agent.auxiliary_client import resolve_provider_client

        client, model = resolve_provider_client(
            "zai",
            "glm-5.2",
            explicit_api_key="zai-key",
            explicit_base_url="https://api.z.ai/api/coding/paas/v4",
        )

    assert client is mock_openai.return_value
    assert model == "glm-5.2"
    kwargs = mock_openai.call_args.kwargs
    assert kwargs["default_headers"]["User-Agent"] == ZAI_OPENCODE_USER_AGENT
    _assert_no_zai_session_headers(kwargs["default_headers"])
    assert isinstance(kwargs["http_client"], httpx.Client)
    request = httpx.Request(
        "POST",
        "https://api.z.ai/api/coding/paas/v4/chat/completions",
        headers={"X-Stainless-Lang": "python"},
    )
    kwargs["http_client"].event_hooks["request"][0](request)
    _assert_no_zai_session_headers(request.headers)
    assert "X-Stainless-Lang" not in request.headers
    kwargs["http_client"].close()


def test_cached_zai_http_client_does_not_emit_task_session(monkeypatch):
    from gateway.session_context import set_session_vars

    monkeypatch.setenv("HERMES_SESSION_ID", "stale-env-session")
    set_session_vars(session_id="sess-one")
    monkeypatch.setenv("ZAI_API_KEY", "zai-key")

    with patch("hermes_cli.auth.detect_zai_endpoint", return_value=None), \
         patch("agent.auxiliary_client.OpenAI") as mock_openai:
        mock_openai.return_value = SimpleNamespace(
            api_key="zai-key",
            base_url="https://api.z.ai/api/coding/paas/v4",
        )
        from agent.auxiliary_client import resolve_provider_client

        resolve_provider_client(
            "zai",
            "glm-5.2",
            explicit_api_key="zai-key",
            explicit_base_url="https://api.z.ai/api/coding/paas/v4",
        )

    http_client = mock_openai.call_args.kwargs["http_client"]
    hook = http_client.event_hooks["request"][0]
    request_one = httpx.Request(
        "POST",
        "https://api.z.ai/api/coding/paas/v4/chat/completions",
    )
    hook(request_one)
    _assert_no_zai_session_headers(request_one.headers)

    set_session_vars(session_id="sess-two")
    request_two = httpx.Request(
        "POST",
        "https://api.z.ai/api/coding/paas/v4/chat/completions",
    )
    hook(request_two)
    _assert_no_zai_session_headers(request_two.headers)
    http_client.close()


def test_zai_request_hook_strips_stainless_without_adding_session_headers(monkeypatch):
    from agent.provider_client_identity import build_zai_sync_http_client
    from gateway.session_context import set_session_vars

    monkeypatch.setenv("HERMES_SESSION_ID", "stale-env-session")
    set_session_vars(session_id="fresh-session")

    http_client = build_zai_sync_http_client()
    request = httpx.Request(
        "POST",
        "https://api.z.ai/api/coding/paas/v4/chat/completions",
        headers={"X-Stainless-Lang": "python"},
    )

    http_client.event_hooks["request"][0](request)

    _assert_no_zai_session_headers(request.headers)
    assert "X-Stainless-Lang" not in request.headers
    http_client.close()


def test_auxiliary_async_openai_client_applies_zai_identity(monkeypatch):
    from gateway.session_context import set_session_vars

    monkeypatch.setenv("HERMES_SESSION_ID", "stale-env-session")
    set_session_vars(session_id="sess-async")
    monkeypatch.setenv("ZAI_API_KEY", "zai-key")

    sync_client = SimpleNamespace(
        api_key="zai-key",
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
    )
    async_client = MagicMock()
    with patch("hermes_cli.auth.detect_zai_endpoint", return_value=None), \
         patch("agent.auxiliary_client.OpenAI", return_value=sync_client), \
         patch("openai.AsyncOpenAI", return_value=async_client) as mock_async_openai:
        from agent.auxiliary_client import resolve_provider_client

        client, model = resolve_provider_client(
            "zai",
            "glm-5.2",
            async_mode=True,
            explicit_api_key="zai-key",
            explicit_base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        )

    assert client is async_client
    assert model == "glm-5.2"
    kwargs = mock_async_openai.call_args.kwargs
    assert kwargs["default_headers"]["User-Agent"] == ZAI_OPENCODE_USER_AGENT
    _assert_no_zai_session_headers(kwargs["default_headers"])
    assert isinstance(kwargs["http_client"], httpx.AsyncClient)
    request = httpx.Request(
        "POST",
        "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions",
        headers={"X-Stainless-Runtime": "CPython", "X-Other": "keep"},
    )
    asyncio.run(kwargs["http_client"].event_hooks["request"][0](request))
    assert "X-Stainless-Runtime" not in request.headers
    assert request.headers["X-Other"] == "keep"
    _assert_no_zai_session_headers(request.headers)
    asyncio.run(kwargs["http_client"].aclose())


@pytest.mark.parametrize(
    "base_url",
    [
        "https://api.z.ai/api/anthropic",
        "https://open.bigmodel.cn/api/anthropic",
    ],
)
def test_zai_anthropic_client_preserves_betas_and_strips_stainless(base_url):
    from agent.anthropic_adapter import build_anthropic_client
    from gateway.session_context import set_session_vars

    with patch("agent.anthropic_adapter._anthropic_sdk") as mock_sdk:
        build_anthropic_client(
            "zai-key",
            base_url=base_url,
        )

    kwargs = mock_sdk.Anthropic.call_args.kwargs
    assert kwargs["api_key"] == "zai-key"
    assert "auth_token" not in kwargs
    headers = kwargs["default_headers"]
    assert headers["User-Agent"] == ZAI_OPENCODE_USER_AGENT
    _assert_no_zai_session_headers(headers)
    assert "interleaved-thinking-2025-05-14" in headers["anthropic-beta"]
    assert "fine-grained-tool-streaming-2025-05-14" in headers["anthropic-beta"]

    set_session_vars(session_id="sess-anthropic")
    request = httpx.Request(
        "POST",
        "https://api.z.ai/api/anthropic/v1/messages",
        headers={"X-Stainless-Arch": "arm64", "anthropic-beta": headers["anthropic-beta"]},
    )
    hook = kwargs["http_client"].event_hooks["request"][0]
    hook(request)
    assert "X-Stainless-Arch" not in request.headers
    _assert_no_zai_session_headers(request.headers)
    assert request.headers["anthropic-beta"] == headers["anthropic-beta"]
    kwargs["http_client"].close()
