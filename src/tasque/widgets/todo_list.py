"""TodoList widget — a keyboard-navigable list of TodoItem rows."""

from __future__ import annotations

import logging

from textual.binding import Binding
from textual.message import Message
from textual.widgets import ListView

from tasque.models import Todo
from tasque.widgets.todo_item import TodoItem

logger = logging.getLogger("tasque.widgets.todo_list")


class TodoList(ListView):
    """A :class:`textual.widgets.ListView` subclass that renders :class:`TodoItem` rows.

    Navigation bindings add vim-style ``j``/``k``, top/bottom ``g``/``G``,
    and page jumps ``Ctrl+d``/``Ctrl+u``.

    Intent messages (seams for Features #5 and #6) are defined here so the
    screen can register handlers before those features land.  The bindings
    that *post* them (``Space``, ``e``, ``d``, ``p``) are **not** added until
    those features are implemented.
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "cursor_top", "Top", show=False),
        Binding("G", "cursor_bottom", "Bottom", show=False),
        Binding("home", "cursor_top", "Top", show=False),
        Binding("end", "cursor_bottom", "Bottom", show=False),
        Binding("ctrl+d", "cursor_page_down", "Page down", show=False),
        Binding("ctrl+u", "cursor_page_up", "Page up", show=False),
        Binding("pagedown", "cursor_page_down", "Page down", show=False),
        Binding("pageup", "cursor_page_up", "Page up", show=False),
    ]

    # -- Intent message seams (Features #5 / #6) ----------------------------- #

    class ToggleRequested(Message):
        """Posted when the user requests toggling the current todo. (Feature #5)"""

        def __init__(self, todo_id: int) -> None:
            super().__init__()
            self.todo_id = todo_id

    class EditRequested(Message):
        """Posted when the user requests editing the current todo. (Feature #5)"""

        def __init__(self, todo_id: int) -> None:
            super().__init__()
            self.todo_id = todo_id

    class DeleteRequested(Message):
        """Posted when the user requests deleting the current todo. (Feature #5)"""

        def __init__(self, todo_id: int) -> None:
            super().__init__()
            self.todo_id = todo_id

    class PriorityCycleRequested(Message):
        """Posted when the user requests cycling the current todo's priority. (Feature #6)"""

        def __init__(self, todo_id: int) -> None:
            super().__init__()
            self.todo_id = todo_id

    # -- public API --------------------------------------------------------- #

    async def set_todos(self, todos: list[Todo]) -> None:
        """Replace the list contents with the given todos, resetting the cursor.

        Awaits the removal of old items before mounting new ones so the DOM
        is always consistent. Sets ``index = 0`` after mounting so the first
        item is highlighted.
        """
        await self.clear()
        if todos:
            await self.mount(*[TodoItem(todo) for todo in todos])
            self.index = 0

    def update_todo(self, todo: Todo) -> None:
        """Update a single row in-place without rebuilding the full list.

        Finds the :class:`TodoItem` whose ``todo_id`` matches and sets its
        ``todo`` reactive, which triggers ``watch_todo`` to refresh the row.
        The cursor (``ListView.index``) is not changed.
        """
        for item in self.query(TodoItem):
            if item.todo_id == todo.id:
                item.todo = todo
                break

    @property
    def current_todo_id(self) -> int | None:
        """The id of the currently highlighted todo, or ``None``."""
        child = self.highlighted_child
        if isinstance(child, TodoItem):
            return child.todo_id
        return None

    # -- navigation actions ------------------------------------------------- #

    def action_cursor_top(self) -> None:
        """Move the cursor to the first item."""
        if self._nodes:
            self.index = 0

    def action_cursor_bottom(self) -> None:
        """Move the cursor to the last item."""
        if self._nodes:
            self.index = len(self._nodes) - 1

    def action_cursor_page_down(self) -> None:
        """Move the cursor down by approximately one page."""
        if not self._nodes:
            return
        if self.index is None:
            self.index = 0
            return
        page = max(1, self.size.height)
        self.index = min(self.index + page, len(self._nodes) - 1)

    def action_cursor_page_up(self) -> None:
        """Move the cursor up by approximately one page."""
        if not self._nodes:
            return
        if self.index is None:
            self.index = len(self._nodes) - 1
            return
        page = max(1, self.size.height)
        self.index = max(0, self.index - page)
