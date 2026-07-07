"""A single-row widget representing one todo inside the TodoList."""

from __future__ import annotations

import logging
from datetime import date

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import ListItem, Static

from tasque.models import DueState, Priority, Todo, due_state

# Maps used for rendering the #priority slot and setting the accessible label.
_PRIORITY_TAGS: dict[Priority, str] = {
    Priority.HIGH: "(H) ",
    Priority.MEDIUM: "(M) ",
    Priority.LOW: "(L) ",
}
_PRIORITY_CLASS: dict[Priority, str] = {
    Priority.HIGH: "-priority-high",
    Priority.MEDIUM: "-priority-medium",
    Priority.LOW: "-priority-low",
}
# Priority-code → spoken word, for the accessible label.
_PRIORITY_WORDS: dict[Priority, str] = {
    Priority.HIGH: "high priority",
    Priority.MEDIUM: "medium priority",
    Priority.LOW: "low priority",
}

logger = logging.getLogger("tasque.widgets.todo_item")


def _priority_tag(priority: Priority | None) -> str:
    """Return the exact 4-character slot content for a priority level."""
    return _PRIORITY_TAGS.get(priority, "    ")  # type: ignore[arg-type]


def _fmt_due(due: date, today: date) -> str:
    """Format a due date for the slot: MM-DD in the current year, else full ISO.

    The year rule (due-dates.md Q4): the common case stays compact (``06-30``)
    while a date in another year is unambiguous (``2027-01-15``).
    """
    return due.strftime("%m-%d") if due.year == today.year else due.isoformat()


def _due_display(due: date | None, state: DueState, completed: bool, today: date) -> str:
    """The string for the reserved ``#due`` slot (due-dates.md Q4).

    Blank for none; ``──`` for a completed row (escalation is moot); ``OVERDUE
    <date>`` / ``due today`` for active escalated rows; a bare date for future.
    """
    if due is None:
        return ""  # blank slot — no due date
    if completed:
        return "──"  # done rows show no stale escalation
    if state is DueState.OVERDUE:
        return f"OVERDUE {_fmt_due(due, today)}"
    if state is DueState.TODAY:
        return "due today"
    return _fmt_due(due, today)  # future


def _due_word(due: date | None, state: DueState, completed: bool) -> str | None:
    """The spoken due phrase for the accessible label, or ``None`` to omit it.

    Future uses the full ISO date (``due 2026-06-30``) for unambiguous read-aloud
    (due-dates.md Q4/§Accessibility); none and completed contribute nothing.
    """
    if due is None or completed:
        return None
    if state is DueState.OVERDUE:
        return "overdue"
    if state is DueState.TODAY:
        return "due today"
    return f"due {due.isoformat()}"


class TodoItem(ListItem):
    """One task row inside :class:`~tasque.widgets.todo_list.TodoList`.

    Layout (horizontal, one line)::

        ▸ [x] (H) <title text…>          #category        <due>
        └┬┘ └┬┘ └┬┘                               └──── #meta ──┘
        gutter checkbox priority  title (1fr)

    Slots ``#priority`` (#6) and ``#due`` (#7) are active; ``#category`` stays
    reserved and empty until Feature #8 activates it.

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
        # markup=False prevents Rich from interpreting "[ ]" / "[x]" / "▸" / "(H)"
        # as Console Markup tags, which would strip them silently (LEARNINGS 2026-07-01).
        yield Static("  ", id="gutter", markup=False)
        yield Static(checkbox_text, id="checkbox", markup=False)
        yield Static(_priority_tag(t.priority), id="priority", markup=False)
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
        today = date.today()
        state = due_state(new_todo.due_date, today)
        self.query_one("#checkbox", Static).update("[x]" if new_todo.completed else "[ ]")
        self.query_one("#priority", Static).update(_priority_tag(new_todo.priority))
        self.query_one("#title", Static).update(new_todo.text)
        self.query_one("#due", Static).update(
            _due_display(new_todo.due_date, state, new_todo.completed, today)
        )
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
        # Remove all priority classes then re-apply the one that matches.
        self.remove_class("-priority-high", "-priority-medium", "-priority-low")
        cls = _PRIORITY_CLASS.get(todo.priority)  # type: ignore[arg-type]
        if cls:
            self.add_class(cls)
        # Due-date escalation, gated on completion: a done row never carries
        # -overdue / -due-today, so those classes can never co-occur with -done
        # and there is no CSS source-order tie to break (feature-7.md §3 / §8,
        # contrast the priority done-dim, LEARNINGS 2026-07-03).
        state = due_state(todo.due_date, date.today())
        self.set_class(not todo.completed and state is DueState.OVERDUE, "-overdue")
        self.set_class(not todo.completed and state is DueState.TODAY, "-due-today")

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
        # Due folds in AFTER the text — order is completion, priority, text, due
        # (main-screen.md § Screen reader / due-dates.md Q5).
        due_word = _due_word(todo.due_date, due_state(todo.due_date, date.today()), todo.completed)
        if due_word is not None:
            parts.append(due_word)
        return ", ".join(parts)

    # -- public API --------------------------------------------------------- #

    @property
    def todo_id(self) -> int | None:
        """The persisted id of the wrapped todo."""
        if self.todo is not None:
            return self.todo.id
        return self._initial_todo.id
