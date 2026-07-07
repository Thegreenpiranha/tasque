"""Integration tests for MainScreen (Features #4, #6).

Tests push MainScreen into a minimal app backed by an in-memory Database and
assert on user-visible DOM state via Textual's `App.run_test()` harness.

Note: always query from `app.screen` (the active `MainScreen`), not from `app`
directly.  Textual's `App.query()` does not traverse into pushed screens.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from textual.app import App
from textual.widgets import Input, Static

from tasque.app import TasqueApp
from tasque.controller import TodoController
from tasque.db import Database, PersistenceError, TodoNotFoundError
from tasque.models import Priority, Todo
from tasque.screens.delete_confirm import DeleteConfirmScreen
from tasque.screens.main import MainScreen
from tasque.widgets.empty_state import EmptyState
from tasque.widgets.input_bar import InputBar
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


# --------------------------------------------------------------------------- #
# Helpers for the Feature #5 mutation flows
# --------------------------------------------------------------------------- #


def _item_texts(screen) -> list[str]:
    return [str(item.query_one("#title").render()) for item in screen.query(TodoItem)]


def _capture_notifications(app) -> list[str]:
    """Replace app.notify with a recorder; return the list it appends to."""
    messages: list[str] = []
    app.notify = lambda message, **kwargs: messages.append(message)  # type: ignore[assignment]
    return messages


def _shown_hints(screen) -> list[tuple[str, str]]:
    """The (key, description) pairs the Footer would show for the active screen."""
    return [
        (binding.binding.key, binding.binding.description)
        for binding in screen.active_bindings.values()
        if binding.binding.show
    ]


# --------------------------------------------------------------------------- #
# Add flow
# --------------------------------------------------------------------------- #


async def test_add_creates_row_and_keeps_bar_open(mem_db):
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("a")
        await pilot.pause()
        screen.query_one("#bar-input", Input).value = "buy milk"
        await pilot.press("enter")
        await pilot.pause()

        assert _item_texts(screen) == ["buy milk"]
        bar = screen.query_one(InputBar)
        assert not bar.has_class("-hidden")  # stays open for rapid multi-add
        assert screen.query_one("#bar-input", Input).value == ""  # cleared


async def test_add_appends_at_the_bottom(mem_db):
    mem_db.add(Todo.new("first"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("a")
        await pilot.pause()
        screen.query_one("#bar-input", Input).value = "second"
        await pilot.press("enter")
        await pilot.pause()

        assert _item_texts(screen) == ["first", "second"]


async def test_empty_add_creates_no_row(mem_db):
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("enter")  # empty field
        await pilot.pause()

        assert len(screen.query(TodoItem)) == 0
        assert screen.query_one(InputBar).has_class("-invalid")


async def test_a_from_empty_state_opens_the_bar(mem_db):
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("a")
        await pilot.pause()

        assert not screen.query_one(InputBar).has_class("-hidden")


async def test_reopening_add_while_open_keeps_single_bar(mem_db):
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("a")
        await pilot.pause()
        screen.query_one("#bar-input", Input).value = "half-typed"
        # Defense-in-depth guard: a stray `a` reaching the screen must not
        # reset or stack a second bar (main-screen.md "no stacked bars").
        screen.action_add_todo()
        await pilot.pause()

        assert len(screen.query(InputBar)) == 1
        assert screen.query_one("#bar-input", Input).value == "half-typed"


async def test_add_persistence_failure_keeps_typed_text(mem_db):
    controller = _make_controller(mem_db)

    def _boom(text):
        raise PersistenceError("disk gone")

    controller.add_todo = _boom  # type: ignore[method-assign]
    app = _TestApp(controller)

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#bar-input", Input).value = "retry me"
        await pilot.press("enter")
        await pilot.pause()

        assert any("Error" in m for m in messages)
        bar = app.screen.query_one(InputBar)
        assert not bar.has_class("-hidden")  # stays open for retry
        assert app.screen.query_one("#bar-input", Input).value == "retry me"


# --------------------------------------------------------------------------- #
# Toggle flow
# --------------------------------------------------------------------------- #


async def test_space_toggles_completion(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("space")
        await pilot.pause()

        item = screen.query_one(TodoItem)
        assert item.has_class("-done")
        assert str(item.query_one("#checkbox").render()) == "[x]"


async def test_space_toggles_back_off(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("space")
        await pilot.pause()
        await pilot.press("space")
        await pilot.pause()

        item = screen.query_one(TodoItem)
        assert not item.has_class("-done")
        assert str(item.query_one("#checkbox").render()) == "[ ]"


async def test_toggle_updates_border_title_counts(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("space")
        await pilot.pause()

        panel = screen.query_one("#list-panel")
        assert "0 active" in (panel.border_title or "")
        assert "1 done" in (panel.border_title or "")


# --------------------------------------------------------------------------- #
# Edit flow
# --------------------------------------------------------------------------- #


async def test_edit_prefills_bar_with_row_text(mem_db):
    mem_db.add(Todo.new("original"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("e")
        await pilot.pause()

        bar = screen.query_one(InputBar)
        assert not bar.has_class("-hidden")
        assert screen.query_one("#bar-input", Input).value == "original"


async def test_edit_saves_new_text_in_place(mem_db):
    saved = mem_db.add(Todo.new("original"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("e")
        await pilot.pause()
        screen.query_one("#bar-input", Input).value = "edited text"
        await pilot.press("enter")
        await pilot.pause()

        items = list(screen.query(TodoItem))
        assert len(items) == 1
        assert items[0].todo_id == saved.id
        assert str(items[0].query_one("#title").render()) == "edited text"
        assert screen.query_one(InputBar).has_class("-hidden")
        assert screen.query_one(TodoList).has_focus


async def test_edit_escape_discards_change(mem_db):
    mem_db.add(Todo.new("original"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("e")
        await pilot.pause()
        screen.query_one("#bar-input", Input).value = "throwaway"
        await pilot.press("escape")
        await pilot.pause()

        assert _item_texts(screen) == ["original"]
        assert screen.query_one(InputBar).has_class("-hidden")


# --------------------------------------------------------------------------- #
# Delete flow
# --------------------------------------------------------------------------- #


async def test_delete_confirmed_removes_row_and_lands_cursor(mem_db):
    a = mem_db.add(Todo.new("first"))
    mem_db.add(Todo.new("second"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()  # cursor on "first" (index 0)
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, DeleteConfirmScreen)
        await pilot.press("y")
        await pilot.pause()

        assert _item_texts(app.screen) == ["second"]
        # deleted index 0 → "second" slides up to index 0 and is highlighted
        todo_list = app.screen.query_one(TodoList)
        assert todo_list.current_todo_id != a.id
        assert app.screen.query(TodoItem)[0].has_class("-highlight")


async def test_delete_last_row_clamps_cursor_to_previous(mem_db):
    mem_db.add(Todo.new("first"))
    mem_db.add(Todo.new("second"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)
        todo_list.focus()
        await pilot.press("G")  # cursor on the last row ("second")
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()

        assert _item_texts(app.screen) == ["first"]
        assert app.screen.query_one(TodoList).current_todo_id is not None
        assert app.screen.query(TodoItem)[0].has_class("-highlight")


async def test_delete_cancelled_keeps_row(mem_db):
    mem_db.add(Todo.new("keep me"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert _item_texts(app.screen) == ["keep me"]


async def test_delete_only_row_shows_empty_state(mem_db):
    mem_db.add(Todo.new("last one"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()

        assert app.screen.query_one(EmptyState).has_class("-hidden") is False
        assert app.screen.query_one(TodoList).has_class("-hidden") is True


async def test_delete_shows_success_toast(mem_db):
    mem_db.add(Todo.new("delete me"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        app.screen.query_one(TodoList).focus()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()

        assert any("Deleted" in m and "delete me" in m for m in messages)


# --------------------------------------------------------------------------- #
# State-guard: action keys inert while the bar is open
# --------------------------------------------------------------------------- #


async def test_delete_key_inert_while_input_bar_open(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("a")  # open the bar; input takes focus
        await pilot.pause()
        await pilot.press("d")  # should type a literal "d", not open the modal
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)  # no modal pushed
        assert "d" in screen.query_one("#bar-input", Input).value


# --------------------------------------------------------------------------- #
# Failure path: controller raises → error toast, row unchanged
# --------------------------------------------------------------------------- #


async def test_edit_failure_shows_error_toast_and_keeps_text(mem_db):
    saved = mem_db.add(Todo.new("original"))
    controller = _make_controller(mem_db)

    def _boom(todo_id, text):
        raise TodoNotFoundError(todo_id)

    controller.edit_todo = _boom  # type: ignore[method-assign]
    app = _TestApp(controller)

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        app.screen.query_one(TodoList).focus()
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#bar-input", Input).value = "new text"
        await pilot.press("enter")
        await pilot.pause()

        assert any("Error" in m for m in messages)
        # The persisted row keeps its old text (the write never happened).
        assert mem_db.get(saved.id).text == "original"


async def test_toggle_failure_shows_error_toast_and_leaves_row_unchanged(mem_db):
    """main-screen.md §Error: a failed toggle surfaces a toast, never a crash."""
    mem_db.add(Todo.new("task"))
    controller = _make_controller(mem_db)

    def _boom(todo_id):
        raise TodoNotFoundError(todo_id)

    controller.toggle_todo = _boom  # type: ignore[method-assign]
    app = _TestApp(controller)

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        app.screen.query_one(TodoList).focus()
        await pilot.press("space")
        await pilot.pause()

        assert any("Error" in m for m in messages)
        assert not app.screen.query_one(TodoItem).has_class("-done")


async def test_edit_request_failure_shows_error_toast_and_opens_no_bar(mem_db):
    """edit-screen.md §Error (row deleted): pressing `e` on a gone row toasts, no bar."""
    mem_db.add(Todo.new("task"))
    controller = _make_controller(mem_db)

    def _boom(todo_id):
        raise TodoNotFoundError(todo_id)

    controller.get_todo = _boom  # type: ignore[method-assign]
    app = _TestApp(controller)

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        app.screen.query_one(TodoList).focus()
        await pilot.press("e")
        await pilot.pause()

        assert any("Error" in m for m in messages)
        assert app.screen.query_one(InputBar).has_class("-hidden")


async def test_delete_request_failure_shows_error_toast_and_opens_no_modal(mem_db):
    """delete-confirmation.md §Error (row already gone): `d` toasts, no modal."""
    mem_db.add(Todo.new("task"))
    controller = _make_controller(mem_db)

    def _boom(todo_id):
        raise TodoNotFoundError(todo_id)

    controller.get_todo = _boom  # type: ignore[method-assign]
    app = _TestApp(controller)

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        app.screen.query_one(TodoList).focus()
        await pilot.press("d")
        await pilot.pause()

        assert any("Error" in m for m in messages)
        assert isinstance(app.screen, MainScreen)  # no modal was pushed


async def test_delete_confirm_failure_shows_error_toast_and_keeps_row(mem_db):
    """delete-confirmation.md §Error (persistence): confirmed delete that fails
    toasts and keeps the list's last good render."""
    mem_db.add(Todo.new("keep me"))
    controller = _make_controller(mem_db)

    def _boom(todo_id):
        raise PersistenceError("disk gone")

    controller.delete_todo = _boom  # type: ignore[method-assign]
    app = _TestApp(controller)

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        app.screen.query_one(TodoList).focus()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()

        assert any("Error" in m for m in messages)
        assert _item_texts(app.screen) == ["keep me"]


