"""Tests for Batch A i18n: agent/* and gateway/kanban_watchers.py message localisation."""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

from agent.i18n import t


# ---------------------------------------------------------------------------
# Rendering assertions — representative keys resolve to Russian under lang="ru"
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
