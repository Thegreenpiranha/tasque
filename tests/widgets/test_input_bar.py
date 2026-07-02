"""Behavioural tests for the InputBar widget (Feature #5).

Assertions are on observable state — visibility class, border-title word, the
`Input`'s value/focus, and the messages the bar posts — never private methods.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Input

from tasque.widgets.input_bar import InputBar

# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #


class _BarApp(App):
    """Minimal app hosting one InputBar and recording the messages it posts."""

    def __init__(self) -> None:
        super().__init__()
        self.submitted: list[InputBar.Submitted] = []
        self.cancelled: list[InputBar.Cancelled] = []

    def compose(self) -> ComposeResult:
        yield InputBar()

    def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
        self.submitted.append(event)

    def on_input_bar_cancelled(self, event: InputBar.Cancelled) -> None:
        self.cancelled.append(event)


# --------------------------------------------------------------------------- #
# Idle / open / close
# --------------------------------------------------------------------------- #


async def test_bar_starts_hidden():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(InputBar).has_class("-hidden")


async def test_open_add_shows_bar_with_new_task_title():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_add()
        await pilot.pause()

        assert not bar.has_class("-hidden")
        assert bar.border_title == "New task"
        assert app.query_one("#bar-input", Input).value == ""


async def test_open_add_focuses_the_input():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_add()
        await pilot.pause()

        assert app.query_one("#bar-input", Input).has_focus


async def test_close_hides_the_bar():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_add()
        await pilot.pause()
        bar.close()
        await pilot.pause()

        assert bar.has_class("-hidden")


# --------------------------------------------------------------------------- #
# Edit mode pre-fill
# --------------------------------------------------------------------------- #


async def test_open_edit_prefills_value_and_edit_title():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_edit(7, "existing text")
        await pilot.pause()

        field = app.query_one("#bar-input", Input)
        assert bar.border_title == "Edit task"
        assert field.value == "existing text"
        assert field.cursor_position == len("existing text")
        assert bar.editing_id == 7


# --------------------------------------------------------------------------- #
# Submit (add)
# --------------------------------------------------------------------------- #


async def test_enter_with_text_posts_submitted_add():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_add()
        await pilot.pause()
        app.query_one("#bar-input", Input).value = "buy milk"
        await pilot.press("enter")
        await pilot.pause()

        assert len(app.submitted) == 1
        assert app.submitted[0].value == "buy milk"
        assert app.submitted[0].mode == "add"


async def test_enter_trims_surrounding_whitespace():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_add()
        await pilot.pause()
        app.query_one("#bar-input", Input).value = "   padded   "
        await pilot.press("enter")
        await pilot.pause()

        assert app.submitted[0].value == "padded"


async def test_empty_submit_pulses_invalid_and_posts_nothing():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_add()
        await pilot.pause()
        await pilot.press("enter")  # field is empty
        await pilot.pause()

        assert bar.has_class("-invalid")
        assert app.submitted == []


async def test_whitespace_only_submit_is_rejected():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_add()
        await pilot.pause()
        app.query_one("#bar-input", Input).value = "     "
        await pilot.press("enter")
        await pilot.pause()

        assert app.submitted == []
        assert bar.has_class("-invalid")


async def test_clear_for_next_add_empties_field_but_keeps_bar_open():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_add()
        await pilot.pause()
        app.query_one("#bar-input", Input).value = "something"
        bar.clear_for_next_add()
        await pilot.pause()

        assert app.query_one("#bar-input", Input).value == ""
        assert not bar.has_class("-hidden")


# --------------------------------------------------------------------------- #
# Submit (edit)
# --------------------------------------------------------------------------- #


async def test_edit_changed_text_posts_submitted_edit():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_edit(3, "old")
        await pilot.pause()
        app.query_one("#bar-input", Input).value = "new"
        await pilot.press("enter")
        await pilot.pause()

        assert len(app.submitted) == 1
        assert app.submitted[0].value == "new"
        assert app.submitted[0].mode == "edit"


async def test_edit_unchanged_text_posts_cancelled_not_submitted():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_edit(3, "same")
        await pilot.pause()
        await pilot.press("enter")  # value unchanged
        await pilot.pause()

        assert app.submitted == []
        assert len(app.cancelled) == 1
        assert app.cancelled[0].mode == "edit"


async def test_empty_edit_is_rejected():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_edit(3, "text")
        await pilot.pause()
        app.query_one("#bar-input", Input).value = ""
        await pilot.press("enter")
        await pilot.pause()

        assert app.submitted == []
        assert app.cancelled == []
        assert bar.has_class("-invalid")


# --------------------------------------------------------------------------- #
# Cancel
# --------------------------------------------------------------------------- #


async def test_escape_posts_cancelled():
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_add()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert len(app.cancelled) == 1
        assert app.cancelled[0].mode == "add"


async def test_escape_still_cancels_after_a_successful_add():
    """Once ≥1 task has been added, Esc reads "Done" but still closes the bar
    (the "Done"-labelled escape binding, input-bar.md § Footer hints)."""
    app = _BarApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        bar = app.query_one(InputBar)
        bar.open_add()
        await pilot.pause()
        bar.clear_for_next_add()  # a task landed → Esc now means "Done"
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert len(app.cancelled) == 1
        assert app.cancelled[0].mode == "add"
