"""Tests for agent i18n: agent/* and gateway/kanban_watchers.py message localisation.

Covers Batch A (direct emission) and Batch E (indirect/deferred emission paths).
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

from agent.i18n import t


# ---------------------------------------------------------------------------
# Batch A rendering assertions — representative keys resolve to Russian under lang="ru"
# ---------------------------------------------------------------------------

class TestBatchARendering:
    def test_self_review_header_ru(self):
        en = t("gateway.self_review_header", lang="en", summary="test")
        ru = t("gateway.self_review_header", lang="ru", summary="test")
        assert "test" in en
        assert "test" in ru
        assert en != ru, "Russian should differ from English"

    def test_kanban_done_ru(self):
        en = t("gateway.kanban_done", lang="en", tag="", task_id="T1", title="My task", handoff="")
        ru = t("gateway.kanban_done", lang="ru", tag="", task_id="T1", title="My task", handoff="")
        assert "T1" in en
        assert "T1" in ru
        assert en != ru

    def test_iteration_budget_exhausted_ru(self):
        en = t("gateway.iteration_budget_exhausted", lang="en", n=5, max=10)
        ru = t("gateway.iteration_budget_exhausted", lang="ru", n=5, max=10)
        assert "5" in en and "10" in en
        assert "5" in ru and "10" in ru
        assert en != ru

    def test_api_error_billing_ru(self):
        en = t("gateway.api_error_billing", lang="en", summary="out of funds")
        ru = t("gateway.api_error_billing", lang="ru", summary="out of funds")
        assert "out of funds" in en
        assert "out of funds" in ru
        assert en != ru

    def test_review_label_skill_ru(self):
        en = t("gateway.review_label_skill", lang="en")
        ru = t("gateway.review_label_skill", lang="ru")
        assert en == "Skill"
        assert en != ru

    def test_empty_response_retry_ru(self):
        en = t("gateway.empty_response_retry", lang="en", n=2)
        ru = t("gateway.empty_response_retry", lang="ru", n=2)
        assert "2" in en
        assert "2" in ru
        assert en != ru

    def test_stale_connections_cleaned_ru(self):
        en = t("gateway.stale_connections_cleaned", lang="en")
        ru = t("gateway.stale_connections_cleaned", lang="ru")
        assert en != ru


# ---------------------------------------------------------------------------
# Batch E rendering assertions — codex gpt-5.5 autoraise notice
# ---------------------------------------------------------------------------

class TestBatchERendering:
    def test_codex_gpt55_autoraise_notice_ru(self):
        """Russian translation of the codex autoraise notice must differ from English
        and must preserve the {to_pct} and {from_pct} substitutions."""
        en = t("gateway.codex_gpt55_autoraise_notice", lang="en", to_pct=90, from_pct=80)
        ru = t("gateway.codex_gpt55_autoraise_notice", lang="ru", to_pct=90, from_pct=80)
        assert "90" in en and "80" in en, "English must contain the substituted percentages"
        assert "90" in ru and "80" in ru, "Russian must contain the substituted percentages"
        assert en != ru, "Russian should differ from English"

    def test_codex_gpt55_autoraise_notice_en_exact(self):
        """English catalog value must render with the correct opt-out command intact."""
        result = t("gateway.codex_gpt55_autoraise_notice", lang="en", to_pct=95, from_pct=85)
        assert "272K" in result
        assert "gpt-5.5" in result
        assert "hermes config set compression.codex_gpt55_autoraise false" in result
        assert "95" in result and "85" in result


# ---------------------------------------------------------------------------
# Source guard — wrapped literals must no longer appear bare in touched files
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_source(relpath: str) -> str:
    return (REPO_ROOT / relpath).read_text(encoding="utf-8")


class TestSourceGuards:
    def test_background_review_no_bare_self_improvement_literal(self):
        src = _read_source("agent/background_review.py")
        # The messenger-sent path must use t() not the bare f-string
        assert f'"💾 Self-improvement review: ' not in src, (
            "bare '💾 Self-improvement review:' string literal found in background_review.py"
        )

    def test_background_review_no_bare_skill_patched_literal(self):
        src = _read_source("agent/background_review.py")
        assert "f\"📝 Skill '" not in src, (
            "bare f-string for skill patched found in background_review.py"
        )

    def test_turn_finalizer_no_bare_budget_exhausted_literal(self):
        src = _read_source("agent/turn_finalizer.py")
        assert '"⚠️ Iteration budget exhausted (' not in src, (
            "bare iteration budget exhausted literal found in turn_finalizer.py"
        )

    def test_turn_context_no_bare_stale_connections_literal(self):
        src = _read_source("agent/turn_context.py")
        assert '"🔌 Detected stale connections' not in src, (
            "bare stale connections literal found in turn_context.py"
        )

    def test_turn_context_no_bare_preflight_compression_literal(self):
        src = _read_source("agent/turn_context.py")
        assert '"📦 Preflight compression:' not in src, (
            "bare preflight compression literal found in turn_context.py"
        )

    def test_conversation_compression_no_bare_aux_unavailable_literal(self):
        src = _read_source("agent/conversation_compression.py")
        assert '"⚠ Configured auxiliary compression provider' not in src, (
            "bare aux unavailable literal found in conversation_compression.py"
        )

    def test_conversation_loop_no_bare_api_error_billing_literal(self):
        src = _read_source("agent/conversation_loop.py")
        assert '"❌ Billing or credits exhausted — ' not in src, (
            "bare billing error f-string found in conversation_loop.py"
        )

    def test_conversation_loop_no_bare_tool_guardrail_literal(self):
        src = _read_source("agent/conversation_loop.py")
        assert 'f"⚠️ Tool guardrail halted' not in src, (
            "bare tool guardrail f-string found in conversation_loop.py"
        )

    def test_kanban_watchers_no_bare_kanban_done_literal(self):
        src = _read_source("gateway/kanban_watchers.py")
        assert 'f"✔ {tag}Kanban' not in src, (
            "bare kanban done f-string found in kanban_watchers.py"
        )

    def test_kanban_watchers_no_bare_kanban_blocked_literal(self):
        src = _read_source("gateway/kanban_watchers.py")
        assert 'f"⏸ {tag}Kanban' not in src, (
            "bare kanban blocked f-string found in kanban_watchers.py"
        )

    def test_agent_init_no_bare_codex_autoraise_literal(self):
        """The codex gpt-5.5 autoraise notice must not appear bare in agent_init.py."""
        src = _read_source("agent/agent_init.py")
        assert "Codex gpt-5.5 caps context at 272K" not in src, (
            "bare codex gpt-5.5 autoraise notice literal found in agent_init.py — "
            "must be wrapped with t('gateway.codex_gpt55_autoraise_notice', ...)"
        )
