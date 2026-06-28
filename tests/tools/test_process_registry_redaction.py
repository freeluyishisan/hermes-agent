"""Regression tests for process-registry secret redaction surfaces."""

import time

import pytest

from tools.process_registry import ProcessRegistry, ProcessSession, _store_process_output


@pytest.fixture()
def registry():
    """Create a fresh ProcessRegistry."""
    return ProcessRegistry()


def _make_session(
    sid="proc_test123",
    command="echo hello",
    task_id="t1",
    exited=False,
    exit_code=None,
    output="",
    started_at=None,
) -> ProcessSession:
    """Helper to create a ProcessSession for testing."""
    return ProcessSession(
        id=sid,
        command=command,
        task_id=task_id,
        started_at=started_at or time.time(),
        exited=exited,
        exit_code=exit_code,
        output_buffer=output,
    )


def _hubspot_private_app_token() -> str:
    """Build a HubSpot-shaped token without a scanner-triggering literal."""
    return "pat-" + "na1-" + "aaaaaaaa-bbbb-cccc-dddd-" + "eeeeeeeeeeee"


def test_process_outputs_redact_bare_secret_env_values(monkeypatch, registry):
    monkeypatch.setattr("agent.redact._REDACT_ENABLED", True)
    secret = _hubspot_private_app_token()
    monkeypatch.setenv("HUBSPOT_SERVICE_KEY", secret)
    session = _make_session(
        exited=True,
        exit_code=0,
        output=f"poll={secret}\nlog={secret}\nwait={secret}",
    )
    registry._finished[session.id] = session

    poll = registry.poll(session.id)
    log = registry.read_log(session.id)
    wait = registry.wait(session.id, timeout=1)
    listing = registry.list_sessions()

    for output in (
        poll["output_preview"],
        log["output"],
        wait["output"],
        listing[0]["output_preview"],
    ):
        assert secret not in output
        assert "pat-na...eeee" in output


def test_process_output_redaction_handles_secret_split_across_chunks(monkeypatch, registry):
    monkeypatch.setattr("agent.redact._REDACT_ENABLED", True)
    secret = _hubspot_private_app_token()
    monkeypatch.setenv("HUBSPOT_SERVICE_KEY", secret)
    session = _make_session(exited=True, exit_code=0, output="")

    _store_process_output(session, "chunk1=" + secret[:24], append=True)
    _store_process_output(session, secret[24:] + "\n", append=True)
    registry._finished[session.id] = session

    # The internal buffer stays raw so redaction can see secrets that span
    # reader chunks; every user-visible surface must still be redacted.
    assert secret in session.output_buffer
    poll = registry.poll(session.id)
    log = registry.read_log(session.id)
    wait = registry.wait(session.id, timeout=1)

    for output in (poll["output_preview"], log["output"], wait["output"]):
        assert secret not in output
        assert "eeeeeeeeeeee" not in output
        assert "pat-na...eeee" in output


def test_watch_notification_redacts_bare_secret_env_values(monkeypatch, registry):
    monkeypatch.setattr("agent.redact._REDACT_ENABLED", True)
    secret = _hubspot_private_app_token()
    monkeypatch.setenv("HUBSPOT_SERVICE_KEY", secret)
    session = _make_session(output="")
    session.watch_patterns = ["SECRET_READY"]

    registry._check_watch_patterns(session, f"SECRET_READY {secret}\n")
    event = registry.completion_queue.get_nowait()

    assert secret not in event["output"]
    assert "pat-na...eeee" in event["output"]


def test_watch_notification_redacts_split_bare_secret_env_value_fragment(monkeypatch, registry):
    monkeypatch.setattr("agent.redact._REDACT_ENABLED", True)
    secret = "opaque-service-secret-value-1234567890"
    monkeypatch.setenv("EXAMPLE_SERVICE_KEY", secret)
    session = _make_session(output="")
    session.watch_patterns = ["SECRET_READY"]

    registry._check_watch_patterns(session, f"SECRET_READY {secret[:18]}\n")
    event = registry.completion_queue.get_nowait()

    assert secret[:18] not in event["output"]
    assert "opaque-service" not in event["output"]
    assert "opaque...7890" in event["output"]


def test_completion_notification_redacts_bare_secret_env_values(monkeypatch, registry):
    monkeypatch.setattr("agent.redact._REDACT_ENABLED", True)
    secret = _hubspot_private_app_token()
    monkeypatch.setenv("HUBSPOT_SERVICE_KEY", secret)
    session = _make_session(output=f"finished with {secret}", exited=True, exit_code=0)
    session.notify_on_complete = True
    registry._running[session.id] = session

    registry._move_to_finished(session)
    event = registry.completion_queue.get_nowait()

    assert secret not in event["output"]
    assert "pat-na...eeee" in event["output"]
