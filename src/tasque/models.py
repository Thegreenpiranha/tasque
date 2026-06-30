"""Core domain dataclasses shared across layers.

Pure module: no database, no Textual, no I/O. Just the immutable shapes that
flow ``db -> controller -> widget`` and back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


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
    priority: int | None = None
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
