"""A single-row widget representing one todo inside the TodoList."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import ListItem, Static

from tasque.models import Todo

# Priority-code → spoken word, for the accessible label (values land with #6).
_PRIORITY_WORDS = {3: "high priority", 2: "medium priority", 1: "low priority"}

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
        except NoMatches:
            # The watcher can fire before compose() has created #gutter; the
            # on_mount → watch_todo path renders the correct gutter shortly after.
            self.log("watch_highlighted fired before #gutter existed; skipping")

    # -- helpers ------------------------------------------------------------ #

    def _sync_classes(self, todo: Todo) -> None:
        self.set_class(todo.completed, "-done")
        # Seam classes for Feature #6 / #7 (defined, never set in #4):
        self.remove_class("-priority-high", "-priority-medium", "-priority-low")
        self.remove_class("-overdue", "-due-today")

    # -- accessibility ------------------------------------------------------ #

    @property
    def accessible_label(self) -> str:
        """A single readable string folding the row's state, for a screen reader.

        e.g. ``"incomplete, high priority, Finish the quarterly report"``. Priority
        joins in with Feature #6 and due date with #7; today (both ``None``) the
        label is just completion + text. Computed live from the current ``todo``
        so it never goes stale after a toggle or edit.
        """
        todo = self.todo if self.todo is not None else self._initial_todo
        return self._compose_accessible_label(todo)

    @staticmethod
    def _compose_accessible_label(todo: Todo) -> str:
        parts = ["completed" if todo.completed else "incomplete"]
        priority_word = _PRIORITY_WORDS.get(todo.priority)  # type: ignore[arg-type]
        if priority_word is not None:
            parts.append(priority_word)
        parts.append(todo.text)
        return ", ".join(parts)

    # -- public API --------------------------------------------------------- #

    @property
    def todo_id(self) -> int | None:
        """The persisted id of the wrapped todo."""
        if self.todo is not None:
            return self.todo.id
        return self._initial_todo.id
