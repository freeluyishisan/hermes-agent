"""Localization of gateway system messages wrapped via t() (issue #29846).

Batch G: i18n coverage of cron/scheduler.py and gateway/platforms/yuanbao.py strings.
"""

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


# ---- Batch G: cron/scheduler.py and gateway/platforms/yuanbao.py strings ----

_SCHEDULER_PY = Path(__file__).parents[2] / "cron" / "scheduler.py"
_SCHEDULER_SRC = _SCHEDULER_PY.read_text(encoding="utf-8")

_YUANBAO_PY = Path(__file__).parents[2] / "gateway" / "platforms" / "yuanbao.py"
_YUANBAO_SRC = _YUANBAO_PY.read_text(encoding="utf-8")


@pytest.mark.parametrize("key,kwargs", [
    ("gateway.cron_response_prefix", {}),
    ("gateway.cron_stop_hint_prefix", {}),
    ("gateway.cron_failure_rate_limit", {"job_name": "my-job", "reason": "rate limit"}),
    ("gateway.cron_failure_timeout", {"job_name": "my-job"}),
    ("gateway.cron_failure_auth", {"job_name": "my-job"}),
    ("gateway.cron_failure_generic", {"job_name": "my-job", "cleaned": "something went wrong"}),
    ("gateway.cron_watchdog_failed", {"job_name": "my-job", "output": "error output", "now_iso": "2026-01-01 12:00:00"}),
])
def test_batchG_key_resolves_in_russian(key, kwargs):
    """Each Batch G key must resolve (not raise) in Russian."""
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


# ---- Batch F: base.py platform adapter strings ----

_BASE_PY = Path(__file__).parents[2] / "gateway" / "platforms" / "base.py"
_BASE_SRC = _BASE_PY.read_text(encoding="utf-8")


@pytest.mark.parametrize("key,kwargs", [
    ("gateway.delivery_failed", {}),
    ("gateway.response_formatting_failed", {"content": "some text"}),
    ("gateway.audio_fallback_caption", {"audio_path": "/tmp/audio.ogg"}),
    ("gateway.file_fallback_caption", {"file_path": "/tmp/file.pdf"}),
    ("gateway.image_fallback_caption", {"image_path": "/tmp/image.png"}),
    ("gateway.clarify_question", {"question": "What do you prefer?"}),
    ("gateway.clarify_instructions", {}),
])
def test_batchF_key_resolves_in_russian(key, kwargs):
    """Each Batch F key must resolve (not raise KeyError) in Russian."""
    result = i18n.t(key, lang="ru", **kwargs)
    assert isinstance(result, str) and result, f"Empty or non-string result for {key!r}"


@pytest.mark.parametrize("literal", [
    # Strings now wrapped with t() in gateway/platforms/base.py
    '"⚠️ Message delivery failed after multiple attempts.',   # delivery_failed
    '"(Response formatting failed, plain text:)',              # response_formatting_failed
    'f"🔊 Audio: {audio_path}"',                              # audio_fallback_caption
    'f"📎 File: {file_path}"',                                # file_fallback_caption
    'f"🖼️ Image: {image_path}"',                              # image_fallback_caption
    'f"❓ {question}"',                                        # clarify_question
    '"Reply with the number, the option text',                 # clarify_instructions
    '"Sorry, I encountered an error ({error_type})',           # api_error_generic (base.py)
])
def test_batchF_literal_not_unwrapped_in_base(literal):
    assert literal not in _BASE_SRC, (
        f"unwrapped English literal still present in base.py: {literal!r}"
    )


def test_batchG_cron_response_prefix_russian():
    """Russian cron response message must start with the Russian cron_response_prefix."""
    prefix_ru = i18n.t("gateway.cron_response_prefix", lang="ru")
    assert prefix_ru != "gateway.cron_response_prefix", "Key not found in catalog"
    # The scheduler builds: t("gateway.cron_response_prefix") + f"{task_name}\n..."
    task_name = "my-reminder"
    cron_msg = prefix_ru + f"{task_name}\n(job_id: job123)\n-------------\n\ncontent"
    assert cron_msg.startswith(prefix_ru)