# --------------------------------------------------------------------------- #
# Help binding (placeholder until a later feature)
# --------------------------------------------------------------------------- #


async def test_help_key_shows_placeholder_notification(mem_db):
    """The `?` binding (main-screen.md keybindings) is wired to a placeholder toast."""
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        await pilot.press("question_mark")
        await pilot.pause()

        assert any("Help" in m for m in messages)


# --------------------------------------------------------------------------- #
# Enter toggles (alias of Space) — reviewer suggestion
# --------------------------------------------------------------------------- #


async def test_enter_toggles_completion(mem_db):
    """Enter is the toggle alias of Space (main-screen.md keybindings table)."""
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("enter")
        await pilot.pause()

        item = screen.query_one(TodoItem)
        assert item.has_class("-done")
        assert str(item.query_one("#checkbox").render()) == "[x]"


# --------------------------------------------------------------------------- #
# Empty-state CTA timing — the CTA is part of the resting empty state
# --------------------------------------------------------------------------- #


async def test_empty_state_shows_add_cta_at_rest(mem_db):
    """First run: the CTA is visible without pressing `a` (main-screen.md §Empty)."""
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        empty = app.screen.query_one(EmptyState)

        assert not empty.has_class("-hidden")
        assert "add your first task" in str(empty.render())


