"""Behavioural tests for DeleteConfirmScreen (Feature #5).

Asserts on the dismiss result, default-safe focus, the quoted target text, and
the focused-button `« »` marker — all observable state, not private methods.
"""

from __future__ import annotations

from textual.app import App
from textual.widgets import Button

from tasque.screens.delete_confirm import DeleteConfirmScreen

# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #


class _ModalApp(App):
    """Pushes a DeleteConfirmScreen and records its dismiss result."""

    def __init__(self, task_text: str = "Finish the report") -> None:
        super().__init__()
        self._task_text = task_text
        self.result: bool | None = None
        self.dismissed = False

    def on_mount(self) -> None:
        self.push_screen(DeleteConfirmScreen(self._task_text), self._record)

    def _record(self, result: bool) -> None:
        self.result = result
        self.dismissed = True


# --------------------------------------------------------------------------- #
# Content
# --------------------------------------------------------------------------- #


async def test_dialog_quotes_the_task_text():
    app = _ModalApp("Water the plants")
    async with app.run_test() as pilot:
        await pilot.pause()
        target = app.screen.query_one("#confirm-target")

        assert "Water the plants" in str(target.render())


async def test_border_title_names_the_action():
    app = _ModalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        dialog = app.screen.query_one("#confirm-dialog")

        assert dialog.border_title == "Delete task?"


# --------------------------------------------------------------------------- #
# Default-safe focus
# --------------------------------------------------------------------------- #


async def test_cancel_is_focused_by_default():
    app = _ModalApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.screen.query_one("#cancel-btn", Button).has_focus


async def test_focused_button_is_marked_with_brackets():
    app = _ModalApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        cancel = app.screen.query_one("#cancel-btn", Button)
        assert "«" in str(cancel.label) and "»" in str(cancel.label)


# --------------------------------------------------------------------------- #
# Confirm paths
# --------------------------------------------------------------------------- #


async def test_y_confirms_delete():
    app = _ModalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()

        assert app.dismissed is True
        assert app.result is True


async def test_d_confirms_delete():
    app = _ModalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()

        assert app.result is True


async def test_enter_on_default_cancel_cancels():
    app = _ModalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")  # reflexive Enter on the default (Cancel)
        await pilot.pause()

        assert app.result is False


# --------------------------------------------------------------------------- #
# Cancel paths
# --------------------------------------------------------------------------- #


async def test_n_cancels():
    app = _ModalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()

        assert app.result is False


async def test_escape_cancels():
    app = _ModalApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert app.result is False