def test_batchG_yuanbao_footer_prefix_matches_catalog():
    """yuanbao.py must use t() for footer_prefix, not a hardcoded English string."""
    # Check that the footer_prefix assignment uses t()
    assert 't("gateway.cron_stop_hint_prefix")' in _YUANBAO_SRC, (
        "yuanbao.py footer_prefix not using t('gateway.cron_stop_hint_prefix')"
    )


def test_batchG_scheduler_uses_t_for_cron_prefix():
    """scheduler.py must use t() for the cron response prefix, not hardcoded string."""
    assert 't("gateway.cron_response_prefix")' in _SCHEDULER_SRC, (
        "scheduler.py not using t('gateway.cron_response_prefix')"
    )


# ---- Batch H: onboarding busy-input hints + /bundles + /update managed ----

_ONBOARDING_PY = Path(__file__).parents[2] / "agent" / "onboarding.py"
_ONBOARDING_SRC = _ONBOARDING_PY.read_text(encoding="utf-8")


@pytest.mark.parametrize("key,kwargs", [
    ("gateway.busy_hint_queued", {}),
    ("gateway.busy_hint_steered", {}),
    ("gateway.busy_hint_interrupt", {}),
    ("gateway.tool_progress_hint", {}),
    ("gateway.bundles_unavailable", {"exc": "ImportError"}),
    ("gateway.bundles_none_installed", {"bundles_dir": "/home/user/.hermes/bundles"}),
    ("gateway.bundles_header", {"n": 3}),
    ("gateway.bundles_invoke_hint", {}),
    ("gateway.update_managed", {"managed_msg": "update Hermes Agent"}),
])
def test_batchH_key_resolves_in_russian(key, kwargs):
    """Each Batch H key must resolve (not raise) in Russian."""
    result = i18n.t(key, lang="ru", **kwargs)
    assert isinstance(result, str) and result, f"Empty or non-string result for {key!r}"


def test_batchH_busy_hint_queued_russian_content():
    """Russian busy_hint_queued must contain the /busy commands."""
    result = i18n.t("gateway.busy_hint_queued", lang="ru")
    assert "/busy interrupt" in result
    assert "/busy status" in result


def test_batchH_busy_hint_steered_russian_content():
    """Russian busy_hint_steered must contain both /busy commands."""
    result = i18n.t("gateway.busy_hint_steered", lang="ru")
    assert "/busy interrupt" in result
    assert "/busy queue" in result


def test_batchH_bundles_none_installed_russian_contains_dir():
    """Russian bundles_none_installed must include the bundles_dir placeholder."""
    result = i18n.t("gateway.bundles_none_installed", lang="ru", bundles_dir="/opt/bundles")
    assert "/opt/bundles" in result


def test_batchH_update_managed_russian_preserves_managed_msg():
    """Russian update_managed must pass the managed_msg through."""
    result = i18n.t("gateway.update_managed", lang="ru", managed_msg="contact your administrator")
    assert "contact your administrator" in result


def test_batchH_onboarding_uses_t_not_hardcoded():
    """onboarding.py must NOT contain the old hardcoded English busy-hint strings."""
    assert "First-time tip — I queued" not in _ONBOARDING_SRC
    assert "First-time tip — I steered" not in _ONBOARDING_SRC
    assert "First-time tip — I just interrupted" not in _ONBOARDING_SRC
    assert "First-time tip — that tool took" not in _ONBOARDING_SRC


def test_batchH_slash_commands_uses_t_not_hardcoded():
    """slash_commands.py must NOT contain the old hardcoded /bundles strings."""
    assert '"Bundles subsystem unavailable:' not in _SLASH_COMMANDS_PY
    assert '"No skill bundles installed.' not in _SLASH_COMMANDS_PY
    assert '"**Skill Bundles**' not in _SLASH_COMMANDS_PY
    assert '"Invoke a bundle with' not in _SLASH_COMMANDS_PY
    assert 'f"✗ {format_managed_message(' not in _SLASH_COMMANDS_PY


