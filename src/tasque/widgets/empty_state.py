"""Empty-state widget shown inside the list panel when there are no todos."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class EmptyState(Static):
    """Centered placeholder shown when the todo list is empty.

    ``cta`` is a call-to-action line shown below the primary message. It is
    empty until Feature #5 adds the "Press a to add…" hint; wiring it as a
    reactive now means Feature #5 can just set ``empty_state.cta = "..."``
    without touching this widget's structure.
    """

    cta: reactive[str] = reactive("", init=False)

    def __init__(self) -> None:
        super().__init__("No tasks yet")

    def watch_cta(self, value: str) -> None:
        if value:
            self.update(f"No tasks yet\n{value}")
        else:
            self.update("No tasks yet")
