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
    'f"⏩ Steered into current run',   # final-review fix
    # Batch B literals
    '"Gateway is restarting',         # shutdown_restarting
    '"Gateway is shutting down',      # shutdown_shutting_down
    'f"✗ Failed to send reply to update process',   # steer_update_send_failed
    '"Queued for next turn."',        # queued_next_turn_simple
    '"Usage: /steer <prompt>"',       # steer_usage
    '"Agent is still starting',       # steer_agent_starting
    'f"⚠️ Steer failed:',             # steer_failed
    '"Steer rejected (empty prompt)', # steer_rejected
    '"No active agent',               # steer_no_agent
    '"Command returned no output."',  # quick_cmd_no_output
    '"Quick command timed out',       # quick_cmd_timeout
    '"Could not determine chat ID."', # topic_no_chat_id
    '"Multi-session topic mode is not currently enabled', # topic_not_enabled
    '"Session not found:',            # session_not_found (raw string form)
    '"That session is not a Telegram', # session_not_telegram
    '"That session does not belong',  # session_wrong_user
    '"That session is already linked', # session_already_linked
    'f"Session restored:',            # session_restored
    'f"🟡 /{command} cancelled.',     # command_cancelled
    '"Suggestions command failed:',   # suggestions_failed
    'no provider credentials configured', # bg_task_no_creds
    'f"❌ Background task {task_id} failed: {e}"', # bg_task_failed
    'f"⛔ /{canonical_cmd} is admin-only here.', # admin_only_*
    '"You can run: "',                # admin_only_with_allowed
])
def test_english_literal_not_unwrapped(literal):
    assert literal not in _RUN_PY, f"unwrapped English literal still present: {literal!r}"


# ---- Batch B: spot-check that Russian translations round-trip correctly ----

@pytest.mark.parametrize("key,kwargs", [
    ("gateway.busy_queued_drain", {"gerund": "processing"}),
    ("gateway.busy_not_accepting_turn", {"gerund": "processing"}),
    ("gateway.busy_not_accepting_work", {"gerund": "processing"}),
    ("gateway.shutdown_restarting", {}),
    ("gateway.shutdown_shutting_down", {}),
    ("gateway.steer_update_send_failed", {"error": "oops"}),
    ("gateway.steer_update_sent", {"label": "label"}),
    ("gateway.queued_next_turn_simple", {}),
    ("gateway.queued_next_turn_depth", {"depth": 3}),
    ("gateway.steer_usage", {}),
    ("gateway.steer_agent_starting", {}),
    ("gateway.steer_failed", {"error": "boom"}),
    ("gateway.steer_queued", {"preview": "do something"}),
    ("gateway.steer_rejected", {}),
    ("gateway.steer_no_agent", {}),
    ("gateway.steer_usage_no_agent", {}),
    ("gateway.agent_running_switch_model", {}),
    ("gateway.agent_running_change_runtime", {}),
    ("gateway.agent_running_goal", {}),
    ("gateway.agent_running_cant_run_cmd", {"name": "stop"}),
    ("gateway.force_stopped_starting", {}),
    ("gateway.command_blocked_hook", {"command": "eval"}),
    ("gateway.quick_cmd_no_output", {}),
    ("gateway.quick_cmd_timeout", {}),
    ("gateway.quick_cmd_error", {"error": "err"}),
    ("gateway.quick_cmd_no_command", {"command": "foo"}),
    ("gateway.quick_cmd_no_target", {"command": "foo"}),
    ("gateway.quick_cmd_unsupported_type", {"command": "foo"}),
    ("gateway.api_hint_auth", {}),
    ("gateway.api_hint_billing", {}),
    ("gateway.api_hint_plan_limit_hours", {"hours": 5}),
    ("gateway.api_hint_plan_limit", {}),
    ("gateway.api_hint_rate_limited", {}),
    ("gateway.api_hint_overloaded", {}),
    ("gateway.api_hint_rejected", {}),
    ("gateway.api_error_generic", {"error_type": "500", "error_detail": "d", "status_hint": "h"}),
    ("gateway.model_no_response_tool_results", {}),
    ("gateway.session_auto_reset", {}),
    ("gateway.voice_no_stt", {}),
    ("gateway.voice_no_stt_setup_suffix", {}),
    ("gateway.compress_aborted", {"err": "oops"}),
    ("gateway.compress_aux_model_failed", {"model": "gpt-4o", "err": "err"}),
    ("gateway.admin_only_with_allowed", {"cmd": "reset", "allowed_list": "/help"}),
    ("gateway.admin_only_no_commands", {"cmd": "reset"}),
    ("gateway.suggestions_failed", {"error": "boom"}),
    ("gateway.bg_task_no_creds", {"task_id": "abc123"}),
    ("gateway.bg_task_complete", {"preview": "do something"}),
    ("gateway.bg_task_failed", {"task_id": "abc123", "error": "boom"}),
    ("gateway.topic_no_chat_id", {}),
    ("gateway.topic_not_enabled", {}),
    ("gateway.topic_disabled", {}),
    ("gateway.topic_no_unlinked_sessions", {}),
    ("gateway.topic_restore_instructions", {}),
    ("gateway.session_not_found", {"session_id": "abc"}),
    ("gateway.session_not_telegram", {}),
    ("gateway.session_wrong_user", {}),
    ("gateway.session_already_linked", {}),
    ("gateway.session_restored", {"title": "My Session"}),
    ("gateway.session_restored_last_msg", {"content": "hello"}),
    ("gateway.command_cancelled", {"command": "reset"}),
])
def test_batchB_key_resolves_in_russian(key, kwargs):
    """Each Batch B key must resolve (not raise KeyError) in Russian."""
    result = i18n.t(key, lang="ru", **kwargs)
    assert isinstance(result, str) and result, f"Empty or non-string result for {key!r}"
