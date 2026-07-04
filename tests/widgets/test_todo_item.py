"""Behavioural tests for TodoItem and EmptyState (Features #4, #6).

Tests run through Textual's async `App.run_test()` harness so they assert on
observable DOM state, not private implementation details.
"""

from __future__ import annotations

from datetime import date, timedelta

from textual.app import App, ComposeResult
from textual.widgets import Static

from tasque.models import Priority, Todo
from tasque.widgets.empty_state import EmptyState
from tasque.widgets.todo_item import TodoItem
from tasque.widgets.todo_list import TodoList

# Relative-to-real-today seeding keeps these pilot tests deterministic without
# freezing the clock; the fixed-now boundary precision lives in test_models.py.
_TODAY = date.today()
_YESTERDAY = _TODAY - timedelta(days=1)
_TOMORROW = _TODAY + timedelta(days=1)

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


# --------------------------------------------------------------------------- #
# Priority tag rendering (Feature #6)
# --------------------------------------------------------------------------- #


async def test_priority_none_renders_blank_slot():
    """A todo with no priority shows 4 spaces in the #priority slot."""
    todo = Todo(text="task", id=1, completed=False, priority=None)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        priority_widget = item.query_one("#priority", Static)

        assert str(priority_widget.render()).strip() == ""


async def test_priority_high_renders_H_tag():
    todo = Todo(text="task", id=1, completed=False, priority=Priority.HIGH)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        priority_widget = item.query_one("#priority", Static)

        assert "(H)" in str(priority_widget.render())


async def test_priority_medium_renders_M_tag():
    todo = Todo(text="task", id=1, completed=False, priority=Priority.MEDIUM)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        priority_widget = item.query_one("#priority", Static)

        assert "(M)" in str(priority_widget.render())


async def test_priority_low_renders_L_tag():
    todo = Todo(text="task", id=1, completed=False, priority=Priority.LOW)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        priority_widget = item.query_one("#priority", Static)

        assert "(L)" in str(priority_widget.render())


# --------------------------------------------------------------------------- #
# Priority CSS class (Feature #6)
# --------------------------------------------------------------------------- #


async def test_priority_high_sets_priority_high_class():
    todo = Todo(text="task", id=1, completed=False, priority=Priority.HIGH)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)

        assert item.has_class("-priority-high")
        assert not item.has_class("-priority-medium")
        assert not item.has_class("-priority-low")


async def test_priority_medium_sets_priority_medium_class():
    todo = Todo(text="task", id=1, completed=False, priority=Priority.MEDIUM)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)

        assert item.has_class("-priority-medium")
        assert not item.has_class("-priority-high")
        assert not item.has_class("-priority-low")


async def test_priority_low_sets_priority_low_class():
    todo = Todo(text="task", id=1, completed=False, priority=Priority.LOW)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)

        assert item.has_class("-priority-low")
        assert not item.has_class("-priority-high")
        assert not item.has_class("-priority-medium")


async def test_priority_none_sets_no_priority_class():
    todo = Todo(text="task", id=1, completed=False, priority=None)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)

        assert not item.has_class("-priority-high")
        assert not item.has_class("-priority-medium")
        assert not item.has_class("-priority-low")


async def test_update_todo_changes_priority_tag_without_rebuild():
    """update_todo re-renders the #priority slot via the reactive."""
    todo = Todo(text="task", id=5, completed=False, priority=None)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)

        updated = Todo(text="task", id=5, completed=False, priority=Priority.HIGH)
        todo_list.update_todo(updated)
        await pilot.pause()

        item = app.query_one(TodoItem)
        priority_widget = item.query_one("#priority", Static)
        assert "(H)" in str(priority_widget.render())
        assert item.has_class("-priority-high")


async def test_update_todo_clears_priority_class_when_set_to_none():
    """update_todo removes the priority class when priority is cleared."""
    todo = Todo(text="task", id=5, completed=False, priority=Priority.MEDIUM)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)

        cleared = Todo(text="task", id=5, completed=False, priority=None)
        todo_list.update_todo(cleared)
        await pilot.pause()

        item = app.query_one(TodoItem)
        assert not item.has_class("-priority-high")
        assert not item.has_class("-priority-medium")
        assert not item.has_class("-priority-low")


# --------------------------------------------------------------------------- #
# Accessible label with priority (Feature #6)
# --------------------------------------------------------------------------- #


def test_accessible_label_includes_high_priority():
    item = TodoItem(Todo(text="task", id=1, completed=False, priority=Priority.HIGH))
    assert "high priority" in item.accessible_label


def test_accessible_label_includes_medium_priority():
    item = TodoItem(Todo(text="task", id=1, completed=False, priority=Priority.MEDIUM))
    assert "medium priority" in item.accessible_label


def test_accessible_label_includes_low_priority():
    item = TodoItem(Todo(text="task", id=1, completed=False, priority=Priority.LOW))
    assert "low priority" in item.accessible_label