async def test_cta_present_after_deleting_the_last_row(mem_db):
    """Clearing the list returns to the resting empty state, CTA and all."""
    mem_db.add(Todo.new("last one"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.query_one(TodoList).focus()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()

        empty = app.screen.query_one(EmptyState)
        assert not empty.has_class("-hidden")
        assert "add your first task" in str(empty.render())


# --------------------------------------------------------------------------- #
# Footer hint swap — mode-dependent hints (input-bar / edit-screen / delete specs)
# --------------------------------------------------------------------------- #


async def test_footer_idle_shows_list_action_hints(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.pause()

        hints = dict(_shown_hints(screen))
        assert hints.get("space") == "Toggle"
        assert hints.get("e") == "Edit"
        assert hints.get("d") == "Delete"
        assert hints.get("a") == "Add"


async def test_footer_add_mode_shows_add_task_and_cancel(mem_db):
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()

        hints = dict(_shown_hints(app.screen))
        assert hints.get("enter") == "Add task"
        assert hints.get("escape") == "Cancel"
        # The list-idle hints are gone while typing.
        assert "a" not in hints


async def test_footer_add_mode_swaps_cancel_to_done_after_first_add(mem_db):
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#bar-input", Input).value = "milk"
        await pilot.press("enter")
        await pilot.pause()

        hints = dict(_shown_hints(app.screen))
        assert hints.get("enter") == "Add task"
        assert hints.get("escape") == "Done"  # ≥1 task added this session


async def test_footer_edit_mode_shows_save(mem_db):
    mem_db.add(Todo.new("original"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.query_one(TodoList).focus()
        await pilot.press("e")
        await pilot.pause()

        hints = dict(_shown_hints(app.screen))
        assert hints.get("enter") == "Save"
        assert hints.get("escape") == "Cancel"


async def test_footer_delete_modal_shows_delete_and_cancel(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.query_one(TodoList).focus()
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, DeleteConfirmScreen)

        hints = dict(_shown_hints(app.screen))
        assert hints.get("y") == "Delete"
        assert hints.get("n") == "Cancel"


# --------------------------------------------------------------------------- #
# Priority cycle — `p` key (Feature #6)
# --------------------------------------------------------------------------- #


def _priority_text(screen) -> str:
    """Text content of the #priority slot on the first TodoItem."""
    return str(screen.query_one(TodoItem).query_one("#priority", Static).render())


async def test_p_cycles_priority_none_to_low(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("p")
        await pilot.pause()

        assert "(L)" in _priority_text(screen)
        assert screen.query_one(TodoItem).has_class("-priority-low")


async def test_p_cycles_priority_low_to_medium(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("p")
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()

        assert "(M)" in _priority_text(screen)
        assert screen.query_one(TodoItem).has_class("-priority-medium")


async def test_p_cycles_priority_to_high(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        for _ in range(3):
            await pilot.press("p")
            await pilot.pause()

        assert "(H)" in _priority_text(screen)
        assert screen.query_one(TodoItem).has_class("-priority-high")


async def test_p_cycles_priority_high_back_to_none(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        for _ in range(4):
            await pilot.press("p")
            await pilot.pause()

        text = _priority_text(screen).strip()
        assert text == ""
        item = screen.query_one(TodoItem)
        assert not item.has_class("-priority-high")
        assert not item.has_class("-priority-medium")
        assert not item.has_class("-priority-low")


async def test_p_in_created_mode_keeps_cursor_index(mem_db):
    """In creation-order sort, pressing p keeps the cursor on the same row (no re-sort)."""
    mem_db.add(Todo.new("first"))
    mem_db.add(Todo.new("second"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)
        todo_list.focus()
        # Move to second row
        await pilot.press("j")
        await pilot.pause()
        second_id = todo_list.current_todo_id

        await pilot.press("p")
        await pilot.pause()

        # Cursor must stay on the same task
        assert todo_list.current_todo_id == second_id


async def test_p_on_empty_list_is_noop(mem_db):
    """p on an empty list does not crash."""
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("p")  # no row; should be silent
        await pilot.pause()

        assert len(screen.query(TodoItem)) == 0


async def test_p_failure_shows_error_toast(mem_db):
    """If cycle_priority raises (row deleted), an error toast appears, no crash."""
    mem_db.add(Todo.new("task"))
    controller = _make_controller(mem_db)

    def _boom(todo_id):
        raise TodoNotFoundError(todo_id)

    controller.cycle_priority = _boom  # type: ignore[method-assign]
    app = _TestApp(controller)

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        app.screen.query_one(TodoList).focus()
        await pilot.press("p")
        await pilot.pause()

        assert any("Error" in m for m in messages)


# --------------------------------------------------------------------------- #
# Sort toggle — `s` key (Feature #6)
# --------------------------------------------------------------------------- #


async def test_s_reorders_list_by_priority(mem_db):
    """After pressing s, high-priority tasks appear before low-priority ones."""
    low = mem_db.add(Todo.new("low"))
    mem_db.set_priority(low.id, Priority.LOW)
    high = mem_db.add(Todo.new("high"))
    mem_db.set_priority(high.id, Priority.HIGH)

    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        # Initially in creation order: low, high
        items = list(screen.query(TodoItem))
        assert items[0].todo_id == low.id

        await pilot.press("s")
        await pilot.pause()

        items = list(screen.query(TodoItem))
        assert items[0].todo_id == high.id  # high first after sort


async def test_s_keeps_cursor_on_same_task(mem_db):
    """The cursor follows the current task across a sort toggle (keep_id)."""
    low = mem_db.add(Todo.new("low"))
    mem_db.set_priority(low.id, Priority.LOW)
    mem_db.add(Todo.new("high-priority"))

    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)
        todo_list.focus()
        # Cursor starts on "low" (index 0, first row)
        task_id_before = todo_list.current_todo_id

        await pilot.press("s")
        await pilot.pause()

        # After sort, cursor should still be on the same task
        assert todo_list.current_todo_id == task_id_before


async def test_s_shows_sort_notification(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        await pilot.press("s")
        await pilot.pause()

        assert any("priority" in m.lower() for m in messages)


async def test_s_adds_by_priority_to_border_title(mem_db):
    """The border-title gains '· by priority' when sort is PRIORITY."""
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        panel = screen.query_one("#list-panel")

        assert "by priority" not in (panel.border_title or "")

        await pilot.press("s")
        await pilot.pause()

        assert "by priority" in (panel.border_title or "")


async def test_s_toggle_back_removes_by_priority_from_border_title(mem_db):
    """Toggling back to creation order removes the '· by priority' suffix."""
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("s")
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()

        panel = screen.query_one("#list-panel")
        assert "by priority" not in (panel.border_title or "")


async def test_footer_shows_priority_and_sort_hints(mem_db):
    """p Priority and s Sort show in the footer while the list has focus."""
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.query_one(TodoList).focus()
        await pilot.pause()

        hints = dict(_shown_hints(app.screen))
        assert hints.get("p") == "Priority"
        assert hints.get("s") == "Sort"


# --------------------------------------------------------------------------- #
# Priority cycle in PRIORITY sort mode (Feature #6)
# --------------------------------------------------------------------------- #


async def test_p_in_priority_mode_keeps_cursor_on_cycled_task(mem_db):
    """In priority sort, pressing p re-sorts; cursor follows the cycled task (keep_id).

    Setup: high (id=1, added first) and low (id=2, added second).
    Creation sort: [high, low] — cursor on high (index 0).
    After s: priority sort [high (HIGH), low (LOW)] — same idx-0 position.
    After p: high cycles HIGH→None, sinks to idx=1; cursor must follow high to idx=1.
    """
    # high is added FIRST so it is at index 0 in creation sort (cursor there on load).
    high = mem_db.add(Todo.new("high"))
    mem_db.set_priority(high.id, Priority.HIGH)
    low = mem_db.add(Todo.new("low"))
    mem_db.set_priority(low.id, Priority.LOW)

    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)
        todo_list.focus()

        # Initial cursor on high (creation sort, idx=0, keep_id=high.id on sort).
        assert todo_list.current_todo_id == high.id

        # Switch to priority sort: high(HIGH) still at idx=0, low(LOW) at idx=1.
        # keep_id=high.id → highlight_id keeps cursor on high.
        await pilot.press("s")
        await pilot.pause()
        assert todo_list.current_todo_id == high.id

        # Cycle high: HIGH → None. It sinks below low (NULLS LAST).
        # New order: [low (idx=0), high (idx=1)]. Cursor follows high to idx=1.
        await pilot.press("p")
        await pilot.pause()

        assert todo_list.current_todo_id == high.id


# --------------------------------------------------------------------------- #
# Toggle complete in PRIORITY sort mode (Feature #6)
# --------------------------------------------------------------------------- #


async def test_toggle_in_priority_mode_cursor_stays_on_position(mem_db):
    """Completing a task in priority sort leaves the cursor at the same index
    (the next active task slides in), NOT following the completed task down."""
    high = mem_db.add(Todo.new("high"))
    mem_db.set_priority(high.id, Priority.HIGH)
    low = mem_db.add(Todo.new("low"))
    mem_db.set_priority(low.id, Priority.LOW)

    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)
        todo_list.focus()

        # Switch to priority sort: high appears first (index 0), low second
        await pilot.press("s")
        await pilot.pause()
        assert todo_list.current_todo_id == high.id  # cursor on "high"

        # Complete "high" — it should slide to the done band at the bottom
        await pilot.press("space")
        await pilot.pause()

        # Cursor stays at index 0 — "low" now occupies that slot
        assert todo_list.current_todo_id == low.id


async def test_toggle_in_created_mode_still_works_in_place(mem_db):
    """In creation-order mode, toggle is still an in-place update (no re-sort)."""
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("space")
        await pilot.pause()

        # Item is done, list still has one item, cursor unchanged
        item = screen.query_one(TodoItem)
        assert item.has_class("-done")


# --------------------------------------------------------------------------- #
# Done dims the priority tag — the load-bearing CSS source order (Feature #6)
# --------------------------------------------------------------------------- #
#
# Uses the real TasqueApp so tasque.tcss is actually loaded (the bare _TestApp /
# _ItemApp harnesses don't set CSS_PATH, so their computed colours are default).
# A class assertion (-done + -priority-high) can't catch a regression here: both
# classes are present regardless of rule order. Only the *resolved colour* proves
# the `.-done > #priority` rule wins the equal-specificity tie — which it does
# only while it sits AFTER the `.-priority-*` block (priority.md §CSS,
# LEARNINGS 2026-07-03). Moving that rule up would leave a done HIGH tag bright
# $error and fail both assertions below.


async def test_done_high_priority_tag_dims_instead_of_error_colour(mem_db):
    active = mem_db.add(Todo.new("active high"))
    mem_db.set_priority(active.id, Priority.HIGH)
    done = mem_db.add(Todo.new("done high"))
    mem_db.set_priority(done.id, Priority.HIGH)
    mem_db.set_completed(done.id, True)

    app = TasqueApp(controller=_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        items = {item.todo_id: item for item in app.screen.query(TodoItem)}
        active_colour = items[active.id].query_one("#priority", Static).styles.color
        done_priority_colour = items[done.id].query_one("#priority", Static).styles.color
        done_title_colour = items[done.id].query_one("#title", Static).styles.color

        # The done tag drops the bright $error priority colour ...
        assert done_priority_colour != active_colour
        # ... and dims to the same disabled colour as the done row's title.
        assert done_priority_colour == done_title_colour


# --------------------------------------------------------------------------- #
# Due date — `D` set/clear flow (Feature #7)
# --------------------------------------------------------------------------- #

_TODAY = date.today()
_YESTERDAY = _TODAY - timedelta(days=1)
_TOMORROW = _TODAY + timedelta(days=1)


def _due_text(screen) -> str:
    return str(screen.query_one(TodoItem).query_one("#due", Static).render())


async def test_D_opens_due_bar_empty_for_undated_row(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("D")
        await pilot.pause()

        bar = screen.query_one(InputBar)
        assert not bar.has_class("-hidden")
        assert bar.border_title == "Due date"
        assert screen.query_one("#bar-input", Input).value == ""


async def test_D_prefills_bar_with_existing_due_date(mem_db):
    saved = mem_db.add(Todo.new("task"))
    mem_db.set_due_date(saved.id, date(2026, 7, 10))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("D")
        await pilot.pause()

        assert screen.query_one("#bar-input", Input).value == "2026-07-10"


async def test_setting_due_date_persists_and_renders(mem_db):
    saved = mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("D")
        await pilot.pause()
        screen.query_one("#bar-input", Input).value = "today"
        await pilot.press("enter")
        await pilot.pause()

        assert mem_db.get(saved.id).due_date == _TODAY
        assert "due today" in _due_text(screen)
        assert screen.query_one(InputBar).has_class("-hidden")
        assert screen.query_one(TodoList).has_focus


async def test_clearing_due_date_with_blank_field(mem_db):
    saved = mem_db.add(Todo.new("task"))
    mem_db.set_due_date(saved.id, date(2026, 7, 10))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("D")
        await pilot.pause()
        screen.query_one("#bar-input", Input).value = ""
        await pilot.press("enter")
        await pilot.pause()

        assert mem_db.get(saved.id).due_date is None
        assert _due_text(screen).strip() == ""
        assert screen.query_one(InputBar).has_class("-hidden")


async def test_junk_due_date_pulses_invalid_and_keeps_bar_open(mem_db):
    saved = mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("D")
        await pilot.pause()
        screen.query_one("#bar-input", Input).value = "not a date"
        await pilot.press("enter")
        await pilot.pause()

        bar = screen.query_one(InputBar)
        assert bar.has_class("-invalid")
        assert not bar.has_class("-hidden")  # stays open to fix
        assert screen.query_one("#bar-input", Input).value == "not a date"
        assert mem_db.get(saved.id).due_date is None  # nothing persisted


async def test_junk_due_date_shows_inline_parse_hint(mem_db):
    """A rejected date surfaces the spec's inline hint text so the feedback is
    words + pulse, never hue alone (due-dates.md Q3)."""
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("D")
        await pilot.pause()
        screen.query_one("#bar-input", Input).value = "not a date"
        await pilot.press("enter")
        await pilot.pause()

        bar = screen.query_one(InputBar)
        assert bar.border_subtitle == "Can't read that date — try YYYY-MM-DD, today, +3"


async def test_overdue_seed_renders_overdue_and_class(mem_db):
    saved = mem_db.add(Todo.new("late task"))
    mem_db.set_due_date(saved.id, _YESTERDAY)
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert "OVERDUE" in _due_text(screen)
        assert screen.query_one(TodoItem).has_class("-overdue")


async def test_completing_overdue_row_clears_escalation_in_created_sort(mem_db):
    saved = mem_db.add(Todo.new("late task"))
    mem_db.set_due_date(saved.id, _YESTERDAY)
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("space")  # complete it
        await pilot.pause()

        item = screen.query_one(TodoItem)
        assert item.has_class("-done")
        assert not item.has_class("-overdue")
        assert "──" in _due_text(screen)


async def test_D_key_inert_while_input_bar_open(mem_db):
    """D is a TodoList binding — with the bar open it types a literal, no second bar."""
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("a")  # open add bar; input takes focus
        await pilot.pause()
        await pilot.press("D")  # should type "D", not reopen in due mode
        await pilot.pause()

        assert screen.query_one(InputBar).border_title == "New task"  # still add mode
        assert "D" in screen.query_one("#bar-input", Input).value


async def test_D_request_failure_shows_error_toast_and_opens_no_bar(mem_db):
    mem_db.add(Todo.new("task"))
    controller = _make_controller(mem_db)

    def _boom(todo_id):
        raise TodoNotFoundError(todo_id)

    controller.get_todo = _boom  # type: ignore[method-assign]
    app = _TestApp(controller)

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        app.screen.query_one(TodoList).focus()
        await pilot.press("D")
        await pilot.pause()

        assert any("Error" in m for m in messages)
        assert app.screen.query_one(InputBar).has_class("-hidden")


async def test_set_due_failure_shows_error_toast(mem_db):
    """Row deleted out from under the bar → toast, bar closes, no crash."""
    mem_db.add(Todo.new("task"))
    controller = _make_controller(mem_db)
    app = _TestApp(controller)

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        screen = app.screen
        screen.query_one(TodoList).focus()
        await pilot.press("D")
        await pilot.pause()

        # Break the write after the bar is open.
        def _boom(todo_id, due):
            raise TodoNotFoundError(todo_id)

        controller.set_due_date = _boom  # type: ignore[method-assign]
        screen.query_one("#bar-input", Input).value = "today"
        await pilot.press("enter")
        await pilot.pause()

        assert any("Error" in m for m in messages)
        assert isinstance(app.screen, MainScreen)
        assert screen.query_one(InputBar).has_class("-hidden")


async def test_p_in_due_sort_stays_in_place(mem_db):
    """A priority cycle does not re-rank in DUE sort (only a due change does)."""
    a = mem_db.add(Todo.new("a"))
    mem_db.set_due_date(a.id, _TODAY)
    b = mem_db.add(Todo.new("b"))
    mem_db.set_due_date(b.id, _TOMORROW)
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)
        todo_list.focus()
        await pilot.press("s")  # → PRIORITY
        await pilot.pause()
        await pilot.press("s")  # → DUE
        await pilot.pause()
        # a (today) is first; cursor on a.
        assert todo_list.current_todo_id == a.id
        await pilot.press("p")  # cycle a's priority; DUE order unaffected
        await pilot.pause()
        assert [i.todo_id for i in screen.query(TodoItem)] == [a.id, b.id]


# --------------------------------------------------------------------------- #
# Due date — sort cycle & re-rank (Feature #7)
# --------------------------------------------------------------------------- #


async def test_s_cycles_created_priority_due_created(mem_db):
    """The `s` sort cycle is three-way: creation → priority → due → creation."""
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        panel = screen.query_one("#list-panel")

        assert "by priority" not in (panel.border_title or "")
        assert "by due" not in (panel.border_title or "")

        await pilot.press("s")  # → priority
        await pilot.pause()
        assert "by priority" in (panel.border_title or "")

        await pilot.press("s")  # → due
        await pilot.pause()
        assert "by due" in (panel.border_title or "")
        assert "by priority" not in (panel.border_title or "")

        await pilot.press("s")  # → creation (suffix-free)
        await pilot.pause()
        assert "by due" not in (panel.border_title or "")
        assert "by priority" not in (panel.border_title or "")


async def test_s_to_due_shows_due_date_notification(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        messages = _capture_notifications(app)
        await pilot.press("s")  # priority
        await pilot.pause()
        await pilot.press("s")  # due
        await pilot.pause()

        assert any("due date" in m.lower() for m in messages)


async def test_due_sort_orders_earliest_first_done_demoted(mem_db):
    later = mem_db.add(Todo.new("later"))
    mem_db.set_due_date(later.id, _TOMORROW)
    sooner = mem_db.add(Todo.new("sooner"))
    mem_db.set_due_date(sooner.id, _TODAY)
    done = mem_db.add(Todo.new("done"))
    mem_db.set_due_date(done.id, _YESTERDAY)
    mem_db.set_completed(done.id, True)
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("s")  # priority
        await pilot.pause()
        await pilot.press("s")  # due
        await pilot.pause()

        ids = [i.todo_id for i in screen.query(TodoItem)]
        assert ids == [sooner.id, later.id, done.id]  # active earliest-first, done last


async def test_setting_due_in_due_sort_reranks_and_cursor_follows(mem_db):
    """In DUE sort, giving a task a later date re-ranks it; the cursor follows."""
    a = mem_db.add(Todo.new("a"))
    mem_db.set_due_date(a.id, _TOMORROW)
    b = mem_db.add(Todo.new("b"))
    mem_db.set_due_date(b.id, _TODAY)
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)
        todo_list.focus()
        # keep_id follows the load cursor (a) through both sorts.
        await pilot.press("s")  # priority
        await pilot.pause()
        await pilot.press("s")  # due — order [b (today), a (tomorrow)], cursor still on a
        await pilot.pause()
        # Move the cursor onto b (index 0 in DUE order).
        await pilot.press("k")
        await pilot.pause()
        assert todo_list.current_todo_id == b.id

        # Give b a far-future date so it sinks below a; cursor must follow b.
        await pilot.press("D")
        await pilot.pause()
        screen.query_one("#bar-input", Input).value = "+30"
        await pilot.press("enter")
        await pilot.pause()

        assert [i.todo_id for i in screen.query(TodoItem)] == [a.id, b.id]
        assert todo_list.current_todo_id == b.id  # cursor followed the task


async def test_setting_due_in_created_sort_stays_in_place(mem_db):
    """In creation order, setting a due date is a cheap in-place re-render (no move)."""
    a = mem_db.add(Todo.new("a"))
    mem_db.add(Todo.new("b"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)
        todo_list.focus()
        # cursor on a (index 0)
        await pilot.press("D")
        await pilot.pause()
        screen.query_one("#bar-input", Input).value = "today"
        await pilot.press("enter")
        await pilot.pause()

        # a keeps its creation-order slot; cursor stays on a.
        items = list(screen.query(TodoItem))
        assert items[0].todo_id == a.id
        assert todo_list.current_todo_id == a.id


async def test_toggle_in_due_sort_demotes_done_cursor_holds_index(mem_db):
    """Completing in DUE sort demotes the task; cursor holds its index (next slides in)."""
    a = mem_db.add(Todo.new("a"))
    mem_db.set_due_date(a.id, _TODAY)
    b = mem_db.add(Todo.new("b"))
    mem_db.set_due_date(b.id, _TOMORROW)
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        todo_list = screen.query_one(TodoList)
        todo_list.focus()
        await pilot.press("s")  # priority
        await pilot.pause()
        await pilot.press("s")  # due — cursor on a (index 0)
        await pilot.pause()
        assert todo_list.current_todo_id == a.id

        await pilot.press("space")  # complete a → sinks to done band
        await pilot.pause()

        # Cursor holds index 0 — b slides in.
        assert todo_list.current_todo_id == b.id


# --------------------------------------------------------------------------- #
# Due date — footer hints (Feature #7)
# --------------------------------------------------------------------------- #


async def test_footer_shows_due_hint_while_list_focused(mem_db):
    mem_db.add(Todo.new("task"))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.query_one(TodoList).focus()
        await pilot.pause()

        hints = dict(_shown_hints(app.screen))
        assert hints.get("D") == "Due"


async def test_footer_due_mode_shows_set_due_with_text(mem_db):
    saved = mem_db.add(Todo.new("task"))
    mem_db.set_due_date(saved.id, date(2026, 7, 10))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.query_one(TodoList).focus()
        await pilot.press("D")
        await pilot.pause()

        hints = dict(_shown_hints(app.screen))
        assert hints.get("enter") == "Set due"
        assert hints.get("escape") == "Cancel"


async def test_footer_due_mode_swaps_to_clear_due_when_empty(mem_db):
    saved = mem_db.add(Todo.new("task"))
    mem_db.set_due_date(saved.id, date(2026, 7, 10))
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.query_one(TodoList).focus()
        await pilot.press("D")
        await pilot.pause()
        app.screen.query_one("#bar-input", Input).value = ""
        await pilot.pause()

        hints = dict(_shown_hints(app.screen))
        assert hints.get("enter") == "Clear due"


async def test_footer_due_mode_swaps_back_to_set_due_when_text_typed(mem_db):
    """The swap is bidirectional: an undated row opens empty (Clear due), and
    typing a date flips the Enter hint back to Set due on the Input.Changed."""
    mem_db.add(Todo.new("task"))  # undated → bar opens empty
    app = _TestApp(_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        app.screen.query_one(TodoList).focus()
        await pilot.press("D")
        await pilot.pause()
        assert dict(_shown_hints(app.screen)).get("enter") == "Clear due"

        app.screen.query_one("#bar-input", Input).value = "today"
        await pilot.pause()

        assert dict(_shown_hints(app.screen)).get("enter") == "Set due"


# --------------------------------------------------------------------------- #
# Due escalation resolves to the right colour token — load-bearing #meta CSS
# (Feature #7). Mirrors the priority done-dim computed-colour test above:
# class-presence (-overdue / -due-today) can't tell $error from $warning, so a
# regression that swapped or broke the `.-overdue > #meta` / `.-due-today >
# #meta` rules would leave every has_class assertion green. Only the resolved
# colour proves the escalation is actually tinted (feature-7.md §11,
# due-dates.md §CSS, LEARNINGS 2026-07-03). Real TasqueApp so tasque.tcss loads.
# --------------------------------------------------------------------------- #


async def test_overdue_and_due_today_resolve_to_distinct_escalation_colours(mem_db):
    overdue = mem_db.add(Todo.new("overdue"))
    mem_db.set_due_date(overdue.id, _YESTERDAY)
    today = mem_db.add(Todo.new("today"))
    mem_db.set_due_date(today.id, _TODAY)
    # Reference rows: high priority is $error, medium is $warning — the same two
    # tokens the due rules use, so we assert the mapping without hard-coding RGB.
    high = mem_db.add(Todo.new("high"))
    mem_db.set_priority(high.id, Priority.HIGH)
    medium = mem_db.add(Todo.new("medium"))
    mem_db.set_priority(medium.id, Priority.MEDIUM)

    app = TasqueApp(controller=_make_controller(mem_db))

    async with app.run_test() as pilot:
        await pilot.pause()
        items = {item.todo_id: item for item in app.screen.query(TodoItem)}
        overdue_colour = items[overdue.id].query_one("#meta").styles.color
        today_colour = items[today.id].query_one("#meta").styles.color
        error_colour = items[high.id].query_one("#priority", Static).styles.color
        warning_colour = items[medium.id].query_one("#priority", Static).styles.color

        # Overdue tints $error, due-today tints $warning — and the two escalation
        # states are visibly distinct from each other.
        assert overdue_colour == error_colour
        assert today_colour == warning_colour
        assert overdue_colour != today_colour
