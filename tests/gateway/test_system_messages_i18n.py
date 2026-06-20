"""Localization of gateway system messages wrapped via t() (issue #29846)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent import i18n
from gateway import run as gw
from gateway import slash_commands as sc


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
_SLASH_COMMANDS_PY = Path(sc.__file__).read_text(encoding="utf-8")

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


# ---- Batch C: /whoami, /platform, codex-runtime, /subgoal, /memory, /skills ----

@pytest.mark.parametrize("literal", [
    # /whoami
    '"**You** — {platform} ({scope})',       # whoami_unrestricted / whoami_admin / whoami_user
    '"Tier: unrestricted',                    # whoami_unrestricted
    '"Tier: user',                            # whoami_user
    '"Slash commands: all available"',        # whoami_unrestricted / whoami_admin
    # /platform
    '"**Gateway platforms**"',                # platform_list_header
    '"Connected: " +',                        # platform_connected
    '"Connected: (none)"',                    # platform_connected_none
    '"Failed/paused: (none)"',                # platform_failed_none
    'f"Usage: /platform {action} <name>"',   # platform_usage
    'f"Unknown platform: {target}"',         # platform_unknown
    '"Usage: /platform <list|pause|resume>', # platform_usage_full
    # codex-runtime
    '"❌ " + "\\n❌ "',                        # codex_runtime_errors (old form)
    'f"❌ Could not load config: {exc}"',     # codex_runtime_config_error
    # /subgoal
    '"No active goal. Set one with /goal <text>."',   # subgoal_no_active_goal
    '"Usage: /subgoal remove <n>"',                   # subgoal_remove_usage
    '"/subgoal remove: <n> must be an integer',       # subgoal_remove_not_integer
    'f"✓ Removed subgoal {idx}: {removed}"',          # subgoal_removed
    'f"✓ Cleared {prev} subgoal',                     # subgoal_cleared_one/many
    '"No subgoals to clear."',                         # subgoal_none_to_clear
    'f"✓ Added subgoal {idx}: {text}"',                # subgoal_added
    # /memory & /skills
    '"Unknown /memory subcommand.',                    # memory_unknown_subcommand
    '"Skill write approval is off',                    # skills_write_approval_off
    '"Unknown /skills subcommand on this platform.',   # skills_unknown_subcommand
    '"\\n… (truncated — full diff in "',               # skills_diff_truncated
])
def test_batchC_literal_not_unwrapped_in_slash_commands(literal):
    assert literal not in _SLASH_COMMANDS_PY, (
        f"unwrapped English literal still present in slash_commands.py: {literal!r}"
    )


@pytest.mark.parametrize("key,kwargs", [
    # /whoami
    ("gateway.whoami_unrestricted", {"platform": "telegram", "scope": "DM", "user_id": "123"}),
    ("gateway.whoami_admin", {"platform": "telegram", "scope": "DM", "user_id": "123"}),
    ("gateway.whoami_user", {"platform": "telegram", "scope": "DM", "user_id": "123", "runnable_str": "/help, /whoami"}),
    # /platform
    ("gateway.platform_list_header", {}),
    ("gateway.platform_connected", {"platforms": "telegram, discord"}),
    ("gateway.platform_connected_none", {}),
    ("gateway.platform_failed_paused", {"platform": "discord", "reason": "paused"}),
    ("gateway.platform_retrying", {"platform": "discord", "attempts": 3}),
    ("gateway.platform_failed_none", {}),
    ("gateway.platform_usage", {"action": "pause"}),
    ("gateway.platform_unknown", {"target": "xyz"}),
    ("gateway.platform_not_in_queue", {"platform": "discord"}),
    ("gateway.platform_already_paused", {"platform": "discord"}),
    ("gateway.platform_paused_ok", {"platform": "discord"}),
    ("gateway.platform_not_in_queue_resume", {"platform": "discord"}),
    ("gateway.platform_already_retrying", {"platform": "discord"}),
    ("gateway.platform_resumed_ok", {"platform": "discord"}),
    ("gateway.platform_usage_full", {}),
    # codex-runtime & model
    ("gateway.model_expensive_warning", {"warning_message": "This model costs $$$", "prefix": "!"}),
    ("gateway.codex_runtime_errors", {"errors": "bad arg"}),
    ("gateway.codex_runtime_config_error", {"exc": "FileNotFoundError"}),
    ("gateway.codex_runtime_result", {"prefix": "✓", "message": "switched to auto"}),
    # /subgoal
    ("gateway.subgoal_no_active_goal", {}),
    ("gateway.subgoal_remove_usage", {}),
    ("gateway.subgoal_remove_not_integer", {}),
    ("gateway.subgoal_remove_error", {"exc": "index out of range"}),
    ("gateway.subgoal_removed", {"idx": 1, "removed": "Write tests"}),
    ("gateway.subgoal_clear_error", {"exc": "locked"}),
    ("gateway.subgoal_cleared_one", {"count": 1}),
    ("gateway.subgoal_cleared_many", {"count": 3}),
    ("gateway.subgoal_none_to_clear", {}),
    ("gateway.subgoal_add_error", {"exc": "goal locked"}),
    ("gateway.subgoal_added", {"idx": 2, "text": "Write tests"}),
    # /memory & /skills
    ("gateway.memory_unknown_subcommand", {}),
    ("gateway.skills_write_approval_off", {}),
    ("gateway.skills_unknown_subcommand", {}),
    ("gateway.skills_diff_truncated", {"pending_id": "abc123"}),
])
def test_batchC_key_resolves_in_russian(key, kwargs):
    """Each Batch C key must resolve (not raise KeyError) in Russian."""
    result = i18n.t(key, lang="ru", **kwargs)
    assert isinstance(result, str) and result, f"Empty or non-string result for {key!r}"


# ---- Batch D: Telegram platform UI strings ----

_TELEGRAM_PY = Path(__file__).parents[2] / "gateway" / "platforms" / "telegram.py"
_TELEGRAM_SRC = _TELEGRAM_PY.read_text(encoding="utf-8")


@pytest.mark.parametrize("key,kwargs", [
    ("gateway.tg_update_prompt_header", {}),
    ("gateway.tg_btn_yes", {}),
    ("gateway.tg_btn_no", {}),
    ("gateway.tg_approval_header", {}),
    ("gateway.tg_btn_allow_once", {}),
    ("gateway.tg_btn_allow_session", {}),
    ("gateway.tg_btn_allow_always", {}),
    ("gateway.tg_btn_deny", {}),
    ("gateway.tg_btn_approve_once", {}),
    ("gateway.tg_btn_always_approve", {}),
    ("gateway.tg_btn_cancel", {}),
    ("gateway.tg_btn_cancel_x", {}),
    ("gateway.tg_btn_prev", {}),
    ("gateway.tg_btn_next", {}),
    ("gateway.tg_btn_back", {}),
    ("gateway.tg_btn_switch_anyway", {}),
    ("gateway.tg_more_available", {"n": 5}),
    ("gateway.tg_model_config_header", {}),
    ("gateway.tg_picker_expired", {}),
    ("gateway.tg_provider_not_found", {}),
    ("gateway.tg_invalid_page", {}),
    ("gateway.tg_invalid_selection", {}),
    ("gateway.tg_invalid_model_index", {}),
    ("gateway.tg_picker_expired_short", {}),
    ("gateway.tg_switch_failed", {}),
    ("gateway.tg_model_switched", {}),
    ("gateway.tg_confirm_expensive", {}),
    ("gateway.tg_group_not_found", {}),
    ("gateway.tg_model_selection_cancelled", {}),
    ("gateway.tg_expensive_warning_header", {}),
    ("gateway.tg_approved_once", {}),
    ("gateway.tg_denied", {}),
    ("gateway.tg_approval_resolved", {}),
    ("gateway.tg_prompt_resolved", {}),
    ("gateway.tg_approved_session", {}),
    ("gateway.tg_approved_permanently", {}),
    ("gateway.tg_always_approve_label", {}),
    ("gateway.tg_cancelled_label", {}),
    ("gateway.tg_not_authorized_approve", {}),
    ("gateway.tg_not_authorized_prompt", {}),
    ("gateway.tg_not_authorized_update", {}),
    ("gateway.tg_not_authorized_email", {}),
    ("gateway.tg_type_answer", {}),
    ("gateway.tg_invalid_choice", {}),
    ("gateway.tg_clarify_resolved", {"resolved_text": "Yes"}),
    ("gateway.tg_sent_answer", {"answer": "y"}),
    ("gateway.tg_update_answered", {"label": "Yes"}),
    ("gateway.tg_gmail_invalid_data", {}),
    ("gateway.tg_gmail_unknown_verb", {"verb": "send"}),
    ("gateway.tg_gmail_script_missing", {"script_name": "send.sh"}),
    ("gateway.tg_gmail_verb_failed", {"verb": "send", "detail": "error msg"}),
    ("gateway.tg_gmail_verb_timed_out", {"verb": "send"}),
    ("gateway.tg_gmail_verb_error", {"verb": "send", "error": "timeout"}),
    ("gateway.tg_invalid_approval_data", {}),
])
def test_batchD_key_resolves_in_russian(key, kwargs):
    """Each Batch D key must resolve (not raise KeyError) in Russian."""
    result = i18n.t(key, lang="ru", **kwargs)
    assert isinstance(result, str) and result, f"Empty or non-string result for {key!r}"


@pytest.mark.parametrize("literal", [
    # Strings now wrapped with t() in telegram.py
    '"⚕ *Update needs your input:*\\n\\n"',
    '"✓ Yes"',
    '"✗ No"',
    '"⚠️ <b>Command Approval Required</b>\\n\\n"',
    '"✅ Allow Once"',
    '"✅ Session"',
    '"✅ Always"',
    '"❌ Deny"',
    '"✅ Approve Once"',
    '"🔒 Always Approve"',
    '"❌ Cancel"',
    '"✗ Cancel"',
    '"◀ Prev"',
    '"Next ▶"',
    '"◀ Back"',
    '"Switch anyway"',
    '"⚙ *Model Configuration*\\n\\n"',
    '"Picker expired — use /model again."',
    '"Provider not found."',
    '"Invalid page."',
    '"Switch failed."',
    '"Model switched!"',
    '"Confirm expensive model"',
    '"Group not found."',
    '"Model selection cancelled."',
    '"⚠ *Expensive Model Warning*\\n\\n',
    '"Invalid approval data."',
    '"⛔ You are not authorized to approve commands."',
    '"⛔ You are not authorized to answer this prompt."',
    '"⛔ You are not authorized to answer update prompts."',
    '"⛔ You are not authorized to act on this email."',
    '"✏️ Type your answer in the chat."',
    '"Invalid choice."',
    '"Invalid gmail-triage data."',
    # Batch D fixes — approval-result labels now wrapped
    '"✅ Approved once"',
    '"❌ Denied"',
    '"This approval has already been resolved."',
    '"This prompt has already been resolved."',
])
def test_batchD_literal_not_unwrapped_in_telegram(literal):
    assert literal not in _TELEGRAM_SRC, (
        f"unwrapped English literal still present in telegram.py: {literal!r}"
    )
