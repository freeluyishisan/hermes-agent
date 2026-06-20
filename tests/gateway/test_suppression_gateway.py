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
