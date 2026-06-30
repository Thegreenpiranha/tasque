"""Unit tests for the Todo domain model (Feature #2)."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime

import pytest

from tasque.models import Todo


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
