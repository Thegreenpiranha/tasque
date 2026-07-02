"""Test the ``python -m tasque`` entry point (Feature #1).

``__main__.main()`` is what actually runs when a user launches the app. It is
never hit by the rest of the suite (which drives the app through the pilot
harness), so a typo there would ship silently. This test verifies it constructs
a :class:`TasqueApp` and runs it — without launching a real TUI and without
touching the user's real data directory (the path is redirected to a tmp dir).
"""

from __future__ import annotations

from tasque.__main__ import main
from tasque.app import TasqueApp


def test_main_constructs_and_runs_the_app(monkeypatch, tmp_path):
    # Redirect the user data dir so main()'s default TasqueApp() never writes
    # to the real %LOCALAPPDATA%/Tasque location.
    monkeypatch.setattr("tasque.app.user_data_dir", lambda *a, **k: str(tmp_path / "Tasque"))
    launched: list[TasqueApp] = []
    monkeypatch.setattr(TasqueApp, "run", lambda self: launched.append(self))

    main()

    assert len(launched) == 1
    assert isinstance(launched[0], TasqueApp)
