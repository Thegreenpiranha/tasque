"""DeleteConfirmScreen — the modal delete confirmation (Feature #5).

A :class:`~textual.screen.ModalScreen` that dims the main screen, centres a
bordered dialog naming the target task, and returns a ``bool`` via
``dismiss(True|False)`` (``True`` = delete confirmed). Built against
``docs/ux/delete-confirmation.md``.

Design points carried from the spec:
- **Default focus = Cancel** (the safe option) so a reflexive Enter cancels —
  the k9s lesson (a stray Enter must never delete).
- The focused button is marked with ``« … »`` brackets *and* Textual focus
  styling, so focus reads without relying on colour. CSS cannot inject that
  text, so the labels are rewritten in Python (a permitted styling exception).
- Copy is deliberately neutral: ``Delete this task?`` + the quoted title only —
  no "permanently", no undo hint (deferred to Feature #9, see ``LEARNINGS.md``).
"""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

logger = logging.getLogger("tasque.screens.delete_confirm")


class DeleteConfirmScreen(ModalScreen[bool]):
    """Confirm-or-cancel dialog for deleting one task.

    Args:
        task_text: The task's text, shown quoted so the action is concrete.
    """

    BINDINGS = [
        Binding("y", "confirm", "Delete", show=True),
        Binding("d", "confirm", show=False),  # d = "yes, delete what I pressed d for"
        Binding("n", "cancel", "Cancel", show=True),
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, task_text: str) -> None:
        super().__init__()
        self._task_text = task_text

    # -- compose ------------------------------------------------------------ #

    def compose(self) -> ComposeResult:
        with Container(id="confirm-dialog"):
            yield Static("Delete this task?", id="confirm-prompt", markup=False)
            yield Static(f'"{self._task_text}"', id="confirm-target", markup=False)
            with Horizontal(id="confirm-buttons"):
                yield Button("Delete", id="delete-btn", variant="error")
                yield Button("Cancel", id="cancel-btn", variant="default")
        yield Footer()

    # -- lifecycle ---------------------------------------------------------- #

    def on_mount(self) -> None:
        self.query_one("#confirm-dialog", Container).border_title = "Delete task?"
        # Default focus on the safe option (Cancel), so Enter-by-reflex cancels.
        self.query_one("#cancel-btn", Button).focus()

    # -- actions ------------------------------------------------------------ #

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    # -- events ------------------------------------------------------------- #

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "delete-btn")

    def on_descendant_focus(self, event: object) -> None:
        """Mark the focused button with ``« … »`` so focus reads in monochrome."""
        for button in self.query(Button):
            base = "Delete" if button.id == "delete-btn" else "Cancel"
            button.label = f"« {base} »" if button.has_focus else base
