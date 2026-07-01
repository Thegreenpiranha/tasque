"""Application controller — the layer between the UI and the persistence layer.

Widgets never import ``db.py`` directly; they call methods here. The controller
reads from :class:`~tasque.db.Database`, hands frozen dataclasses to widgets,
and catches :exc:`~tasque.db.TasqueError` subclasses before they reach the UI.

Mutation methods are **seams** for Feature #5 and beyond — their signatures are
locked now so the widget layer can code against them, but they raise
:exc:`NotImplementedError` until the respective feature lands.

The ``Command`` protocol and ``_apply`` choke-point are seams for Feature #9
(undo/redo): every future mutation will route through ``_apply`` so the undo
stack can intercept it without touching widget code.
"""

from __future__ import annotations

import logging
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

    Every mutation will implement this in Feature #9 so the undo stack in
    :meth:`TodoController._apply` can record and replay them.
    """

    def execute(self) -> None:
        """Perform the mutation."""
        ...

    def undo(self) -> None:
        """Reverse the mutation."""
        ...


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

    # -- mutation seams (Feature #5) ---------------------------------------- #

    def add_todo(self, text: str) -> Todo:
        """Create and persist a new todo. *Implemented in Feature #5.*"""
        raise NotImplementedError("add_todo is a Feature #5 seam")

    def toggle_todo(self, todo_id: int) -> Todo:
        """Flip the completed flag on a todo. *Implemented in Feature #5.*"""
        raise NotImplementedError("toggle_todo is a Feature #5 seam")

    def edit_todo(self, todo_id: int, text: str) -> Todo:
        """Replace a todo's text. *Implemented in Feature #5.*"""
        raise NotImplementedError("edit_todo is a Feature #5 seam")

    def delete_todo(self, todo_id: int) -> Todo:
        """Delete a todo and return the deleted value. *Implemented in Feature #5.*"""
        raise NotImplementedError("delete_todo is a Feature #5 seam")

    # -- mutation seam (Feature #6) ----------------------------------------- #

    def cycle_priority(self, todo_id: int) -> Todo:
        """Cycle priority none→low→medium→high→none. *Implemented in Feature #6.*"""
        raise NotImplementedError("cycle_priority is a Feature #6 seam")

    # -- undo/redo choke-point (Feature #9) ---------------------------------- #

    def _apply(self, command: Command) -> None:
        """Route a command through the undo stack. *Implemented in Feature #9.*"""
        raise NotImplementedError("_apply is a Feature #9 seam")
