"""Unit tests for the Todo domain model (Features #2, #6)."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime

import pytest

from tasque.models import Priority, Todo, next_priority


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
