"""Behavioural tests for TodoItem and EmptyState (Feature #4).

Tests run through Textual's async `App.run_test()` harness so they assert on
observable DOM state, not private implementation details.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static

from tasque.models import Todo
from tasque.widgets.empty_state import EmptyState
from tasque.widgets.todo_item import TodoItem
from tasque.widgets.todo_list import TodoList

# --------------------------------------------------------------------------- #
# Minimal test harnesses
# --------------------------------------------------------------------------- #


class _ItemApp(App):
    """A minimal app that shows a single TodoItem inside a TodoList."""

    def __init__(self, todo: Todo) -> None:
        super().__init__()
        self._todo = todo

    def compose(self) -> ComposeResult:
        yield TodoList(id="list")

    async def on_mount(self) -> None:
        await self.query_one(TodoList).set_todos([self._todo])


class _EmptyStateApp(App):
    """A minimal app showing a standalone EmptyState for CTA tests."""

    def compose(self) -> ComposeResult:
        yield EmptyState()


# --------------------------------------------------------------------------- #
# Checkbox rendering
# --------------------------------------------------------------------------- #


async def test_incomplete_item_renders_empty_checkbox():
    todo = Todo(text="buy milk", id=1, completed=False)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        checkbox = item.query_one("#checkbox", Static)

        assert "[ ]" in str(checkbox.render())


async def test_completed_item_renders_checked_checkbox():
    todo = Todo(text="buy milk", id=1, completed=True)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        checkbox = item.query_one("#checkbox", Static)

        assert "[x]" in str(checkbox.render())


# --------------------------------------------------------------------------- #
# CSS class state
# --------------------------------------------------------------------------- #


async def test_completed_item_has_done_class():
    todo = Todo(text="task", id=2, completed=True)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)

        assert item.has_class("-done")


async def test_incomplete_item_does_not_have_done_class():
    todo = Todo(text="task", id=3, completed=False)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)

        assert not item.has_class("-done")


# --------------------------------------------------------------------------- #
# Cursor gutter
# --------------------------------------------------------------------------- #


async def test_first_item_shows_cursor_glyph_when_highlighted():
    todo = Todo(text="task", id=4, completed=False)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        gutter = item.query_one("#gutter", Static)

        assert "▸" in str(gutter.render())


# --------------------------------------------------------------------------- #
# todo_id property
# --------------------------------------------------------------------------- #


async def test_todo_id_returns_the_wrapped_todo_id():
    todo = Todo(text="task", id=99, completed=False)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)

        assert item.todo_id == 99


def test_todo_id_is_available_before_mount():
    """A TodoItem knows its id from construction, before the `todo` reactive is
    set in on_mount — so `current_todo_id` is correct during list assembly."""
    item = TodoItem(Todo(text="task", id=7, completed=False))

    assert item.todo_id == 7


# --------------------------------------------------------------------------- #
# update_todo (reactive re-render)
# --------------------------------------------------------------------------- #


async def test_update_todo_changes_checkbox_without_rebuilding_list():
    todo = Todo(text="task", id=5, completed=False)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        todo_list = app.query_one(TodoList)

        # Simulate what the controller would do after a toggle (Feature #5)
        updated = Todo(text="task", id=5, completed=True)
        todo_list.update_todo(updated)
        await pilot.pause()

        checkbox = item.query_one("#checkbox", Static)
        assert "[x]" in str(checkbox.render())
        assert item.has_class("-done")


# --------------------------------------------------------------------------- #
# Accessible label (screen-reader string) — main-screen.md § Accessibility
# --------------------------------------------------------------------------- #


def test_accessible_label_folds_state_before_mount():
    """Incomplete rows read state-first, then the text — available at construction."""
    item = TodoItem(Todo(text="Finish the report", id=1, completed=False))

    assert item.accessible_label == "incomplete, Finish the report"


def test_accessible_label_reads_completed_for_done_items():
    item = TodoItem(Todo(text="Water the plants", id=2, completed=True))

    assert item.accessible_label == "completed, Water the plants"


def test_accessible_label_folds_in_priority_when_set():
    """The label speaks priority between state and text (Feature #6 activates it)."""
    item = TodoItem(Todo(text="Renew passport", id=3, completed=False, priority=3))

    assert item.accessible_label == "incomplete, high priority, Renew passport"


async def test_accessible_label_tracks_state_after_toggle():
    """After a re-render the label reflects the new completion state, not the old."""
    todo = Todo(text="task", id=5, completed=False)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        assert item.accessible_label == "incomplete, task"

        item.todo = Todo(text="task", id=5, completed=True)
        await pilot.pause()

        assert item.accessible_label == "completed, task"


# --------------------------------------------------------------------------- #
# EmptyState — including the cta reactive seam (Feature #5)
# --------------------------------------------------------------------------- #


async def test_empty_state_shows_no_tasks_yet_text():
    app = _EmptyStateApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        empty = app.query_one(EmptyState)

        assert "No tasks yet" in str(empty.render())


async def test_empty_state_shows_cta_line_when_cta_is_set():
    """Verify the watch_cta seam that Feature #5 will activate."""
    app = _EmptyStateApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        empty = app.query_one(EmptyState)
        empty.cta = "Press a to add your first task"
        await pilot.pause()

        content = str(empty.render())
        assert "No tasks yet" in content
        assert "Press a to add your first task" in content


async def test_empty_state_clears_cta_when_reset_to_empty():
    app = _EmptyStateApp()

    async with app.run_test() as pilot:
        await pilot.pause()
        empty = app.query_one(EmptyState)
        empty.cta = "some hint"
        await pilot.pause()
        empty.cta = ""
        await pilot.pause()

        content = str(empty.render())
        assert "No tasks yet" in content
        assert "some hint" not in content
