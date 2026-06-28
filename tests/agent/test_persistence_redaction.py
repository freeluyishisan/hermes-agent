"""Persistence-boundary redaction tests (#43666).

Covers the three gaps from the issue:

1. DB URIs in tool-output file dumps — dialect+driver schemes
   (``postgresql+psycopg://...``) slipped through ``_DB_CONNSTR_RE`` and
   landed in state.db in plaintext. Pattern-level tests live in
   tests/agent/test_redact.py (TestDbConnstrDialectDriver); here we prove
   the end-to-end property: the bytes written to the SQLite file contain
   no plaintext secret, and the stored bytes equal the replayed bytes
   (stored == wire invariant).
2. Compaction blocks — summarizer input serialization and the static
   fallback summary carry no plaintext secret.
3. Reasoning fields — ``reasoning`` / ``reasoning_content`` /
   ``reasoning_details`` are credential-redacted at message construction.
   Opaque reasoning_details items (signature, encrypted_content) and
   Gemini ``extra_content`` are preserved byte-exact: altering them breaks
   provider signature checks on replay.

All redaction is gated on ``security.redact_secrets`` — the disabled
case must be a byte-identical no-op (also asserted here).
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent.redact import redact_sensitive_text

SECRET_PW = "honchorulez"
SECRET_URI = f"postgresql+psycopg://postgres:{SECRET_PW}@127.0.0.1:5432/postgres"


@pytest.fixture(autouse=True)
def _redaction_enabled(monkeypatch):
    """Ensure redaction is on regardless of prior test imports."""
    monkeypatch.delenv("HERMES_REDACT_SECRETS", raising=False)
    monkeypatch.setattr("agent.redact._REDACT_ENABLED", True)


def _make_agent():
    """Minimal agent exposing the real _build_assistant_message."""
    from run_agent import AIAgent

    agent = MagicMock(spec=AIAgent)
    agent._build_assistant_message = AIAgent._build_assistant_message.__get__(agent)
    agent._extract_reasoning = AIAgent._extract_reasoning.__get__(agent)
    agent._strip_think_blocks = AIAgent._strip_think_blocks.__get__(agent)
    agent.verbose_logging = False
    agent.reasoning_callback = None
    agent.stream_delta_callback = None
    agent._stream_callback = None
    agent._needs_thinking_reasoning_pad.return_value = False
    agent._split_responses_tool_id.return_value = (None, None)
    agent._derive_responses_function_call_id.side_effect = lambda cid, rid: rid or cid
    return agent


def _api_msg(content, **fields):
    msg = SimpleNamespace(content=content, tool_calls=fields.pop("tool_calls", None))
    for key, value in fields.items():
        setattr(msg, key, value)
    return msg


class TestReasoningFieldRedaction:
    """#43666 gap 3 — reasoning fields at the persistence boundary."""

    def test_reasoning_redacted(self):
        agent = _make_agent()
        result = agent._build_assistant_message(
            _api_msg("done", reasoning=f"I will connect via {SECRET_URI}"), "stop"
        )
        assert SECRET_PW not in result["reasoning"]
        assert ":***@" in result["reasoning"]

    def test_reasoning_content_redacted(self):
        agent = _make_agent()
        result = agent._build_assistant_message(
            _api_msg("done", reasoning_content=f"the uri is {SECRET_URI}"), "stop"
        )
        assert SECRET_PW not in result["reasoning_content"]
        assert SECRET_PW not in (result.get("reasoning") or "")

    def test_inline_think_block_reasoning_redacted(self):
        agent = _make_agent()
        result = agent._build_assistant_message(
            _api_msg(f"<think>connect with {SECRET_URI}</think>ok"), "stop"
        )
        assert SECRET_PW not in result["reasoning"]

    def test_reasoning_details_text_redacted(self):
        agent = _make_agent()
        details = [{"type": "reasoning.text", "text": f"using {SECRET_URI}"}]
        result = agent._build_assistant_message(
            _api_msg("done", reasoning="r", reasoning_details=details), "stop"
        )
        assert SECRET_PW not in result["reasoning_details"][0]["text"]

    def test_reasoning_details_summary_redacted(self):
        agent = _make_agent()
        details = [{"type": "reasoning.summary", "summary": f"used {SECRET_URI}"}]
        result = agent._build_assistant_message(
            _api_msg("done", reasoning="r", reasoning_details=details), "stop"
        )
        assert SECRET_PW not in result["reasoning_details"][0]["summary"]

    def test_unsigned_anthropic_thinking_block_redacted(self):
        """Anthropic-shaped {"type": "thinking", "thinking": ...} items
        without a signature (e.g. synthesized from reasoning_content in
        anthropic_adapter) are redacted via the ``thinking`` key."""
        agent = _make_agent()
        details = [{"type": "thinking", "thinking": f"connect via {SECRET_URI}"}]
        result = agent._build_assistant_message(
            _api_msg("done", reasoning="r", reasoning_details=details), "stop"
        )
        assert SECRET_PW not in result["reasoning_details"][0]["thinking"]

    def test_signed_detail_preserved_byte_exact(self):
        """Items with a signature must replay byte-exact — altering the
        text invalidates the provider's signature check and forces the
        strip-reasoning retry path. Documented limitation: a secret inside
        a signed thinking block is NOT redacted."""
        agent = _make_agent()
        signed = {
            "type": "reasoning.text",
            "text": f"via {SECRET_URI}",
            "signature": "sig-abc123",
        }
        result = agent._build_assistant_message(
            _api_msg("done", reasoning="r", reasoning_details=[signed]), "stop"
        )
        assert result["reasoning_details"][0] is signed

    def test_encrypted_detail_preserved_byte_exact(self):
        agent = _make_agent()
        encrypted = {"type": "reasoning.encrypted", "data": "opaque-blob=="}
        result = agent._build_assistant_message(
            _api_msg("done", reasoning="r", reasoning_details=[encrypted]), "stop"
        )
        assert result["reasoning_details"][0] is encrypted

    def test_raw_api_detail_dict_not_mutated(self):
        """Copy-on-write: the dict shared with the raw API response object
        must keep its original value — tool execution in the same turn
        reads the raw response, not the persisted shape."""
        agent = _make_agent()
        original = {"type": "reasoning.text", "text": f"using {SECRET_URI}"}
        agent._build_assistant_message(
            _api_msg("done", reasoning="r", reasoning_details=[original]), "stop"
        )
        assert SECRET_PW in original["text"]

    def test_redaction_disabled_is_noop(self, monkeypatch):
        """security.redact_secrets: false must be a byte-identical no-op."""
        monkeypatch.setattr("agent.redact._REDACT_ENABLED", False)
        agent = _make_agent()
        details = [{"type": "reasoning.text", "text": f"using {SECRET_URI}"}]
        result = agent._build_assistant_message(
            _api_msg(
                f"uri: {SECRET_URI}",
                reasoning=f"via {SECRET_URI}",
                reasoning_details=details,
            ),
            "stop",
        )
        assert SECRET_URI in result["content"]
        assert SECRET_URI in result["reasoning"]
        assert SECRET_URI in result["reasoning_details"][0]["text"]


