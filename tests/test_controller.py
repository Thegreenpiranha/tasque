"""Unit tests for TodoController (Feature #4).

All tests use an in-memory SQLite database — never the user's database.
"""

from __future__ import annotations

import pytest

from tasque.controller import TodoController
from tasque.db import Database, TodoNotFoundError
from tasque.models import Todo


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
# cycle_priority — still a seam until Feature #6
# --------------------------------------------------------------------------- #


def test_cycle_priority_raises_not_implemented(controller, db):
    saved = db.add(Todo.new("task"))
    with pytest.raises(NotImplementedError):
        controller.cycle_priority(saved.id)
