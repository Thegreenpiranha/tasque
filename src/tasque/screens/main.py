"""The main Tasque screen — todo list, empty state, and key-hint footer."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, ListView

from tasque.controller import TodoController
from tasque.widgets.empty_state import EmptyState
from tasque.widgets.todo_list import TodoList

logger = logging.getLogger("tasque.screens.main")


class MainScreen(Screen[None]):
    """The primary screen: a bordered list panel with Header and Footer.

    Layout::

        Header (1 row)
        ┌─ Inbox · N active · M done ──────────────────────┐
        │  TodoList (scrollable)                            │
        │  EmptyState (centered, hidden when populated)     │
        └───────────────────────────────────────────────────┘
        Footer (1 row)

    The ``#list-panel`` border-title provides the lazygit-style context line.
    ``EmptyState`` and ``TodoList`` toggle ``-hidden`` depending on whether the
    list has any items.
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

        active = sum(1 for t in todos if not t.completed)
        done = sum(1 for t in todos if t.completed)
        self.query_one(
            "#list-panel", Container
        ).border_title = f"Inbox · {active} active · {done} done"

        has_todos = bool(todos)
        todo_list.set_class(not has_todos, "-hidden")
        empty_state.set_class(has_todos, "-hidden")

    # -- event handlers ----------------------------------------------------- #

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Acknowledge highlight changes; future features may update a status bar."""
        event.stop()

    # -- actions ------------------------------------------------------------ #

    def action_add_todo(self) -> None:
        """Open the InputBar to add a task. Implemented in Feature #5."""
        self.app.notify("Add: coming in Feature #5", severity="information")

    def action_help(self) -> None:
        """Show the help overlay. Implemented in a future feature."""
        self.app.notify("Help overlay: coming in a future feature", severity="information")
