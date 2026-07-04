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
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static

logger = logging.getLogger("tasque.widgets.input_bar")

_ADD_PLACEHOLDER = "Add a task and press Enter…"
_DUE_PLACEHOLDER = "YYYY-MM-DD, today, tomorrow, +3"


class InputBar(Widget):
    """Shared add/edit/due entry bar.

    Modes:
    - ``"add"`` — title ``New task``, empty field; Enter appends and the bar
      stays open + clears for rapid multi-add.
    - ``"edit"`` — title ``Edit task``, pre-filled field, caret at end; Enter
      saves and the bar closes.
    - ``"due"`` — title ``Due date``, pre-filled with the row's ISO date (or
      empty); Enter with text sets, Enter while empty clears (a blank field is
      *valid* here). The footer swaps ``Set due`` / ``Clear due`` on emptiness.

    The ``mode`` reactive drives the border-title word and the input placeholder.
    Show/hide is the ``-hidden`` class; the ``-invalid`` class is a ~600ms pulse
    on empty submit (add/edit) or a parse failure the screen detects (due). All
    styling lives in ``tasque.tcss``.
    """

    # "add" | "edit" | "due". init=False so watch_mode does not fire before
    # compose(); always_update=True so re-opening in the same mode drives the title.
    mode: reactive[str] = reactive("add", init=False, always_update=True)

    BINDINGS = [
        # Enter is bound with priority=True so it beats the child Input's own
        # (show=False) "enter" binding in the footer's binding dedup *and* fires
        # our submit handler before Input posts its Submitted. One binding per
        # (mode, field-state) gives the footer its mode-dependent label ("Add
        # task" / "Save" / "Set due" / "Clear due"); check_action() keeps exactly
        # one visible/active at a time.
        Binding("enter", "submit_add", "Add task", show=True, priority=True),
        Binding("enter", "submit_edit", "Save", show=True, priority=True),
        Binding("enter", "submit_due", "Set due", show=True, priority=True),
        Binding("enter", "clear_due", "Clear due", show=True, priority=True),
        # Escape closes the bar. Its label swaps Cancel↔Done: "Done" once at
        # least one task has been added this add-session (the rapid multi-add
        # affordance, per input-bar.md § Footer hints). Again two bindings +
        # check_action so the label — never colour — carries the state.
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("escape", "finish", "Done", show=True),
        # Tab is inert in the single-field bar (canonical convention — see
        # main-screen.md § Accessibility & Degradation). Esc, not Tab, closes it.
        Binding("tab", "noop", show=False),
        Binding("shift+tab", "noop", show=False),
    ]

    # -- messages (seams consumed by MainScreen) ---------------------------- #

    class Submitted(Message):
        """Posted on Enter to commit the field.

        ``mode`` is ``"add"``, ``"edit"``, or ``"due"`` so one ``MainScreen``
        handler serves every flow. ``value`` is the trimmed text; for ``"due"``
        it may be empty (a blank field means 'clear the due date').
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
        # Whether ≥1 task has been added during the current add-session; drives
        # the Esc label swap Cancel→Done. Reset each time the bar opens for add.
        self._added_this_session: bool = False

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
        self._added_this_session = False  # fresh session → Esc reads "Cancel"
        self.mode = "add"
        field = self.query_one("#bar-input", Input)
        field.value = ""
        self.remove_class("-hidden")
        field.focus()
        self.refresh_bindings()  # footer → add-mode hints

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
        self.refresh_bindings()  # footer → edit-mode hints

    def open_due(self, todo_id: int, prefill: str) -> None:
        """Show the bar in due mode for ``todo_id``, pre-filled with ``prefill``.

        ``prefill`` is the row's current due date as ISO (caret at end) or ``""``
        (the placeholder then teaches the grammar). ``editing_id`` is reused as
        "the row the bar acts on" — edit and due are mutually exclusive.
        """
        self.editing_id = todo_id
        self._original_text = None
        self.mode = "due"
        field = self.query_one("#bar-input", Input)
        field.value = prefill
        field.cursor_position = len(prefill)
        self.remove_class("-hidden")
        field.focus()
        self.refresh_bindings()  # footer → due-mode Set/Clear hint

    def clear_for_next_add(self) -> None:
        """Clear the field but keep the bar open and focused (rapid multi-add)."""
        self._added_this_session = True  # a task landed → Esc now reads "Done"
        field = self.query_one("#bar-input", Input)
        field.value = ""
        field.focus()
        self.refresh_bindings()  # footer → "Esc Done"

    def flash_invalid(self) -> None:
        """Pulse the bar ``-invalid`` (~600ms) and keep it open, input intact.

        Public wrapper over the internal pulse so the screen can signal a *parse*
        failure it detects (which the bar can't), reusing the empty-add feedback.
        """
        self._pulse_invalid()

    def close(self) -> None:
        """Hide the bar (``display: none``)."""
        self.add_class("-hidden")

    # -- reactive watchers -------------------------------------------------- #

    def watch_mode(self, mode: str) -> None:
        if mode == "edit":
            self.border_title = "Edit task"
        elif mode == "due":
            self.border_title = "Due date"
        else:
            self.border_title = "New task"
        self._sync_placeholder(mode)
        self.refresh_bindings()  # footer label follows the mode word

    def _sync_placeholder(self, mode: str) -> None:
        """The empty-field placeholder teaches due grammar; add uses its own hint."""
        placeholder = _DUE_PLACEHOLDER if mode == "due" else _ADD_PLACEHOLDER
        self.query_one("#bar-input", Input).placeholder = placeholder

    # -- dynamic footer ----------------------------------------------------- #

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Show exactly the mode-appropriate Enter/Esc hint in the footer.

        Bindings share the Enter/Esc keys (one label per mode/field-state); this
        keeps precisely one enabled + visible so the footer swaps ``Add task``/
        ``Save``/``Set due``/``Clear due`` and ``Cancel``/``Done`` without ever
        showing two. In ``"due"`` mode the Enter label tracks the field's
        emptiness (``Set due`` with text, ``Clear due`` when blank), refreshed by
        ``on_input_changed``.
        """
        if action == "submit_add":
            return self.mode == "add"
        if action == "submit_edit":
            return self.mode == "edit"
        if action == "submit_due":  # "Set due": due mode with text in the field
            return self.mode == "due" and not self._field_is_empty()
        if action == "clear_due":  # "Clear due": due mode with an empty field
            return self.mode == "due" and self._field_is_empty()
        if action == "cancel":  # "Cancel": edit/due mode, or add before the first add
            return not (self.mode == "add" and self._added_this_session)
        if action == "finish":  # "Done": add mode after ≥1 add this session
            return self.mode == "add" and self._added_this_session
        return True

    def _field_is_empty(self) -> bool:
        """Whether the input holds no non-whitespace text (safe before compose)."""
        try:
            return not self.query_one("#bar-input", Input).value.strip()
        except NoMatches:
            return True

    # -- actions ------------------------------------------------------------ #

    def action_submit_add(self) -> None:
        self._submit()

    def action_submit_edit(self) -> None:
        self._submit()

    def action_submit_due(self) -> None:
        self._submit()

    def action_clear_due(self) -> None:
        self._submit()

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled(self.mode))

    def action_finish(self) -> None:
        # "Done" is the same close-the-bar action as Cancel; only the label
        # differs (a task was added, so leaving is "done" not "cancel").
        self.post_message(self.Cancelled(self.mode))

    def action_noop(self) -> None:
        """Tab / Shift+Tab: intentionally inert in the single-field bar."""

    # -- events ------------------------------------------------------------- #

    def on_input_changed(self, event: Input.Changed) -> None:
        """Track empty↔non-empty in due mode so the Set/Clear label follows typing."""
        if self.mode == "due":
            self.refresh_bindings()

    # -- helpers ------------------------------------------------------------ #

    def _submit(self) -> None:
        """Validate the field and post Submitted / Cancelled, or pulse invalid.

        Invoked by the priority Enter binding (which fires ahead of the child
        ``Input``'s own Enter handling), so ``Input.Submitted`` never reaches us.
        In ``"due"`` mode an empty field is *valid* and means 'clear' — it posts
        ``Submitted("", "due")`` rather than pulsing (the screen then clears).
        """
        value = self.query_one("#bar-input", Input).value.strip()
        if self.mode == "due":
            # Empty is valid (clear); non-empty is parsed by the screen, which
            # calls flash_invalid() on junk. The bar never rejects here.
            self.post_message(self.Submitted(value, self.mode))
            return
        if not value:
            self._pulse_invalid()
            return
        if self.mode == "edit" and value == self._original_text:
            # Unchanged edit: no write, identical close/refocus path as cancel.
            self.post_message(self.Cancelled(self.mode))
            return
        self.post_message(self.Submitted(value, self.mode))

    def _pulse_invalid(self) -> None:
        self.add_class("-invalid")
        self.set_timer(0.6, lambda: self.remove_class("-invalid"))
