"""Guards the suppression category map against drift."""
from agent import i18n

# The exact set of keys expected in each mutable category. Update this when a
# new progress/lifecycle/info NOTIFICATION key is added (and add it to
# i18n.GATEWAY_MESSAGE_CATEGORIES). Return-value reply keys are NOT included.
EXPECTED = {
    "progress": {
        "gateway.long_running", "gateway.no_activity_warning",
        "gateway.subagent_working", "gateway.queued_next_turn",
        "gateway.interrupting_task", "gateway.steered_into_run",
        "gateway.busy_not_accepting_turn", "gateway.busy_not_accepting_work",
        "gateway.busy_queued_drain",
    },
    "lifecycle": {
        "gateway.restart_success", "gateway.gateway_online", "gateway.draining",
        "gateway.shutdown_restarting", "gateway.shutdown_shutting_down",
    },
    "info": {
        "gateway.codex_gpt55_autoraise_notice", "gateway.self_review_header",
        "gateway.kanban_done", "gateway.kanban_blocked", "gateway.kanban_crashed",
        "gateway.kanban_gave_up", "gateway.kanban_timed_out",
        "gateway.compression_aux_unavailable", "gateway.compression_no_provider",
        "gateway.compress_aux_model_failed", "gateway.preflight_compression",
        "gateway.stale_connections_cleaned", "gateway.iteration_budget_exhausted",
        "gateway.thinking_prefill_retry",
    },
}


def test_map_matches_expected_membership():
    actual = {}
    for key, cat in i18n.GATEWAY_MESSAGE_CATEGORIES.items():
        actual.setdefault(cat, set()).add(key)
    assert actual == EXPECTED
