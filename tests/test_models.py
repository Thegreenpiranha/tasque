"""Unit tests for the Todo domain model (Features #2, #6, #7)."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime

import pytest

from tasque.models import (
    DueDateParseError,
    DueState,
    Priority,
    Todo,
    TodoSort,
    due_state,
    next_priority,
    parse_due_date,
)


def test_new_todo_defaults():
    todo = Todo.new("buy milk")
    assert todo.text == "buy milk"
    assert todo.id is None
    assert todo.completed is False
    assert isinstance(todo.created_at, datetime)
    assert todo.priority is None
    assert todo.due_date is None
    assert todo.category_id is None
    assert todo.list_id is None


def test_new_accepts_explicit_created_at():
    when = datetime(2026, 1, 1, 12, 0, 0)
    todo = Todo.new("x", created_at=when)
    assert todo.created_at == when


def test_full_construction():
    todo = Todo(
        text="ship it",
        id=7,
        completed=True,
        created_at=datetime(2026, 6, 29),
        priority=2,
        due_date=date(2026, 7, 1),
        category_id=3,
        list_id=1,
    )
    assert todo.id == 7
    assert todo.completed is True
    assert todo.due_date == date(2026, 7, 1)


def test_is_frozen():
    todo = Todo.new("immutable")
    with pytest.raises(FrozenInstanceError):
        todo.text = "changed"  # type: ignore[misc]


def test_replace_yields_new_instance_leaving_original_intact():
    todo = Todo.new("a")
    saved = replace(todo, id=1)
    assert saved.id == 1
    assert saved.text == todo.text
    assert todo.id is None


# --------------------------------------------------------------------------- #
# Priority enum (Feature #6)
# --------------------------------------------------------------------------- #


def test_priority_values_are_ascending():
    """LOW < MEDIUM < HIGH so ORDER BY priority DESC yields high first."""
    assert Priority.LOW < Priority.MEDIUM < Priority.HIGH


def test_priority_is_int_subclass():
    """IntEnum so SQLite stores/reads it as a plain integer with no adapter."""
    assert isinstance(Priority.HIGH, int)
    assert int(Priority.HIGH) == 3
    assert int(Priority.MEDIUM) == 2
    assert int(Priority.LOW) == 1


def test_priority_round_trips_through_int():
    assert Priority(1) is Priority.LOW
    assert Priority(2) is Priority.MEDIUM
    assert Priority(3) is Priority.HIGH


# --------------------------------------------------------------------------- #
# next_priority (Feature #6)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "current, expected",
    [
        (None, Priority.LOW),
        (Priority.LOW, Priority.MEDIUM),
        (Priority.MEDIUM, Priority.HIGH),
        (Priority.HIGH, None),
    ],
)
def test_next_priority_cycle(current, expected):
    assert next_priority(current) is expected


def test_next_priority_full_cycle_returns_to_none():
    """Four consecutive calls cycle completely: none→low→med→high→none."""
    state = None
    for _ in range(4):
        state = next_priority(state)
    assert state is None


def test_next_priority_is_pure_no_side_effects():
    """Calling next_priority does not mutate any global state."""
    next_priority(Priority.HIGH)
    next_priority(None)
    assert next_priority(Priority.LOW) is Priority.MEDIUM


# --------------------------------------------------------------------------- #
# due_state — overdue classification with a fixed "now" (Feature #7)
# --------------------------------------------------------------------------- #

_TODAY = date(2026, 7, 4)


def test_due_state_none_when_no_due_date():
    assert due_state(None, _TODAY) is DueState.NONE


def test_due_state_overdue_when_strictly_before_today():
    assert due_state(date(2026, 7, 3), _TODAY) is DueState.OVERDUE
    assert due_state(date(2025, 1, 1), _TODAY) is DueState.OVERDUE


def test_due_state_today_is_today_not_overdue():
    """The current civil day is 'due today', never overdue (boundary precision)."""
    assert due_state(_TODAY, _TODAY) is DueState.TODAY


def test_due_state_future_when_after_today():
    assert due_state(date(2026, 7, 5), _TODAY) is DueState.FUTURE
    assert due_state(date(2027, 1, 1), _TODAY) is DueState.FUTURE


def test_due_state_is_pure_and_completion_agnostic():
    """Completion is not an input — the widget gates escalation, not the classifier."""
    assert due_state(date(2026, 7, 3), _TODAY) is DueState.OVERDUE
    # Same call again yields the same answer — no hidden state.
    assert due_state(date(2026, 7, 3), _TODAY) is DueState.OVERDUE


# --------------------------------------------------------------------------- #
# parse_due_date — small grammar, fixed-today testable (Feature #7)
# --------------------------------------------------------------------------- #


def test_parse_due_date_iso_round_trips():
    assert parse_due_date("2026-07-10", today=_TODAY) == date(2026, 7, 10)


def test_parse_due_date_iso_ignores_surrounding_whitespace():
    assert parse_due_date("  2026-07-10  ", today=_TODAY) == date(2026, 7, 10)


def test_parse_due_date_today_anchor():
    assert parse_due_date("today", today=_TODAY) == _TODAY


def test_parse_due_date_tomorrow_anchor():
    assert parse_due_date("tomorrow", today=_TODAY) == date(2026, 7, 5)


def test_parse_due_date_is_case_insensitive():
    assert parse_due_date("ToDaY", today=_TODAY) == _TODAY
    assert parse_due_date("TOMORROW", today=_TODAY) == date(2026, 7, 5)


def test_parse_due_date_relative_plus_n():
    assert parse_due_date("+3", today=_TODAY) == date(2026, 7, 7)
    assert parse_due_date("+0", today=_TODAY) == _TODAY


@pytest.mark.parametrize("junk", ["soon", "next fri", "2026-13-40", "+", "+3d", "", "tues"])
def test_parse_due_date_rejects_junk(junk):
    with pytest.raises(DueDateParseError):
        parse_due_date(junk, today=_TODAY)


def test_due_date_parse_error_is_a_value_error_not_tasque_error():
    """Parse failures are input validation (ValueError), never persistence errors."""
    assert issubclass(DueDateParseError, ValueError)


# --------------------------------------------------------------------------- #
# TodoSort.DUE (Feature #7)
# --------------------------------------------------------------------------- #


def test_todo_sort_has_due_member():
    assert TodoSort.DUE.value == "due"
    assert TodoSort.DUE in TodoSort
