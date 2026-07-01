"""Smoke tests: the app boots, shows the main screen, and quits on `q`.

Uses an in-memory database so these tests never touch the user's data file.
"""

from __future__ import annotations

from tasque.app import TasqueApp
from tasque.controller import TodoController
from tasque.db import Database
from tasque.screens.main import MainScreen


def _make_app() -> TasqueApp:
    """Return a TasqueApp backed by a fresh in-memory database."""
    db = Database(":memory:")
    return TasqueApp(controller=TodoController(db))


async def test_app_boots_and_shows_main_screen():
    app = _make_app()

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.title == "Tasque"
        assert isinstance(app.screen, MainScreen)


async def test_quits_on_q():
    app = _make_app()

    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")

    assert app.return_code == 0
