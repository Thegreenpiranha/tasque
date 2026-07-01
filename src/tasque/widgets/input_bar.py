"""InputBar widget — the docked add/edit text-entry bar (Feature #5).

A single bordered bar docked at the bottom of :class:`~tasque.screens.main.MainScreen`,
between the list panel and the Footer. It is the *one* place task text is entered,
serving both the **add** flow (``docs/ux/input-bar.md``) and the **edit** flow
(``docs/ux/edit-screen.md``) — same surface, two modes distinguished by the
border-title *word* (never colour).

It lives outside the ``ListView`` subtree so its ``Input`` focuses normally
(``ListView.can_focus_children=False`` would block an in-row input — see
``docs/ux/edit-screen.md``). It shows/hides via the shared ``-hidden`` class so
idle screens are unchanged from Feature #4.

The bar owns only its ephemeral entry state and never touches the controller or
``db.py``: it posts :class:`InputBar.Submitted` / :class:`InputBar.Cancelled`
and lets ``MainScreen`` drive persistence and clearing.
"""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static

logger = logging.getLogger("tasque.widgets.input_bar")

_ADD_PLACEHOLDER = "Add a task and press Enter…"


class InputBar(Widget):
    """Shared add/edit entry bar.

    Modes:
    - ``"add"`` — title ``New task``, empty field; Enter appends and the bar
      stays open + clears for rapid multi-add.
    - ``"edit"`` — title ``Edit task``, pre-filled field, caret at end; Enter
      saves and the bar closes.

    The ``mode`` reactive drives the border-title word and the input placeholder.
    Show/hide is the ``-hidden`` class; the ``-invalid`` class is a ~600ms pulse
    on empty submit. All styling lives in ``tasque.tcss``.
    """

    # "add" | "edit". init=False so watch_mode does not fire before compose();
    # always_update=True so re-opening in the same mode still drives the title.
    mode: reactive[str] = reactive("add", init=False, always_update=True)

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        # Tab is inert in the single-field bar (canonical convention — see
        # main-screen.md § Accessibility & Degradation). Esc, not Tab, closes it.
        Binding("tab", "noop", show=False),
        Binding("shift+tab", "noop", show=False),
    ]

    # -- messages (seams consumed by MainScreen) ---------------------------- #

    class Submitted(Message):
        """Posted on Enter with non-empty, trimmed text.

        ``mode`` is ``"add"`` or ``"edit"`` so one ``MainScreen`` handler serves
        both flows.
        """

        def __init__(self, value: str, mode: str) -> None:
            super().__init__()
            self.value = value
            self.mode = mode

    class Cancelled(Message):
        """Posted on Esc, or on an unchanged edit confirm (a no-op close)."""

        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode

    def __init__(self) -> None:
        super().__init__(classes="-hidden")
        self.editing_id: int | None = None
        self._original_text: str | None = None

    # -- compose ------------------------------------------------------------ #

    def compose(self) -> ComposeResult:
        with Horizontal():
            # markup=False so Rich does not treat the glyph as Console Markup.
            yield Static("› ", id="prompt", markup=False)
            yield Input(placeholder=_ADD_PLACEHOLDER, id="bar-input")

    # -- public API --------------------------------------------------------- #

    def open_add(self) -> None:
        """Show the bar in add mode with an empty, focused field."""
        self.editing_id = None
        self._original_text = None
        self.mode = "add"
        field = self.query_one("#bar-input", Input)
        field.value = ""
        self.remove_class("-hidden")
        field.focus()

    def open_edit(self, todo_id: int, text: str) -> None:
        """Show the bar in edit mode, pre-filled with ``text``, caret at end."""
        self.editing_id = todo_id
        self._original_text = text
        self.mode = "edit"
        field = self.query_one("#bar-input", Input)
        field.value = text
        field.cursor_position = len(text)
        self.remove_class("-hidden")
        field.focus()

    def clear_for_next_add(self) -> None:
        """Clear the field but keep the bar open and focused (rapid multi-add)."""
        field = self.query_one("#bar-input", Input)
        field.value = ""
        field.focus()

    def close(self) -> None:
        """Hide the bar (``display: none``)."""
        self.add_class("-hidden")

    # -- reactive watchers -------------------------------------------------- #

    def watch_mode(self, mode: str) -> None:
        if mode == "edit":
            self.border_title = "Edit task"
        else:
            self.border_title = "New task"

    # -- events ------------------------------------------------------------- #

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        value = event.value.strip()
        if not value:
            self._pulse_invalid()
            return
        if self.mode == "edit" and value == self._original_text:
            # Unchanged edit: no write, identical close/refocus path as cancel.
            self.post_message(self.Cancelled(self.mode))
            return
        self.post_message(self.Submitted(value, self.mode))

    # -- actions ------------------------------------------------------------ #

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled(self.mode))

    def action_noop(self) -> None:
        """Tab / Shift+Tab: intentionally inert in the single-field bar."""

    # -- helpers ------------------------------------------------------------ #

    def _pulse_invalid(self) -> None:
        self.add_class("-invalid")
        self.set_timer(0.6, lambda: self.remove_class("-invalid"))
