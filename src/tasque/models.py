"""Core domain dataclasses shared across layers.

Pure module: no database, no Textual, no I/O. Just the immutable shapes that
flow ``db -> controller -> widget`` and back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum, IntEnum


class Priority(IntEnum):
    """Task priority levels.

    Stored as an integer in SQLite (IntEnum is an int subclass — no adapter
    needed in Python 3.12). Ascending encoding means ``ORDER BY priority DESC``
    yields HIGH → MEDIUM → LOW with ``NULLS LAST`` pushing none-priority items
    to the bottom. "No priority" is ``None`` (SQL NULL), not a zero member.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class TodoSort(Enum):
    """Available sort modes for the todo list (view state, Features #6 / #7).

    ``CREATED`` preserves insertion order (``ORDER BY id``); ``PRIORITY`` ranks
    by urgency with done items demoted (``ORDER BY completed ASC, priority DESC
    NULLS LAST, id ASC``); ``DUE`` ranks by earliest due date with done items
    demoted (``ORDER BY completed ASC, due_date ASC NULLS LAST, id ASC``). Lives
    in models (not db) for symmetry with Priority and so the controller can
    re-export it without a db-layer import.
    """

    CREATED = "created"
    PRIORITY = "priority"
    DUE = "due"


class DueState(Enum):
    """Classification of a todo's due date relative to the current civil day.

    Pure/clock-free values produced by :func:`due_state`; the widget maps them to
    the reserved ``#due`` slot content and the ``-overdue`` / ``-due-today`` CSS
    classes (Feature #7). Completion is *not* encoded here — the widget gates the
    escalation off on done rows.
    """

    NONE = "none"
    OVERDUE = "overdue"
    TODAY = "today"
    FUTURE = "future"


class DueDateParseError(ValueError):
    """Raised when a user-entered due-date string can't be parsed.

    Input validation, *not* persistence — a plain ``ValueError`` subclass, never
    a :class:`~tasque.db.TasqueError`, so it stays on the local
    pulse-the-bar-``-invalid`` path and never reaches the error-toast path.
    """


_CYCLE: tuple[Priority | None, ...] = (None, Priority.LOW, Priority.MEDIUM, Priority.HIGH)


def next_priority(current: Priority | None) -> Priority | None:
    """Return the next priority in the cycle: none→low→medium→high→none.

    Pure function — no DB, no Textual. Single source of truth for the cycle
    order so the controller command and tests can't drift.
    """
    return _CYCLE[(_CYCLE.index(current) + 1) % len(_CYCLE)]


def due_state(due: date | None, today: date) -> DueState:
    """Classify a due date relative to ``today`` (the local civil date).

    Pure and clock-free: ``today`` is injected, so overdue detection is testable
    with a fixed 'now'. Completion is NOT considered here — the widget gates the
    escalation off on done rows (overdue never shows on a completed task).
    """
    if due is None:
        return DueState.NONE
    if due < today:
        return DueState.OVERDUE
    if due == today:
        return DueState.TODAY
    return DueState.FUTURE


def parse_due_date(text: str, *, today: date) -> date:
    """Parse a due-date string into a ``date``. Raises on junk.

    Accepts (case-insensitive, trimmed): ISO ``YYYY-MM-DD``, ``today``,
    ``tomorrow``, and relative ``+N`` (N calendar days from today). Empty/blank
    is NOT handled here — the caller treats a blank field as 'clear' (set None).
    ``today`` is injected so the relative forms are testable with a fixed now.
    """
    s = text.strip().lower()
    if s == "today":
        return today
    if s == "tomorrow":
        return today + timedelta(days=1)
    if s.startswith("+") and s[1:].isdigit():
        return today + timedelta(days=int(s[1:]))
    try:
        return date.fromisoformat(text.strip())
    except ValueError as exc:
        raise DueDateParseError(f"Not a date: {text!r}") from exc


@dataclass(frozen=True, slots=True)
class Todo:
    """A single to-do item.

    ``id`` is ``None`` until the item has been persisted. ``created_at`` is set
    when the item is first created (see :meth:`Todo.new`). The trailing fields
    are placeholders the schema grows into in later features — ``priority`` (#6),
    ``due_date`` (#7), ``category_id`` (#8), ``list_id`` (#10) — and stay ``None``
    until those land.
    """

    text: str
    id: int | None = None
    completed: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    priority: Priority | None = None
    due_date: date | None = None
    category_id: int | None = None
    list_id: int | None = None

    @classmethod
    def new(cls, text: str, *, created_at: datetime | None = None) -> Todo:
        """Create a new, unsaved todo (``id is None``).

        ``created_at`` may be supplied for deterministic tests; otherwise it
        defaults to the current time.
        """
        return cls(text=text, created_at=created_at or datetime.now())
