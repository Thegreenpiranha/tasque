"""The top-level Tasque Textual application.

Feature #1 scaffolding: shows a placeholder banner and quits on `q`.
Screen and widget wiring arrives in later features.
"""

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static


class TasqueApp(App[None]):
    """Tasque's root application.

    Bindings and screen wiring will grow as features land; for now this is a
    minimal shell proving the package launches and exits cleanly.
    """

    CSS_PATH = "tasque.tcss"
    TITLE = "Tasque"
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Tasque — terminal to-do manager", id="banner")
        yield Footer()
