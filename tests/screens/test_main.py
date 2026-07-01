"""Integration tests for MainScreen (Feature #4).

Tests push MainScreen into a minimal app backed by an in-memory Database and
assert on user-visible DOM state via Textual's `App.run_test()` harness.

Note: always query from `app.screen` (the active `MainScreen`), not from `app`
directly.  Textual's `App.query()` does not traverse into pushed screens.
"""

from __future__ import annotations

import pytest
from textual.app import App

from tasque.controller import TodoController
from tasque.db import Database
from tasque.models import Todo
from tasque.screens.main import MainScreen
from tasque.widgets.empty_state import EmptyState
from tasque.widgets.todo_item import TodoItem
from tasque.widgets.todo_list import TodoList

# --------------------------------------------------------------------------- #
# Fixtures / harness
# --------------------------------------------------------------------------- #


@pytest.fixture
def mem_db():
    database = Database(":memory:")
    try:
        yield database
    finally:
        database.close()


def _make_controller(db: Database) -> TodoController:
    return TodoController(db)


class _TestApp(App):
    """Minimal app that pushes a MainScreen for testing."""

    def __init__(self, controller: TodoController) -> None:
        super().__init__()
        self._controller = controller

    def on_mount(self) -> None:
        self.push_screen(MainScreen(self._controller))


# --------------------------------------------------------------------------- #
# Empty state
# --------------------------------------------------------------------------- #


async def test_empty_db_shows_empty_state(mem_db):
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen  # MainScreen
        empty = screen.query_one(EmptyState)

        assert not empty.has_class("-hidden")


async def test_empty_db_hides_todo_list(mem_db):
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)

        assert todo_list.has_class("-hidden")


async def test_empty_db_shows_no_tasks_text(mem_db):
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        empty = screen.query_one(EmptyState)

        assert "No tasks yet" in str(empty.render())


async def test_empty_db_border_title_shows_zero_counts(mem_db):
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        panel = screen.query_one("#list-panel")

        assert "0 active" in (panel.border_title or "")
        assert "0 done" in (panel.border_title or "")


# --------------------------------------------------------------------------- #
# Populated state
# --------------------------------------------------------------------------- #


async def test_populated_db_hides_empty_state(mem_db):
    mem_db.add(Todo.new("task one"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        empty = screen.query_one(EmptyState)

        assert empty.has_class("-hidden")


async def test_populated_db_shows_todo_list(mem_db):
    mem_db.add(Todo.new("task one"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)

        assert not todo_list.has_class("-hidden")


async def test_three_seeded_todos_render_as_three_items(mem_db):
    mem_db.add(Todo.new("alpha"))
    mem_db.add(Todo.new("beta"))
    mem_db.add(Todo.new("gamma"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        items = screen.query(TodoItem)

        assert len(items) == 3


async def test_items_render_in_creation_order(mem_db):
    a = mem_db.add(Todo.new("first"))
    b = mem_db.add(Todo.new("second"))
    c = mem_db.add(Todo.new("third"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        items = list(screen.query(TodoItem))

        assert [item.todo_id for item in items] == [a.id, b.id, c.id]


async def test_first_item_has_highlight_class(mem_db):
    mem_db.add(Todo.new("first"))
    mem_db.add(Todo.new("second"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        items = list(screen.query(TodoItem))

        assert items[0].has_class("-highlight")


async def test_border_title_counts_active_and_done(mem_db):
    mem_db.add(Todo.new("active task"))
    saved = mem_db.add(Todo.new("done task"))
    mem_db.set_completed(saved.id, True)
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        panel = screen.query_one("#list-panel")

        assert "1 active" in (panel.border_title or "")
        assert "1 done" in (panel.border_title or "")


async def test_completed_todo_renders_with_done_class(mem_db):
    saved = mem_db.add(Todo.new("done task"))
    mem_db.set_completed(saved.id, True)
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        item = screen.query_one(TodoItem)

        assert item.has_class("-done")


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #


async def test_j_key_moves_highlight_to_second_item(mem_db):
    mem_db.add(Todo.new("first"))
    mem_db.add(Todo.new("second"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)
        todo_list.focus()
        await pilot.press("j")
        await pilot.pause()

        items = list(screen.query(TodoItem))
        assert items[1].has_class("-highlight")
        assert not items[0].has_class("-highlight")
