"""Behavioural tests for TodoList widget navigation (Feature #4).

All assertions are on observable DOM state — which item has ``-highlight``,
what ``current_todo_id`` returns, etc. — not on private ListView internals.
"""

from __future__ import annotations

from textual.app import App, ComposeResult

from tasque.models import Todo
from tasque.widgets.todo_item import TodoItem
from tasque.widgets.todo_list import TodoList

# --------------------------------------------------------------------------- #
# Test harness
# --------------------------------------------------------------------------- #


class _ListApp(App):
    """Minimal app with a single TodoList populated from a list of Todos."""

    def __init__(self, todos: list[Todo]) -> None:
        super().__init__()
        self._todos = todos

    def compose(self) -> ComposeResult:
        yield TodoList(id="list")

    async def on_mount(self) -> None:
        await self.query_one(TodoList).set_todos(self._todos)


def _make_todos(n: int) -> list[Todo]:
    """Return n todos with sequential ids."""
    return [Todo(text=f"task {i}", id=i, completed=False) for i in range(1, n + 1)]


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


async def test_n_todos_renders_n_items():
    todos = _make_todos(3)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        items = app.query(TodoItem)

        assert len(items) == 3


async def test_items_render_in_insertion_order():
    todos = _make_todos(3)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        items = list(app.query(TodoItem))

        assert [item.todo_id for item in items] == [1, 2, 3]


async def test_empty_list_renders_no_items():
    app = _ListApp([])

    async with app.run_test() as pilot:
        await pilot.pause()
        items = app.query(TodoItem)

        assert len(items) == 0


# --------------------------------------------------------------------------- #
# Initial highlight
# --------------------------------------------------------------------------- #


async def test_first_item_is_highlighted_on_load():
    todos = _make_todos(3)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        items = list(app.query(TodoItem))

        assert items[0].has_class("-highlight")
        assert not items[1].has_class("-highlight")
        assert not items[2].has_class("-highlight")


async def test_current_todo_id_is_first_after_load():
    todos = _make_todos(3)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)

        assert todo_list.current_todo_id == todos[0].id


# --------------------------------------------------------------------------- #
# j / k navigation
# --------------------------------------------------------------------------- #


async def test_j_moves_highlight_down():
    todos = _make_todos(3)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.focus()
        await pilot.press("j")
        await pilot.pause()

        assert todo_list.current_todo_id == todos[1].id


async def test_k_moves_highlight_up():
    todos = _make_todos(3)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.focus()
        await pilot.press("j")
        await pilot.press("j")
        await pilot.pause()
        await pilot.press("k")
        await pilot.pause()

        assert todo_list.current_todo_id == todos[1].id


async def test_j_does_not_go_past_last_item():
    todos = _make_todos(2)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.focus()
        await pilot.press("j")
        await pilot.press("j")  # already at last; should stay
        await pilot.pause()

        assert todo_list.current_todo_id == todos[-1].id


async def test_k_does_not_go_past_first_item():
    todos = _make_todos(2)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.focus()
        await pilot.press("k")  # already at first; should stay
        await pilot.pause()

        assert todo_list.current_todo_id == todos[0].id


# --------------------------------------------------------------------------- #
# g / G jump to top / bottom
# --------------------------------------------------------------------------- #


async def test_G_jumps_to_last_item():
    todos = _make_todos(5)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.focus()
        await pilot.press("G")
        await pilot.pause()

        assert todo_list.current_todo_id == todos[-1].id


async def test_g_jumps_to_first_item_from_bottom():
    todos = _make_todos(5)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.focus()
        await pilot.press("G")
        await pilot.press("g")
        await pilot.pause()

        assert todo_list.current_todo_id == todos[0].id


# --------------------------------------------------------------------------- #
# Ctrl+d / Ctrl+u page navigation
# --------------------------------------------------------------------------- #


async def test_ctrl_d_moves_cursor_forward():
    todos = _make_todos(20)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.focus()
        first_id = todo_list.current_todo_id
        await pilot.press("ctrl+d")
        await pilot.pause()

        # Page down must move the cursor past the first item.
        assert todo_list.current_todo_id > first_id


async def test_ctrl_u_moves_cursor_backward():
    todos = _make_todos(20)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.focus()
        await pilot.press("G")
        await pilot.pause()
        bottom_id = todo_list.current_todo_id
        await pilot.press("ctrl+u")
        await pilot.pause()

        assert todo_list.current_todo_id < bottom_id


async def test_ctrl_d_does_not_go_past_last_item():
    todos = _make_todos(3)
    app = _ListApp(todos)

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.focus()
        await pilot.press("ctrl+d")
        await pilot.press("ctrl+d")  # Already near end
        await pilot.pause()

        assert todo_list.current_todo_id == todos[-1].id


async def test_ctrl_d_on_empty_list_is_a_noop():
    """Page-down on an empty list must not crash (main-screen.md edge cases)."""
    app = _ListApp([])

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.focus()
        await pilot.press("ctrl+d")
        await pilot.pause()

        assert todo_list.current_todo_id is None


async def test_ctrl_u_on_empty_list_is_a_noop():
    """Page-up on an empty list must not crash (main-screen.md edge cases)."""
    app = _ListApp([])

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)
        todo_list.focus()
        await pilot.press("ctrl+u")
        await pilot.pause()

        assert todo_list.current_todo_id is None


# --------------------------------------------------------------------------- #
# current_todo_id returns None on empty list
# --------------------------------------------------------------------------- #


async def test_current_todo_id_is_none_on_empty_list():
    app = _ListApp([])

    async with app.run_test() as pilot:
        await pilot.pause()
        todo_list = app.query_one(TodoList)

        assert todo_list.current_todo_id is None


# --------------------------------------------------------------------------- #
# Intent message seams (Feature #5 / #6) — verify they are correctly defined
# --------------------------------------------------------------------------- #


def test_toggle_requested_message_carries_todo_id():
    msg = TodoList.ToggleRequested(todo_id=1)
    assert msg.todo_id == 1


def test_edit_requested_message_carries_todo_id():
    msg = TodoList.EditRequested(todo_id=2)
    assert msg.todo_id == 2


def test_delete_requested_message_carries_todo_id():
    msg = TodoList.DeleteRequested(todo_id=3)
    assert msg.todo_id == 3


def test_priority_cycle_requested_message_carries_todo_id():
    msg = TodoList.PriorityCycleRequested(todo_id=4)
    assert msg.todo_id == 4