def test_accessible_label_omits_priority_when_none():
    item = TodoItem(Todo(text="task", id=1, completed=False, priority=None))
    label = item.accessible_label
    assert "priority" not in label


# --------------------------------------------------------------------------- #
# Due-date slot rendering (Feature #7)
# --------------------------------------------------------------------------- #


def _due_text(item: TodoItem) -> str:
    return str(item.query_one("#due", Static).render())


async def test_no_due_date_renders_blank_slot():
    todo = Todo(text="task", id=1, completed=False, due_date=None)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        assert _due_text(item).strip() == ""
        assert not item.has_class("-overdue")
        assert not item.has_class("-due-today")


async def test_overdue_row_renders_overdue_word_and_class():
    todo = Todo(text="task", id=1, completed=False, due_date=_YESTERDAY)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        assert "OVERDUE" in _due_text(item)
        assert _YESTERDAY.strftime("%m-%d") in _due_text(item)
        assert item.has_class("-overdue")
        assert not item.has_class("-due-today")


async def test_due_today_row_renders_due_today_word_and_class():
    todo = Todo(text="task", id=1, completed=False, due_date=_TODAY)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        assert "due today" in _due_text(item)
        assert item.has_class("-due-today")
        assert not item.has_class("-overdue")


async def test_future_row_renders_bare_date_no_class():
    todo = Todo(text="task", id=1, completed=False, due_date=_TOMORROW)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        text = _due_text(item)
        assert "OVERDUE" not in text
        assert "due today" not in text
        assert _TOMORROW.strftime("%m-%d") in text
        assert not item.has_class("-overdue")
        assert not item.has_class("-due-today")


async def test_future_other_year_renders_full_iso():
    """The year rule: a date outside the current year shows full YYYY-MM-DD."""
    other_year = date(_TODAY.year + 1, 1, 15)
    todo = Todo(text="task", id=1, completed=False, due_date=other_year)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        assert other_year.isoformat() in _due_text(item)


async def test_completed_row_suppresses_overdue_shows_dashes():
    """A done row never escalates: no -overdue class, #due reads '──'."""
    todo = Todo(text="task", id=1, completed=True, due_date=_YESTERDAY)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        item = app.query_one(TodoItem)
        assert "──" in _due_text(item)
        assert "OVERDUE" not in _due_text(item)
        assert not item.has_class("-overdue")


async def test_completing_overdue_row_clears_escalation():
    """Toggling complete drops -overdue and flips #due to '──'; undo restores it."""
    todo = Todo(text="task", id=5, completed=False, due_date=_YESTERDAY)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        item = app.query_one(TodoItem)
        assert item.has_class("-overdue")

        todo_list.update_todo(Todo(text="task", id=5, completed=True, due_date=_YESTERDAY))
        await pilot.pause()
        assert not item.has_class("-overdue")
        assert "──" in _due_text(item)

        todo_list.update_todo(Todo(text="task", id=5, completed=False, due_date=_YESTERDAY))
        await pilot.pause()
        assert item.has_class("-overdue")
        assert "OVERDUE" in _due_text(item)


async def test_update_todo_renders_due_slot_without_rebuild():
    todo = Todo(text="task", id=5, completed=False, due_date=None)
    app = _ItemApp(todo)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.update_todo(Todo(text="task", id=5, completed=False, due_date=_TODAY))
        await pilot.pause()

        item = app.query_one(TodoItem)
        assert "due today" in _due_text(item)
        assert item.has_class("-due-today")


# --------------------------------------------------------------------------- #
# Accessible label with due date (Feature #7)
# --------------------------------------------------------------------------- #


def test_accessible_label_includes_overdue():
    item = TodoItem(Todo(text="task", id=1, completed=False, due_date=_YESTERDAY))
    assert "overdue" in item.accessible_label


def test_accessible_label_includes_due_today():
    item = TodoItem(Todo(text="task", id=1, completed=False, due_date=_TODAY))
    assert "due today" in item.accessible_label


def test_accessible_label_future_uses_full_iso():
    """A future row reads the full ISO date, not the compact MM-DD (unambiguous)."""
    item = TodoItem(Todo(text="task", id=1, completed=False, due_date=_TOMORROW))
    assert f"due {_TOMORROW.isoformat()}" in item.accessible_label


def test_accessible_label_omits_due_when_none():
    item = TodoItem(Todo(text="task", id=1, completed=False, due_date=None))
    assert "due" not in item.accessible_label


def test_accessible_label_omits_due_when_completed():
    """A completed row's deadline is moot — the label speaks no due word."""
    item = TodoItem(Todo(text="task", id=1, completed=True, due_date=_YESTERDAY))
    label = item.accessible_label
    assert "overdue" not in label
    assert "due" not in label


def test_accessible_label_order_is_completion_priority_text_due():
    item = TodoItem(
        Todo(text="Report", id=1, completed=False, priority=Priority.HIGH, due_date=_TODAY)
    )
    assert item.accessible_label == "incomplete, high priority, Report, due today"
