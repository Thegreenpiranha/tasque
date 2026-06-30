"""The persistence layer — the *only* module that touches SQLite.

Owns the schema, the migration ladder, and CRUD for todos. Every other module
goes through :class:`Database`; no SQL or ``sqlite3`` import lives anywhere else.

Design notes (see the Feature #3 architecture proposal):

* A :class:`Database` instance wraps one long-lived connection. The controller
  holds one; tests construct ``Database(":memory:")``. A class (not module-level
  functions) is what keeps an in-memory DB alive and lets tests inject a path.
* Schema versioning uses SQLite's ``PRAGMA user_version`` as an applied-count.
  Each later feature *appends* a migration and never edits a shipped one.
* The v1 schema is deliberately minimal (``id``/``text``/``completed``/
  ``created_at``). ``priority``/``due_date``/``category_id``/``list_id`` arrive
  via their own additive migrations in later features; :func:`_row_to_todo`
  fills them with ``None`` until then.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import replace
from datetime import date, datetime
from os import PathLike

from tasque.models import Todo

logger = logging.getLogger("tasque.db")


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class TasqueError(Exception):
    """Base class for all Tasque domain errors."""


class TodoNotFoundError(TasqueError):
    """Raised when an operation targets a todo id that does not exist."""

    def __init__(self, todo_id: int) -> None:
        super().__init__(f"No todo with id {todo_id!r}")
        self.todo_id = todo_id


class MigrationError(TasqueError):
    """Raised when a schema migration step fails."""


class PersistenceError(TasqueError):
    """Wraps an unexpected ``sqlite3`` error so raw DB errors never escape."""


# --------------------------------------------------------------------------- #
# Migrations — append-only. Index in this list == the user_version it produces.
# --------------------------------------------------------------------------- #
def _migration_0001_create_todos(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE todos (
            id          INTEGER PRIMARY KEY,
            text        TEXT    NOT NULL,
            completed   INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL
        )
        """
    )


_MIGRATIONS = [
    _migration_0001_create_todos,
]


# --------------------------------------------------------------------------- #
# Row <-> dataclass mapping (single place that evolves as columns are added)
# --------------------------------------------------------------------------- #
def _row_to_todo(row: sqlite3.Row) -> Todo:
    keys = row.keys()

    def col(name: str):
        return row[name] if name in keys else None

    due_raw = col("due_date")
    return Todo(
        id=row["id"],
        text=row["text"],
        completed=bool(row["completed"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        priority=col("priority"),
        due_date=date.fromisoformat(due_raw) if due_raw else None,
        category_id=col("category_id"),
        list_id=col("list_id"),
    )


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
class Database:
    """A connection to one Tasque SQLite database, migrated to the latest schema.

    The ``path`` may be a filesystem path or ``":memory:"``. Construction opens
    the connection, sets pragmas, and runs any pending migrations.
    """

    def __init__(self, path: str | PathLike[str]) -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    # -- lifecycle ---------------------------------------------------------- #
    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- schema ------------------------------------------------------------- #
    @property
    def schema_version(self) -> int:
        """The number of migrations applied (SQLite ``user_version``)."""
        return self._conn.execute("PRAGMA user_version").fetchone()[0]

    def _migrate(self) -> None:
        try:
            version = self._conn.execute("PRAGMA user_version").fetchone()[0]
            for i, step in enumerate(_MIGRATIONS[version:], start=version):
                logger.debug("applying migration %d: %s", i + 1, step.__name__)
                step(self._conn)
                # user_version can't be parameterized; i + 1 is a trusted int.
                self._conn.execute(f"PRAGMA user_version = {i + 1}")
            self._conn.commit()
        except sqlite3.Error as exc:
            raise MigrationError(f"Migration failed: {exc}") from exc

    # -- CRUD --------------------------------------------------------------- #
    def add(self, todo: Todo) -> Todo:
        """Persist a new (unsaved) todo and return it with its assigned ``id``."""
        try:
            cur = self._conn.execute(
                "INSERT INTO todos (text, completed, created_at) VALUES (?, ?, ?)",
                (todo.text, int(todo.completed), todo.created_at.isoformat()),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise PersistenceError(f"Failed to add todo: {exc}") from exc
        return replace(todo, id=cur.lastrowid)

    def get(self, todo_id: int) -> Todo:
        """Return the todo with ``todo_id`` or raise :class:`TodoNotFoundError`."""
        row = self._conn.execute(
            "SELECT * FROM todos WHERE id = ?", (todo_id,)
        ).fetchone()
        if row is None:
            raise TodoNotFoundError(todo_id)
        return _row_to_todo(row)

    def list_todos(self) -> list[Todo]:
        """Return all todos, ordered by id (insertion order)."""
        rows = self._conn.execute("SELECT * FROM todos ORDER BY id").fetchall()
        return [_row_to_todo(row) for row in rows]

    def update(self, todo: Todo) -> Todo:
        """Persist changes to an existing todo's mutable fields and return it."""
        if todo.id is None:
            raise ValueError("Cannot update an unsaved todo (id is None)")
        cur = self._conn.execute(
            "UPDATE todos SET text = ?, completed = ? WHERE id = ?",
            (todo.text, int(todo.completed), todo.id),
        )
        if cur.rowcount == 0:
            raise TodoNotFoundError(todo.id)
        self._conn.commit()
        return self.get(todo.id)

    def delete(self, todo_id: int) -> Todo:
        """Delete a todo and return the deleted value (so callers can undo)."""
        todo = self.get(todo_id)  # raises TodoNotFoundError if missing
        self._conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        self._conn.commit()
        return todo

    def set_completed(self, todo_id: int, completed: bool) -> Todo:
        """Set a todo's completed flag and return the updated todo."""
        cur = self._conn.execute(
            "UPDATE todos SET completed = ? WHERE id = ?",
            (int(completed), todo_id),
        )
        if cur.rowcount == 0:
            raise TodoNotFoundError(todo_id)
        self._conn.commit()
        return self.get(todo_id)
