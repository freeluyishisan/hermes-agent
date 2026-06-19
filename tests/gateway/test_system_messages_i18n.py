"""Localization of gateway system messages wrapped via t() (issue #29846)."""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

# gateway/run.py has a top-level `from dotenv import load_dotenv` that only
# works when python-dotenv is installed in the *active* interpreter.  In this
# project the package lives in the 3.12 venv but tests are collected under the
# pyenv-shim Python (3.11), so the import fails at collection time.  The
# backward-compat note on that line says it exists so tests can monkeypatch it;
# we simply ensure the stub is in sys.modules before the module is imported.
if "dotenv" not in sys.modules:
    _dotenv_stub = types.ModuleType("dotenv")
    _dotenv_stub.load_dotenv = MagicMock(return_value=None)
    sys.modules["dotenv"] = _dotenv_stub

from agent import i18n  # noqa: E402
from gateway import run as gw  # noqa: E402


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
