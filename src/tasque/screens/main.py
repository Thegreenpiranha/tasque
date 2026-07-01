"""The main Tasque screen — todo list, input bar, empty state, and key-hint footer."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, ListView

from tasque.controller import TodoController
from tasque.db import TasqueError
from tasque.screens.delete_confirm import DeleteConfirmScreen
from tasque.widgets.empty_state import EmptyState
from tasque.widgets.input_bar import InputBar
from tasque.widgets.todo_list import TodoList

logger = logging.getLogger("tasque.screens.main")

_ADD_CTA = "Press  a  to add your first task"


class MainScreen(Screen[None]):
    """The primary screen: a bordered list panel with Header, InputBar, and Footer.

    Layout::

        Header (1 row)
        ┌─ Inbox · N active · M done ──────────────────────┐
        │  TodoList (scrollable)                            │
        │  EmptyState (centered, hidden when populated)     │
        └───────────────────────────────────────────────────┘
        ┌─ New task / Edit task ───────────────────────────┐   ← InputBar (hidden when idle)
        └───────────────────────────────────────────────────┘
        Footer (1 row)

    The four core mutations (add / toggle / edit / delete) route through the
    controller; the screen never touches ``db.py``. Domain errors
    (:class:`~tasque.db.TasqueError`) are caught here and surfaced as toasts —
    this screen is the only layer holding an ``app`` handle (see
    ``docs/architecture/feature-5.md`` §5).
    """

    BINDINGS = [
        Binding("a", "add_todo", "Add", show=True),
        Binding("question_mark", "help", "Help", show=True),
    ]

    def __init__(self, controller: TodoController) -> None:
        super().__init__()
        self._controller = controller

    # -- compose ------------------------------------------------------------ #

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="list-panel"):
            yield TodoList(id="todo-list")
            yield EmptyState()
        yield InputBar()
        yield Footer()

    # -- lifecycle ---------------------------------------------------------- #

    async def on_mount(self) -> None:
        await self.refresh_todos()

    # -- data refresh ------------------------------------------------------- #

    async def refresh_todos(self) -> None:
        """Reload todos from the controller and update the UI."""
        todos = self._controller.list_todos()

        todo_list = self.query_one(TodoList)
        empty_state = self.query_one(EmptyState)

        await todo_list.set_todos(todos)
        self._update_counts(todos)

        has_todos = bool(todos)
        todo_list.set_class(not has_todos, "-hidden")
        empty_state.set_class(has_todos, "-hidden")

    def _update_counts(self, todos: list) -> None:
        """Refresh only the panel border-title counts (no list rebuild)."""
        active = sum(1 for t in todos if not t.completed)
        done = sum(1 for t in todos if t.completed)
        self.query_one(
            "#list-panel", Container
        ).border_title = f"Inbox · {active} active · {done} done"

    # -- event handlers: highlight ------------------------------------------ #

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Acknowledge highlight changes; future features may update a status bar."""
        event.stop()

    # -- event handlers: toggle --------------------------------------------- #

    def on_todo_list_toggle_requested(self, event: TodoList.ToggleRequested) -> None:
        event.stop()
        try:
            updated = self._controller.toggle_todo(event.todo_id)
        except TasqueError as exc:
            self.app.notify(f"Error: {exc}", severity="error")
            return
        self.query_one(TodoList).update_todo(updated)
        self._update_counts(self._controller.list_todos())

    # -- event handlers: add / edit (the InputBar) -------------------------- #

    def on_todo_list_edit_requested(self, event: TodoList.EditRequested) -> None:
        event.stop()
        try:
            todo = self._controller.get_todo(event.todo_id)
        except TasqueError as exc:
            self.app.notify(f"Error: {exc}", severity="error")
            return
        self.query_one(InputBar).open_edit(todo.id, todo.text)

    async def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
        event.stop()
        if event.mode == "add":
            await self._handle_add(event.value)
        else:
            await self._handle_edit(event.value)

    def on_input_bar_cancelled(self, event: InputBar.Cancelled) -> None:
        event.stop()
        input_bar = self.query_one(InputBar)
        input_bar.close()
        self.query_one(TodoList).focus()

    async def _handle_add(self, value: str) -> None:
        input_bar = self.query_one(InputBar)
        try:
            self._controller.add_todo(value)
        except TasqueError as exc:
            # Keep the bar open with the typed text intact so the user can retry.
            self.app.notify(f"Error: {exc}", severity="error")
            return
        await self.refresh_todos()
        todo_list = self.query_one(TodoList)
        if len(todo_list) > 0:
            todo_list.index = len(todo_list) - 1  # cursor → the new row (blurred-dim)
        input_bar.clear_for_next_add()

    async def _handle_edit(self, value: str) -> None:
        input_bar = self.query_one(InputBar)
        todo_list = self.query_one(TodoList)
        try:
            updated = self._controller.edit_todo(input_bar.editing_id, value)
        except TasqueError as exc:
            self.app.notify(f"Error: {exc}", severity="error")
            input_bar.close()
            await self.refresh_todos()
            todo_list.focus()
            return
        todo_list.update_todo(updated)
        input_bar.close()
        todo_list.focus()

    # -- event handlers: delete --------------------------------------------- #

    def on_todo_list_delete_requested(self, event: TodoList.DeleteRequested) -> None:
        event.stop()
        try:
            todo = self._controller.get_todo(event.todo_id)
        except TasqueError as exc:
            self.app.notify(f"Error: {exc}", severity="error")
            return
        index = self.query_one(TodoList).index
        todo_id = event.todo_id
        self.app.push_screen(
            DeleteConfirmScreen(todo.text),
            lambda ok: self._on_delete_confirmed(ok, todo_id, index),
        )

    async def _on_delete_confirmed(self, ok: bool, todo_id: int, index: int | None) -> None:
        todo_list = self.query_one(TodoList)
        if not ok:
            todo_list.focus()  # same row stays highlighted
            return
        n = len(self._controller.list_todos())  # count BEFORE delete
        try:
            deleted = self._controller.delete_todo(todo_id)
        except TasqueError as exc:
            self.app.notify(f"Error: {exc}", severity="error")
            await self.refresh_todos()
            return
        await self.refresh_todos()
        todos = self._controller.list_todos()
        if not todos:
            self.focus()  # empty list can't hold a row cursor; keep a/?/q working
        else:
            landing = index if index is not None else 0
            todo_list.index = min(landing, n - 2)  # next row (clamp to prev if last)
            todo_list.focus()
        self.app.notify(f'✓ Deleted "{deleted.text}"', severity="information")

    # -- actions ------------------------------------------------------------ #

    def action_add_todo(self) -> None:
        """Open the InputBar in add mode (ignored if the bar is already open)."""
        input_bar = self.query_one(InputBar)
        if not input_bar.has_class("-hidden"):
            return  # bar already open; ignore a second `a`
        self.query_one(EmptyState).cta = _ADD_CTA
        input_bar.open_add()

    def action_help(self) -> None:
        """Show the help overlay. Implemented in a future feature."""
        self.app.notify("Help overlay: coming in a future feature", severity="information")
