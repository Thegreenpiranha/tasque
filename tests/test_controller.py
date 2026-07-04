"""Unit tests for TodoController (Features #4, #6).

All tests use an in-memory SQLite database — never the user's database.
"""

from __future__ import annotations

from datetime import date

import pytest

from tasque.controller import (
    DueDateParseError,
    TodoController,
    TodoSort,
    parse_due_date,
)
from tasque.db import Database, TodoNotFoundError
from tasque.models import Priority, Todo


@pytest.fixture
def db():
    database = Database(":memory:")
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def controller(db):
    return TodoController(db)


# --------------------------------------------------------------------------- #
# list_todos
# --------------------------------------------------------------------------- #


def test_list_todos_returns_empty_list_when_db_is_empty(controller):
    assert controller.list_todos() == []


def test_list_todos_returns_todos_in_id_ascending_order(controller, db):
    a = db.add(Todo.new("a"))
    b = db.add(Todo.new("b"))
    c = db.add(Todo.new("c"))

    ids = [t.id for t in controller.list_todos()]

    assert ids == [a.id, b.id, c.id]


def test_list_todos_round_trips_text(controller, db):
    db.add(Todo.new("buy milk"))

    todos = controller.list_todos()

    assert todos[0].text == "buy milk"


def test_list_todos_round_trips_completed_flag(controller, db):
    saved = db.add(Todo.new("task"))
    db.set_completed(saved.id, True)

    todos = controller.list_todos()

    assert todos[0].completed is True


def test_list_todos_returns_frozen_dataclasses(controller, db):
    db.add(Todo.new("x"))

    todo = controller.list_todos()[0]

    # Frozen dataclass: attempts to set an attribute raise
    with pytest.raises((AttributeError, TypeError)):
        todo.text = "mutated"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# get_todo
# --------------------------------------------------------------------------- #


def test_get_todo_returns_the_persisted_todo(controller, db):
    saved = db.add(Todo.new("read me"))

    assert controller.get_todo(saved.id).text == "read me"


def test_get_todo_raises_for_missing_id(controller):
    with pytest.raises(TodoNotFoundError):
        controller.get_todo(999)


# --------------------------------------------------------------------------- #
# add_todo
# --------------------------------------------------------------------------- #


def test_add_todo_returns_todo_with_assigned_id(controller):
    added = controller.add_todo("write tests")

    assert added.id is not None
    assert added.text == "write tests"
    assert added.completed is False


def test_add_todo_persists_to_the_list(controller):
    controller.add_todo("persist me")

    texts = [t.text for t in controller.list_todos()]
    assert texts == ["persist me"]


# --------------------------------------------------------------------------- #
# toggle_todo
# --------------------------------------------------------------------------- #


def test_toggle_todo_flips_completed_to_true(controller):
    added = controller.add_todo("task")

    toggled = controller.toggle_todo(added.id)

    assert toggled.completed is True
    assert controller.get_todo(added.id).completed is True


def test_toggle_todo_flips_back_to_false(controller):
    added = controller.add_todo("task")
    controller.toggle_todo(added.id)

    toggled_again = controller.toggle_todo(added.id)

    assert toggled_again.completed is False


def test_toggle_todo_raises_for_missing_id(controller):
    with pytest.raises(TodoNotFoundError):
        controller.toggle_todo(999)


# --------------------------------------------------------------------------- #
# edit_todo
# --------------------------------------------------------------------------- #


def test_edit_todo_changes_text(controller):
    added = controller.add_todo("old text")

    edited = controller.edit_todo(added.id, "new text")

    assert edited.text == "new text"
    assert controller.get_todo(added.id).text == "new text"


def test_edit_todo_preserves_completed_flag(controller):
    added = controller.add_todo("task")
    controller.toggle_todo(added.id)

    edited = controller.edit_todo(added.id, "renamed")

    assert edited.completed is True


def test_edit_todo_raises_for_missing_id(controller):
    with pytest.raises(TodoNotFoundError):
        controller.edit_todo(999, "nope")


# --------------------------------------------------------------------------- #
# delete_todo
# --------------------------------------------------------------------------- #


def test_delete_todo_returns_the_deleted_todo(controller):
    added = controller.add_todo("delete me")

    deleted = controller.delete_todo(added.id)

    assert deleted.id == added.id
    assert deleted.text == "delete me"


def test_delete_todo_removes_it_from_the_list(controller):
    added = controller.add_todo("delete me")

    controller.delete_todo(added.id)

    assert controller.list_todos() == []


def test_delete_todo_raises_for_missing_id(controller):
    with pytest.raises(TodoNotFoundError):
        controller.delete_todo(999)


# --------------------------------------------------------------------------- #
# cycle_priority (Feature #6)
# --------------------------------------------------------------------------- #


