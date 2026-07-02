"""Behavioural tests for TasqueApp's startup wiring (Feature #1/#4).

The rest of the suite always injects a ``controller=`` to bypass disk I/O, so
the *production* startup path — where the app builds its own ``Database`` from a
filesystem path and where ``default_user_db_path()`` resolves the location — is
otherwise never exercised. These tests cover that path against a tmp file so the
real user data directory is never touched.
"""

from __future__ import annotations

from tasque.app import TasqueApp, default_user_db_path
from tasque.screens.main import MainScreen

# --------------------------------------------------------------------------- #
# default_user_db_path
# --------------------------------------------------------------------------- #


def test_default_user_db_path_returns_db_file_under_data_dir(monkeypatch, tmp_path):
    data_dir = tmp_path / "Tasque"
    monkeypatch.setattr("tasque.app.user_data_dir", lambda *a, **k: str(data_dir))

    path = default_user_db_path()

    assert path == data_dir / "tasque.db"


def test_default_user_db_path_creates_the_data_dir(monkeypatch, tmp_path):
    data_dir = tmp_path / "does-not-exist-yet"
    monkeypatch.setattr("tasque.app.user_data_dir", lambda *a, **k: str(data_dir))

    default_user_db_path()

    assert data_dir.is_dir()


# --------------------------------------------------------------------------- #
# Construction from a db path (no injected controller)
# --------------------------------------------------------------------------- #


async def test_app_builds_its_own_database_from_db_path(tmp_path):
    db_file = tmp_path / "tasque.db"
    app = TasqueApp(db_path=db_file)

    async with app.run_test() as pilot:
        await pilot.pause()

        assert isinstance(app.screen, MainScreen)

    # Constructing the Database opened/migrated the file on disk.
    assert db_file.exists()