class TestToolCallBoundary:
    """Tool-call args are redacted; Gemini extra_content stays byte-exact."""

    def _tool_call(self, arguments, extra_content=None):
        return SimpleNamespace(
            id="call_1",
            call_id="call_1",
            response_item_id="fc_1",
            type="function",
            function=SimpleNamespace(name="terminal", arguments=arguments),
            extra_content=extra_content,
        )

    def test_tool_call_args_redacted_extra_content_untouched(self):
        agent = _make_agent()
        ec = {"google": {"thought_signature": "SIG_ABC123"}}
        tc = self._tool_call(
            json.dumps({"command": f"psql {SECRET_URI}"}), extra_content=ec
        )
        result = agent._build_assistant_message(
            _api_msg("", tool_calls=[tc]), "tool_calls"
        )
        stored = result["tool_calls"][0]
        assert SECRET_PW not in stored["function"]["arguments"]
        assert stored["extra_content"] == ec


class TestStateDbPersistenceBoundary:
    """End-to-end: redacted-at-source bytes are what lands on disk and
    what gets replayed. SQLite runs in WAL mode, so the DB must be
    closed (checkpointed) before scanning the file bytes."""

    def _db(self, tmp_path):
        from hermes_state import SessionDB

        return SessionDB(db_path=tmp_path / "state.db")

    def test_no_plaintext_in_db_file(self, tmp_path):
        db = self._db(tmp_path)
        sid = db.create_session("sess-1", "cli")
        # Tool output passes through redact_sensitive_text at the tool
        # boundary (terminal_tool/code_execution_tool) before it enters
        # history; the flush writes those same bytes.
        tool_output = redact_sensitive_text(f"DATABASE_URL={SECRET_URI}\nconnection ok")
        db.append_message(
            session_id=sid, role="tool", content=tool_output, tool_name="terminal"
        )
        db.append_message(
            session_id=sid,
            role="assistant",
            content="connected",
            reasoning=redact_sensitive_text(f"used {SECRET_URI}"),
            finish_reason="stop",
        )
        db.close()
        for path in tmp_path.rglob("*"):
            if not path.is_file():
                continue
            raw = path.read_bytes()
            assert SECRET_PW.encode() not in raw, f"plaintext secret in {path.name}"

    def test_stored_bytes_equal_replayed_bytes(self, tmp_path):
        db = self._db(tmp_path)
        sid = db.create_session("sess-1", "cli")
        tool_output = redact_sensitive_text(f"dump: {SECRET_URI}")
        db.append_message(
            session_id=sid, role="tool", content=tool_output, tool_name="terminal"
        )
        replayed = db.get_messages_as_conversation(sid)
        db.close()
        tool_msgs = [m for m in replayed if m.get("role") == "tool"]
        assert tool_msgs and tool_msgs[0]["content"] == tool_output


class TestCompactionRedaction:
    """#43666 gap 2 — compaction blocks carry no plaintext secret."""

    @pytest.fixture()
    def compressor(self):
        from agent.context_compressor import ContextCompressor

        with patch(
            "agent.context_compressor.get_model_context_length", return_value=100000
        ):
            return ContextCompressor(
                model="test/model",
                threshold_percent=0.85,
                protect_first_n=2,
                protect_last_n=2,
                quiet_mode=True,
            )

    def _turns(self):
        return [
            {"role": "user", "content": "set up the database"},
            {
                "role": "assistant",
                "content": "running it",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "terminal",
                            "arguments": json.dumps({"command": f"psql {SECRET_URI}"}),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": f"connected via {SECRET_URI}",
            },
        ]

    def test_summarizer_input_has_no_plaintext(self, compressor):
        serialized = compressor._serialize_for_summary(self._turns())
        assert SECRET_PW not in serialized
        assert "terminal" in serialized

    def test_static_fallback_summary_has_no_plaintext(self, compressor):
        summary = compressor._build_static_fallback_summary(
            self._turns(), reason="test"
        )
        assert SECRET_PW not in summary
