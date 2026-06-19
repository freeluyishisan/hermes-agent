"""Localization of gateway system messages wrapped via t() (issue #29846)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent import i18n
from gateway import run as gw


@pytest.fixture(autouse=True)
def _ru(monkeypatch):
    # Force Russian and a clean cache for every test.
    monkeypatch.setenv("HERMES_LANGUAGE", "ru")
    i18n.reset_language_cache()
    yield
    i18n.reset_language_cache()


@pytest.mark.parametrize("text,key", [
    ("invalid api key", "gateway.provider_auth_failed"),
    ("request blocked: policy violation", "gateway.provider_rejected"),
    ("HTTP 429 rate limit", "gateway.provider_rate_limited"),
    ("totally unrecognized boom", "gateway.provider_failed"),
])
def test_provider_error_reply_localized(text, key):
    assert gw._gateway_provider_error_reply(text) == i18n.t(key, lang="ru")


def test_session_too_large_localized():
    out = gw._normalize_empty_agent_response(
        {"failed": True, "error": "context window exceeded"}, "", history_len=0)
    assert out == i18n.t("gateway.session_too_large", lang="ru")


def test_request_failed_localized():
    out = gw._normalize_empty_agent_response(
        {"failed": True, "error": "boom"}, "", history_len=0)
    assert out == i18n.t("gateway.request_failed", lang="ru", error="boom")


def test_processing_stopped_localized():
    out = gw._normalize_empty_agent_response(
        {"api_calls": 1, "partial": True, "error": "midway"}, "")
    assert out == i18n.t("gateway.processing_stopped", lang="ru", error="midway")


def test_empty_response_localized():
    out = gw._normalize_empty_agent_response({"api_calls": 2}, "")
    assert out == i18n.t("gateway.empty_response", lang="ru")


_RUN_PY = Path(gw.__file__).read_text(encoding="utf-8")

# Exact English literals that must no longer appear unwrapped in gateway/run.py
# (they now live only in locales/*.yaml). Tasks 8-10 will append their literals.
@pytest.mark.parametrize("literal", [
    '"(No response generated)"',   # Task 7
    '⏳ Subagent working',            # Task 8
    '⏳ Queued for the next turn',    # Task 8
    '⚡ Interrupting current task',   # Task 8
    '♻ Gateway restarted successfully. Your session continues.',  # Task 9
    '♻️ Gateway online — Hermes is back and ready.',              # Task 9
    'f"⏳ Working — ',                # Task 10
    'f"⚠️ No activity for ',          # Task 10
])
def test_english_literal_not_unwrapped(literal):
    assert literal not in _RUN_PY, f"unwrapped English literal still present: {literal!r}"
