"""Unit tests for TodoController (Feature #4).

All tests use an in-memory SQLite database — never the user's database.
"""

from __future__ import annotations

import pytest

from tasque.controller import TodoController
from tasque.db import Database
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
# Mutation seams — must raise NotImplementedError until Feature #5/#6
# --------------------------------------------------------------------------- #


def test_add_todo_raises_not_implemented(controller):
    with pytest.raises(NotImplementedError):
        controller.add_todo("anything")


def test_toggle_todo_raises_not_implemented(controller, db):
    saved = db.add(Todo.new("task"))
    with pytest.raises(NotImplementedError):
        controller.toggle_todo(saved.id)


def test_edit_todo_raises_not_implemented(controller, db):
    saved = db.add(Todo.new("task"))
    with pytest.raises(NotImplementedError):
        controller.edit_todo(saved.id, "new text")


def test_delete_todo_raises_not_implemented(controller, db):
    saved = db.add(Todo.new("task"))
    with pytest.raises(NotImplementedError):
        controller.delete_todo(saved.id)


def test_cycle_priority_raises_not_implemented(controller, db):
    saved = db.add(Todo.new("task"))
    with pytest.raises(NotImplementedError):
        controller.cycle_priority(saved.id)
