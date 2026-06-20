"""Tests for the Codex gpt-5.5 autoraise *notice* gate.

The threshold raise to 0.85 is behavioural and is covered elsewhere
(`_compression_threshold_for_model`). These tests pin the separate decision of
whether to SURFACE the one-time notice: `_should_announce_codex_gpt55_autoraise`.

Invariant: a deployment can suppress the notice (`announce_enabled=False`)
without affecting the raise. The helper must also never announce a no-op (the
threshold did not actually increase) or fire for non-Codex-gpt-5.5 routes.
"""

from __future__ import annotations

import pytest

from agent.auxiliary_client import (
    _CODEX_GPT55_COMPACTION_THRESHOLD,
    _should_announce_codex_gpt55_autoraise as should_announce,
)

CODEX = "openai-codex"


def test_announces_when_enabled_and_threshold_rose() -> None:
    assert (
        should_announce(
            "gpt-5.5", CODEX, 0.50, _CODEX_GPT55_COMPACTION_THRESHOLD,
            announce_enabled=True,
        )
        is True
    )


def test_suppressed_when_announce_disabled_but_raise_still_applies() -> None:
    # announce_enabled=False is the whole point: the caller still applies the
    # raised threshold; the helper just declines to surface the notice.
    assert (
        should_announce(
            "gpt-5.5", CODEX, 0.50, _CODEX_GPT55_COMPACTION_THRESHOLD,
            announce_enabled=False,
        )
        is False
    )


def test_no_announce_for_non_codex_route() -> None:
    # Same slug on the direct OpenAI API is not the Codex route → no raise, no notice.
    assert (
        should_announce("gpt-5.5", "openai", 0.50, 0.85, announce_enabled=True)
        is False
    )


@pytest.mark.parametrize("model", ["gpt-5.4", "claude-sonnet-4.6", "", None])
def test_no_announce_for_other_models(model) -> None:
    assert should_announce(model, CODEX, 0.50, 0.85, announce_enabled=True) is False


def test_no_announce_when_threshold_unchanged() -> None:
    # User already runs a global threshold at/above the raised value → no-op, no notice.
    assert (
        should_announce("gpt-5.5", CODEX, 0.85, 0.85, announce_enabled=True) is False
    )
    assert (
        should_announce("gpt-5.5", CODEX, 0.90, 0.85, announce_enabled=True) is False
    )


def test_no_announce_when_no_override() -> None:
    # new_threshold is None when the model has no per-model override at all.
    assert (
        should_announce("gpt-5.5", CODEX, 0.50, None, announce_enabled=True) is False
    )


@pytest.mark.parametrize(
    "model",
    ["gpt-5.5", "gpt-5.5-pro", "gpt-5.5-2026-04-23", "openai/gpt-5.5"],
)
def test_announce_tracks_the_gpt55_family(model: str) -> None:
    assert (
        should_announce(model, CODEX, 0.50, 0.85, announce_enabled=True) is True
    )