def test_cycle_priority_none_to_low(controller):
    added = controller.add_todo("task")
    result = controller.cycle_priority(added.id)
    assert result.priority is Priority.LOW


def test_cycle_priority_low_to_medium(controller):
    added = controller.add_todo("task")
    controller.cycle_priority(added.id)  # none → low
    result = controller.cycle_priority(added.id)  # low → medium
    assert result.priority is Priority.MEDIUM


def test_cycle_priority_medium_to_high(controller):
    added = controller.add_todo("task")
    controller.cycle_priority(added.id)
    controller.cycle_priority(added.id)
    result = controller.cycle_priority(added.id)
    assert result.priority is Priority.HIGH


def test_cycle_priority_high_to_none(controller):
    added = controller.add_todo("task")
    for _ in range(3):
        controller.cycle_priority(added.id)  # none→low→medium→high
    result = controller.cycle_priority(added.id)  # high→none
    assert result.priority is None


def test_cycle_priority_full_cycle_returns_to_none(controller):
    """Four consecutive cycles return to none."""
    added = controller.add_todo("task")
    for _ in range(4):
        controller.cycle_priority(added.id)
    final = controller.get_todo(added.id)
    assert final.priority is None


def test_cycle_priority_returns_updated_todo(controller):
    added = controller.add_todo("task")
    result = controller.cycle_priority(added.id)
    assert isinstance(result, Todo)
    assert result.id == added.id
    assert result.priority is Priority.LOW


def test_cycle_priority_raises_for_missing_id(controller):
    with pytest.raises(TodoNotFoundError):
        controller.cycle_priority(999)


def test_cycle_priority_persists_through_list_todos(controller):
    added = controller.add_todo("task")
    controller.cycle_priority(added.id)  # → LOW
    controller.cycle_priority(added.id)  # → MEDIUM
    todos = controller.list_todos()
    assert todos[0].priority is Priority.MEDIUM


# --------------------------------------------------------------------------- #
# list_todos with sort (Feature #6)
# --------------------------------------------------------------------------- #


def test_list_todos_with_priority_sort_passes_through_to_db(controller, db):
    """PRIORITY sort returns tasks ordered by priority DESC."""
    controller.add_todo("a")
    b = controller.add_todo("b")
    db.set_priority(b.id, Priority.HIGH)

    result = controller.list_todos(sort=TodoSort.PRIORITY)
    assert result[0].id == b.id  # HIGH comes first


def test_list_todos_default_sort_unchanged(controller, db):
    """Default sort (no arg) keeps creation order."""
    a = controller.add_todo("a")
    b = controller.add_todo("b")
    assert [t.id for t in controller.list_todos()] == [a.id, b.id]


# --------------------------------------------------------------------------- #
# set_due_date (Feature #7)
# --------------------------------------------------------------------------- #


def test_set_due_date_returns_updated_todo(controller):
    added = controller.add_todo("task")
    result = controller.set_due_date(added.id, date(2026, 7, 10))
    assert isinstance(result, Todo)
    assert result.due_date == date(2026, 7, 10)
    assert controller.get_todo(added.id).due_date == date(2026, 7, 10)


def test_set_due_date_clears_with_none(controller):
    added = controller.add_todo("task")
    controller.set_due_date(added.id, date(2026, 7, 10))
    result = controller.set_due_date(added.id, None)
    assert result.due_date is None
    assert controller.get_todo(added.id).due_date is None


def test_set_due_date_raises_for_missing_id(controller):
    """The _apply path propagates the domain error (row gone)."""
    with pytest.raises(TodoNotFoundError):
        controller.set_due_date(999, date(2026, 7, 10))


def test_set_due_date_persists_through_list_todos(controller):
    added = controller.add_todo("task")
    controller.set_due_date(added.id, date(2026, 7, 10))
    todos = controller.list_todos()
    assert todos[0].due_date == date(2026, 7, 10)


def test_list_todos_with_due_sort_passes_through_to_db(controller):
    a = controller.add_todo("a")
    b = controller.add_todo("b")
    controller.set_due_date(a.id, date(2027, 1, 1))
    controller.set_due_date(b.id, date(2026, 1, 1))

    result = controller.list_todos(sort=TodoSort.DUE)
    assert result[0].id == b.id  # earliest first


# --------------------------------------------------------------------------- #
# Re-exports reachable through the controller layer (Feature #7)
# --------------------------------------------------------------------------- #


def test_parse_due_date_reachable_via_controller_reexport():
    """The screen imports parse_due_date from the controller, not models/db."""
    assert parse_due_date("today", today=date(2026, 7, 4)) == date(2026, 7, 4)


def test_due_date_parse_error_reachable_via_controller_reexport():
    with pytest.raises(DueDateParseError):
        parse_due_date("not a date", today=date(2026, 7, 4))
