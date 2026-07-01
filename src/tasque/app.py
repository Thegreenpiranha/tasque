"""The top-level Tasque Textual application."""

from __future__ import annotations

import logging
from pathlib import Path

from platformdirs import user_data_dir
from textual.app import App

from tasque.controller import TodoController
from tasque.db import Database
from tasque.screens.main import MainScreen

logger = logging.getLogger("tasque")


def default_user_db_path() -> Path:
    """Return the platform-appropriate path for the user's database file.

    On Windows: ``%LOCALAPPDATA%\\Tasque\\tasque.db``
    On macOS/Linux: follows XDG / platformdirs conventions.
    Creates the directory if it does not exist.
    """
    data_dir = Path(user_data_dir("Tasque", appauthor=False))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "tasque.db"


class TasqueApp(App[None]):
    """Tasque's root application.

    Args:
        controller: An already-constructed :class:`~tasque.controller.TodoController`.
            When provided (e.g. in tests), the ``db_path`` argument is ignored.
        db_path: Path to the SQLite database file.  Defaults to the
            platform-appropriate user data directory (via platformdirs).
            Ignored when ``controller`` is provided.
    """

    CSS_PATH = "tasque.tcss"
    TITLE = "Tasque"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(
        self,
        *,
        controller: TodoController | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        if controller is not None:
            self._controller = controller
        else:
            db = Database(db_path or default_user_db_path())
            self._controller = TodoController(db)

    def on_mount(self) -> None:
        self.push_screen(MainScreen(self._controller))
