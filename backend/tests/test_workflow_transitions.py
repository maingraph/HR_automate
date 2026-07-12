import pytest

from app.services.stages import TRANSITIONS, validate_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("pending", "running"),
        ("running", "pause_requested"),
        ("pause_requested", "paused"),
        ("paused", "running"),
        ("running", "awaiting_auth"),
        ("awaiting_auth", "running"),
        ("running", "awaiting_user"),
        ("awaiting_user", "completed"),
    ],
)
def test_valid_stage_transitions(current, target):
    validate_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [("completed", "running"), ("stopped", "running"), ("pending", "completed")],
)
def test_invalid_stage_transitions(current, target):
    with pytest.raises(ValueError, match="Invalid stage transition"):
        validate_transition(current, target)


def test_terminal_states_have_no_outgoing_transitions():
    for state in ("completed", "stopped", "failed", "skipped"):
        assert TRANSITIONS[state] == set()
