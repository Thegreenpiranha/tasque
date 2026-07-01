"""A single-row widget representing one todo inside the TodoList."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import ListItem, Static

from tasque.models import Todo

logger = logging.getLogger("tasque.widgets.todo_item")


class TodoItem(ListItem):
    """One task row inside :class:`~tasque.widgets.todo_list.TodoList`.

    Layout (horizontal, one line)::

        ▸ [x] (H) <title text…>          #category        <due>
        └┬┘ └┬┘ └┬┘                               └──── #meta ──┘
        gutter checkbox priority  title (1fr)

    Slots ``#priority``, ``#due``, and ``#category`` are reserved and empty
    until Feature #6 / #7 / #8 activate them.

    CSS classes toggled from reactive state:
    - ``-done`` — todo is completed (checkbox ``[x]``, title dimmed+strike)
    - ``-highlight`` — inherited from ``ListItem``; the cursor row
    - ``-priority-high``, ``-priority-medium``, ``-priority-low`` — Feature #6
    - ``-overdue``, ``-due-today`` — Feature #7
    """

    # The current todo dataclass. Set to None until on_mount fires so the watcher
    # does not run before compose() has created children (init=False).
    todo: reactive[Todo | None] = reactive(None, init=False)

    def __init__(self, todo: Todo) -> None:
        super().__init__(id=f"todo-{todo.id}")
        self._initial_todo = todo

    # -- compose ------------------------------------------------------------ #

    def compose(self) -> ComposeResult:
        t = self._initial_todo
        checkbox_text = "[x]" if t.completed else "[ ]"
        # markup=False prevents Rich from interpreting "[ ]" / "[x]" / "▸" as
        # Console Markup tags, which would strip them silently.
        yield Static("  ", id="gutter", markup=False)
        yield Static(checkbox_text, id="checkbox", markup=False)
        yield Static("    ", id="priority", markup=False)
        yield Static(t.text, id="title", markup=False)
        with Horizontal(id="meta"):
            yield Static("", id="due", markup=False)
            yield Static("", id="category", markup=False)

    # -- lifecycle ---------------------------------------------------------- #

    def on_mount(self) -> None:
        # Set the reactive after children exist so watch_todo can query them.
        self.todo = self._initial_todo
        self._sync_classes(self._initial_todo)

    # -- reactive watchers -------------------------------------------------- #

    def watch_todo(self, new_todo: Todo | None) -> None:
        if new_todo is None:
            return
        self.query_one("#checkbox", Static).update("[x]" if new_todo.completed else "[ ]")
        self.query_one("#title", Static).update(new_todo.text)
        self._sync_classes(new_todo)

    def watch_highlighted(self, value: bool) -> None:
        super().watch_highlighted(value)
        try:
            self.query_one("#gutter", Static).update("▸ " if value else "  ")
        except Exception:
            # Guard against the watcher firing before compose() has run.
            pass

    # -- helpers ------------------------------------------------------------ #

    def _sync_classes(self, todo: Todo) -> None:
        self.set_class(todo.completed, "-done")
        # Seam classes for Feature #6 / #7 (defined, never set in #4):
        self.remove_class("-priority-high", "-priority-medium", "-priority-low")
        self.remove_class("-overdue", "-due-today")

    # -- public API --------------------------------------------------------- #

    @property
    def todo_id(self) -> int | None:
        """The persisted id of the wrapped todo."""
        if self.todo is not None:
            return self.todo.id
        return self._initial_todo.id
