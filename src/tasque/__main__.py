"""Entry point for `python -m tasque`."""

from tasque.app import TasqueApp


def main() -> None:
    """Launch the Tasque TUI."""
    TasqueApp().run()


if __name__ == "__main__":
    main()
