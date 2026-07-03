"""Integration tests for MainScreen (Features #4, #6).

Tests push MainScreen into a minimal app backed by an in-memory Database and
assert on user-visible DOM state via Textual's `App.run_test()` harness.

Note: always query from `app.screen` (the active `MainScreen`), not from `app`
directly.  Textual's `App.query()` does not traverse into pushed screens.
"""

from __future__ import annotations

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
