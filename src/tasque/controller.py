"""Application controller — the layer between the UI and the persistence layer.

Widgets never import ``db.py`` directly; they call methods here. The controller
reads from :class:`~tasque.db.Database`, hands frozen dataclasses to widgets,
and catches :exc:`~tasque.db.TasqueError` subclasses before they reach the UI.

The core mutations (add / toggle / edit / delete) are implemented as of Feature
#5; each builds a private ``_*Command`` and routes it through :meth:`_apply`.
``cycle_priority`` remains a locked seam until Feature #6.

The ``Command`` protocol and ``_apply`` choke-point are the seam for Feature #9
(undo/redo): every mutation already routes through ``_apply`` and carries its
result on ``command.result``, so the undo stack can intercept it without
touching widget code or changing a single call site.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Protocol, runtime_checkable

from tasque.db import Database
from tasque.models import Todo

logger = logging.getLogger("tasque.controller")


# --------------------------------------------------------------------------- #
# Undo/redo seam (Feature #9)
# --------------------------------------------------------------------------- #
@runtime_checkable
class Command(Protocol):
    """Protocol for undoable commands.

    Every mutation implements this so the undo stack in
    :meth:`TodoController._apply` can record and replay them (Feature #9).
    A command also carries a ``result`` attribute holding the ``Todo`` its
    :meth:`execute` produced, which the public controller methods return —
    this is what keeps ``_apply`` free to stay ``-> None`` (see the four
    ``_*Command`` classes below and ``docs/architecture/feature-5.md`` §4).
    """

    result: Todo | None

    def execute(self) -> None:
        """Perform the mutation, storing its outcome on ``self.result``."""
        ...

    def undo(self) -> None:
        """Reverse the mutation."""
        ...


# --------------------------------------------------------------------------- #
# Mutation commands (Feature #5)
# --------------------------------------------------------------------------- #
# Private, controller-internal command objects. They call ``db.py``'s public
# methods (only *SQL* is forbidden outside ``db.py``, not calling into it). Each
# stores its produced ``Todo`` on ``self.result`` so the controller can return
# it without changing ``_apply``'s ``-> None`` signature. The ``undo`` bodies
# are directionally complete for Feature #9 but never invoked at #5.


class _AddCommand:
    def __init__(self, db: Database, text: str) -> None:
        self._db = db
        self._text = text
        self.result: Todo | None = None

    def execute(self) -> None:
        self.result = self._db.add(Todo.new(self._text))

    def undo(self) -> None:  # pragma: no cover - Feature #9 seam (no public undo yet)
        assert self.result is not None and self.result.id is not None
        self._db.delete(self.result.id)


class _ToggleCommand:
    def __init__(self, db: Database, todo_id: int) -> None:
        self._db = db
        self._todo_id = todo_id
        self._prev_completed: bool | None = None
        self.result: Todo | None = None

    def execute(self) -> None:
        current = self._db.get(self._todo_id)
        self._prev_completed = current.completed
        self.result = self._db.set_completed(self._todo_id, not current.completed)

    def undo(self) -> None:  # pragma: no cover - Feature #9 seam (no public undo yet)
        assert self._prev_completed is not None
        self._db.set_completed(self._todo_id, self._prev_completed)


class _EditCommand:
    def __init__(self, db: Database, todo_id: int, text: str) -> None:
        self._db = db
        self._todo_id = todo_id
        self._text = text
        self._prev_text: str | None = None
        self.result: Todo | None = None

    def execute(self) -> None:
        current = self._db.get(self._todo_id)
        self._prev_text = current.text
        self.result = self._db.update(replace(current, text=self._text))

    def undo(self) -> None:  # pragma: no cover - Feature #9 seam (no public undo yet)
        assert self._prev_text is not None
        current = self._db.get(self._todo_id)
        self._db.update(replace(current, text=self._prev_text))


class _DeleteCommand:
    def __init__(self, db: Database, todo_id: int) -> None:
        self._db = db
        self._todo_id = todo_id
        self.result: Todo | None = None

    def execute(self) -> None:
        # db.delete returns the deleted Todo (raises TodoNotFoundError if gone),
        # preserving the data Feature #9's undo will re-insert.
        self.result = self._db.delete(self._todo_id)

    def undo(self) -> None:  # pragma: no cover - Feature #9 seam (no public undo yet)
        assert self.result is not None
        # NOTE (Feature #9): db.add assigns a *new* id; restoring the original
        # id is a #9 concern (a resurrection/insert-with-id path). Flagged here.
        self._db.add(self.result)


# --------------------------------------------------------------------------- #
# Controller
# --------------------------------------------------------------------------- #
class TodoController:
    """Mediates between the Textual UI and the SQLite persistence layer.

    The controller is the single place where domain errors are caught and where
    (in Feature #9) undoable commands will be pushed onto a stack.

    Args:
        db: An open :class:`~tasque.db.Database` instance.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    # -- read ---------------------------------------------------------------- #

    def list_todos(self) -> list[Todo]:
        """Return all todos ordered by id (insertion / creation order)."""
        return self._db.list_todos()

    def get_todo(self, todo_id: int) -> Todo:
        """Return the todo with ``todo_id`` or raise :class:`TodoNotFoundError`.

        The layer-honest source for the UI's read needs (edit pre-fill text,
        delete-dialog quoted title) — widgets never touch ``db.py`` directly.
        """
        return self._db.get(todo_id)

    # -- mutations (Feature #5) --------------------------------------------- #

    def add_todo(self, text: str) -> Todo:
        """Create and persist a new todo, returning it with its assigned id."""
        command = _AddCommand(self._db, text)
        self._apply(command)
        assert command.result is not None
        return command.result

    def toggle_todo(self, todo_id: int) -> Todo:
        """Flip the completed flag on a todo and return the updated value."""
        command = _ToggleCommand(self._db, todo_id)
        self._apply(command)
        assert command.result is not None
        return command.result

    def edit_todo(self, todo_id: int, text: str) -> Todo:
        """Replace a todo's text and return the updated value."""
        command = _EditCommand(self._db, todo_id, text)
        self._apply(command)
        assert command.result is not None
        return command.result

    def delete_todo(self, todo_id: int) -> Todo:
        """Delete a todo and return the deleted value (the undo seam)."""
        command = _DeleteCommand(self._db, todo_id)
        self._apply(command)
        assert command.result is not None
        return command.result

    # -- mutation seam (Feature #6) ----------------------------------------- #

    def cycle_priority(self, todo_id: int) -> Todo:
        """Cycle priority none→low→medium→high→none. *Implemented in Feature #6.*"""
        raise NotImplementedError("cycle_priority is a Feature #6 seam")

    # -- undo/redo choke-point (Feature #9) ---------------------------------- #

    def _apply(self, command: Command) -> None:
        """Route every mutation through one choke-point.

        Feature #9 grows this into the undo stack (append ``command``, clear the
        redo stack) — the mutation methods above already build a ``Command`` and
        read ``command.result``, so no call site changes when #9 lands.
        """
        command.execute()
