"""Suppressed (empty) system messages are not sent."""
import asyncio
from unittest.mock import MagicMock
from gateway import run as gw
from agent import i18n


class _Adapter:
    def __init__(self): self.sent = []
    async def send(self, chat_id, content, **kw):
        self.sent.append(content); return MagicMock(success=True)


def test_send_unless_empty_skips_blank():
    a = _Adapter()
    asyncio.run(gw._send_unless_empty(a, chat_id="c", content=""))
    asyncio.run(gw._send_unless_empty(a, chat_id="c", content="   "))
    assert a.sent == []  # nothing sent


def test_send_unless_empty_sends_present():
    a = _Adapter()
    asyncio.run(gw._send_unless_empty(a, chat_id="c", content="hi"))
    assert a.sent == ["hi"]


def test_shutdown_lifecycle_keys_in_map():
    """Restoration guard: shutdown lifecycle notices must stay in the map."""
    assert i18n.GATEWAY_MESSAGE_CATEGORIES["gateway.shutdown_restarting"] == "lifecycle"
    assert i18n.GATEWAY_MESSAGE_CATEGORIES["gateway.shutdown_shutting_down"] == "lifecycle"


def test_compress_aux_failed_suppressed_sends_nothing(monkeypatch):
    from agent import i18n
    monkeypatch.setattr(i18n, "_load_config_dict",
        lambda: {"gateway": {"system_messages": {"suppress": ["info"]}}})
    i18n.reset_language_cache()
    import asyncio
    a = _Adapter()
    content = i18n.t("gateway.compress_aux_model_failed", model="m", err="e")
    assert content == ""
    asyncio.run(gw._send_unless_empty(a, chat_id="c", content=content))
    assert a.sent == []
    i18n.reset_language_cache()
