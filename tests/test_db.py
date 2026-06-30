"""Unit + integration tests for the persistence layer (Feature #3).

All tests run against an in-memory or tmp-path database — never the dev DB.
"""

from dataclasses import replace
from datetime import datetime

import pytest

from tasque.db import Database, PersistenceError, TodoNotFoundError
from tasque.models import Todo


@pytest.fixture
def db():
    database = Database(":memory:")
    try:
        yield database
    finally:
        database.close()


# --------------------------------------------------------------------------- #
# CRUD round-trips
# --------------------------------------------------------------------------- #
def test_add_assigns_id_and_returns_todo(db):
    saved = db.add(Todo.new("buy milk"))
    assert saved.id is not None
    assert saved.text == "buy milk"
    assert saved.completed is False


def test_add_get_roundtrip_preserves_created_at(db):
    when = datetime(2026, 1, 2, 3, 4, 5)
    saved = db.add(Todo.new("with timestamp", created_at=when))
    fetched = db.get(saved.id)
    assert fetched == saved
    assert fetched.created_at == when
    assert isinstance(fetched.created_at, datetime)


def test_list_returns_insertion_order(db):
    a = db.add(Todo.new("a"))
    b = db.add(Todo.new("b"))
    c = db.add(Todo.new("c"))
    assert [t.id for t in db.list_todos()] == [a.id, b.id, c.id]


def test_list_empty(db):
    assert db.list_todos() == []


def test_update_persists_text_and_completed(db):
    saved = db.add(Todo.new("draft"))
    updated = db.update(replace(saved, text="final", completed=True))
    assert updated.text == "final"
    assert updated.completed is True
    assert db.get(saved.id).text == "final"


def test_set_completed_toggles_both_ways(db):
    saved = db.add(Todo.new("task"))
    assert db.set_completed(saved.id, True).completed is True
    assert db.get(saved.id).completed is True
    assert db.set_completed(saved.id, False).completed is False


def test_delete_returns_deleted_and_removes_it(db):
    saved = db.add(Todo.new("temp"))
    deleted = db.delete(saved.id)
    assert deleted.id == saved.id
    assert deleted.text == "temp"
    with pytest.raises(TodoNotFoundError):
        db.get(saved.id)


# --------------------------------------------------------------------------- #
# Not-found paths
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "operation",
    [
        lambda db: db.get(999),
        lambda db: db.delete(999),
        lambda db: db.set_completed(999, True),
        lambda db: db.update(Todo(text="x", id=999)),
    ],
)
def test_missing_id_raises_not_found(db, operation):
    with pytest.raises(TodoNotFoundError):
        operation(db)


def test_not_found_carries_the_id(db):
    with pytest.raises(TodoNotFoundError) as exc_info:
        db.get(424242)
    assert exc_info.value.todo_id == 424242


def test_update_unsaved_todo_raises_value_error(db):
    with pytest.raises(ValueError):
        db.update(Todo.new("never saved"))


# --------------------------------------------------------------------------- #
# Migrations / persistence across reopen
# --------------------------------------------------------------------------- #
def test_fresh_db_is_migrated(db):
    assert db.schema_version == len_migrations()


def test_persists_and_skips_migrations_on_reopen(tmp_path):
    path = tmp_path / "tasque.db"
    with Database(path) as first:
        saved = first.add(Todo.new("persisted"))

    with Database(path) as second:
        fetched = second.get(saved.id)
        assert fetched.text == "persisted"
        assert second.schema_version == len_migrations()


def test_broken_migration_raises_migration_error(tmp_path, monkeypatch):
    from tasque import db as db_module

    def bad_migration(conn):
        conn.execute("CREATE TABLE")  # invalid SQL

    monkeypatch.setattr(db_module, "_MIGRATIONS", [bad_migration])
    with pytest.raises(db_module.MigrationError):
        Database(tmp_path / "broken.db")


def test_add_wraps_sqlite_error_as_persistence_error(db):
    # text is NOT NULL in the schema; a None slips past the (frozen) dataclass
    # at runtime and must surface as a domain error, not a raw sqlite3 error.
    bad = replace(Todo.new("ok"), text=None)
    with pytest.raises(PersistenceError):
        db.add(bad)


def len_migrations() -> int:
    from tasque.db import _MIGRATIONS

    return len(_MIGRATIONS)