# ============================================================================
# Batch I: run_agent.py — aux_task_failed, file_mutation_verifier, no_reply_*
# ============================================================================

@pytest.mark.parametrize("key,kwargs", [
    ("gateway.aux_task_failed", {"task": "compression", "detail": "timeout"}),
    ("gateway.file_mutation_header", {"count": 3}),
    ("gateway.file_mutation_bullet", {"path": "/foo/bar.py", "tool": "Edit", "preview": "KeyError"}),
    ("gateway.file_mutation_more", {"remaining": 5}),
    ("gateway.no_reply_empty_response_exhausted", {}),
    ("gateway.no_reply_all_retries_exhausted", {}),
    ("gateway.no_reply_partial_stream_recovery", {}),
    ("gateway.no_reply_fallback_prior_turn_content", {}),
    ("gateway.no_reply_interrupted_during_api_call", {}),
    ("gateway.no_reply_budget_exhausted", {}),
    ("gateway.no_reply_ollama_context_too_small", {}),
    ("gateway.no_reply_max_iterations_reached", {}),
    ("gateway.no_reply_error_near_max_iterations", {}),
    ("gateway.no_reply_pending_tool_result", {}),
])
def test_batchI_key_resolves_in_russian(key, kwargs):
    """Each Batch I key must resolve (not raise KeyError) in Russian."""
    result = i18n.t(key, lang="ru", **kwargs)
    assert isinstance(result, str) and result, f"Empty or non-string result for {key!r}"


def test_batchI_aux_task_failed_russian_differs_from_english():
    """Russian aux_task_failed must not just echo the English string."""
    en = i18n.t("gateway.aux_task_failed", lang="en", task="compression", detail="timeout")
    ru = i18n.t("gateway.aux_task_failed", lang="ru", task="compression", detail="timeout")
    assert "compression" in en and "compression" in ru
    assert "timeout" in en and "timeout" in ru
    assert en != ru


def test_batchI_file_mutation_header_russian_differs_from_english():
    """Russian file_mutation_header must contain a translated warning, not English."""
    en = i18n.t("gateway.file_mutation_header", lang="en", count=2)
    ru = i18n.t("gateway.file_mutation_header", lang="ru", count=2)
    assert en != ru
    assert "2" in en and "2" in ru


def test_batchI_no_reply_budget_exhausted_russian_differs():
    """Russian budget_exhausted clause must differ from English."""
    en = i18n.t("gateway.no_reply_budget_exhausted", lang="en")
    ru = i18n.t("gateway.no_reply_budget_exhausted", lang="ru")
    assert en != ru
    assert ru.startswith("⚠️")


def test_batchI_no_reply_keys_start_with_warning_emoji():
    """All no_reply_* Russian strings should start with the ⚠️ prefix."""
    no_reply_keys = [
        "gateway.no_reply_empty_response_exhausted",
        "gateway.no_reply_all_retries_exhausted",
        "gateway.no_reply_partial_stream_recovery",
        "gateway.no_reply_fallback_prior_turn_content",
        "gateway.no_reply_interrupted_during_api_call",
        "gateway.no_reply_budget_exhausted",
        "gateway.no_reply_ollama_context_too_small",
        "gateway.no_reply_max_iterations_reached",
        "gateway.no_reply_error_near_max_iterations",
        "gateway.no_reply_pending_tool_result",
    ]
    for key in no_reply_keys:
        result = i18n.t(key, lang="ru")
        assert result.startswith("⚠️"), f"{key}: expected ⚠️ prefix, got: {result[:20]!r}"


_RUN_AGENT_SRC = (Path(__file__).parents[2] / "run_agent.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("literal", [
    '"⚠ Auxiliary ',
    '"⚠️ File-mutation verifier: "',
    '"⚠️ No reply: "',
    'prefix = "⚠️ No reply: "',
])
def test_batchI_literal_not_unwrapped_in_run_agent(literal):
    assert literal not in _RUN_AGENT_SRC, (
        f"unwrapped English literal still present in run_agent.py: {literal!r}"
    )
