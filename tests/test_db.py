"""Unit + integration tests for the persistence layer (Features #3, #6).

All tests run against an in-memory or tmp-path database — never the dev DB.
"""

from dataclasses import replace
from datetime import datetime

import pytest

from tasque.db import Database, PersistenceError, TodoNotFoundError
from tasque.models import Priority, Todo, TodoSort


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


# --------------------------------------------------------------------------- #
# Migration 0002 — adds priority column (Feature #6)
# --------------------------------------------------------------------------- #


def test_fresh_db_schema_version_is_2(db):
    """A newly opened DB applies all migrations and reaches version 2."""
    assert db.schema_version == 2


def test_v1_db_migrates_to_v2_preserving_data(tmp_path, monkeypatch):
    """A path-based v1 database is migrated to v2; existing rows keep priority=NULL."""
    import tasque.db as db_module

    all_migrations = list(db_module._MIGRATIONS)
    path = tmp_path / "v1.db"

    # Create a v1-only database
    monkeypatch.setattr(db_module, "_MIGRATIONS", all_migrations[:1])
    with Database(path) as v1:
        v1.add(Todo.new("old task"))
    # user_version is 1 after closing

    # Restore full migration list; reopening should run only 0002
    monkeypatch.setattr(db_module, "_MIGRATIONS", all_migrations)
    with Database(path) as v2:
        assert v2.schema_version == 2
        todos = v2.list_todos()
        assert len(todos) == 1
        assert todos[0].text == "old task"
        assert todos[0].priority is None  # NULL → None from additive migration


# --------------------------------------------------------------------------- #
# set_priority (Feature #6)
# --------------------------------------------------------------------------- #


def test_set_priority_persists_high(db):
    saved = db.add(Todo.new("task"))
    updated = db.set_priority(saved.id, Priority.HIGH)
    assert updated.priority is Priority.HIGH
    assert db.get(saved.id).priority is Priority.HIGH


def test_set_priority_persists_medium(db):
    saved = db.add(Todo.new("task"))
    updated = db.set_priority(saved.id, Priority.MEDIUM)
    assert updated.priority is Priority.MEDIUM


def test_set_priority_persists_low(db):
    saved = db.add(Todo.new("task"))
    updated = db.set_priority(saved.id, Priority.LOW)
    assert updated.priority is Priority.LOW


def test_set_priority_clears_to_none(db):
    """Setting priority back to None clears it (stores SQL NULL)."""
    saved = db.add(Todo.new("task"))
    db.set_priority(saved.id, Priority.HIGH)
    updated = db.set_priority(saved.id, None)
    assert updated.priority is None
    assert db.get(saved.id).priority is None


def test_set_priority_raises_for_missing_id(db):
    with pytest.raises(TodoNotFoundError):
        db.set_priority(999, Priority.HIGH)


def test_set_priority_returns_todo(db):
    saved = db.add(Todo.new("task"))
    result = db.set_priority(saved.id, Priority.MEDIUM)
    assert isinstance(result, Todo)
    assert result.id == saved.id


# --------------------------------------------------------------------------- #
# list_todos with sort parameter (Feature #6)
# --------------------------------------------------------------------------- #


def test_list_todos_default_sort_is_creation_order(db):
    """Default sort (CREATED / no arg) preserves insertion order."""
    a = db.add(Todo.new("a"))
    b = db.add(Todo.new("b"))
    c = db.add(Todo.new("c"))
    assert [t.id for t in db.list_todos()] == [a.id, b.id, c.id]


def test_list_todos_created_sort_explicit(db):
    """TodoSort.CREATED is the same as default insertion order."""
    a = db.add(Todo.new("a"))
    b = db.add(Todo.new("b"))
    assert [t.id for t in db.list_todos(sort=TodoSort.CREATED)] == [a.id, b.id]


def test_list_todos_priority_sort_high_before_medium_before_low(db):
    low = db.add(Todo.new("low"))
    db.set_priority(low.id, Priority.LOW)
    medium = db.add(Todo.new("medium"))
    db.set_priority(medium.id, Priority.MEDIUM)
    high = db.add(Todo.new("high"))
    db.set_priority(high.id, Priority.HIGH)

    ids = [t.id for t in db.list_todos(sort=TodoSort.PRIORITY)]
    assert ids == [high.id, medium.id, low.id]


def test_list_todos_priority_sort_null_last(db):
    """None-priority items sink below any explicitly-prioritised active item."""
    no_prio = db.add(Todo.new("none"))
    low = db.add(Todo.new("low"))
    db.set_priority(low.id, Priority.LOW)

    ids = [t.id for t in db.list_todos(sort=TodoSort.PRIORITY)]
    assert ids.index(low.id) < ids.index(no_prio.id)


def test_list_todos_priority_sort_id_tiebreak(db):
    """Same-priority tasks appear in creation order (id ASC tie-break)."""
    first = db.add(Todo.new("first high"))
    db.set_priority(first.id, Priority.HIGH)
    second = db.add(Todo.new("second high"))
    db.set_priority(second.id, Priority.HIGH)

    ids = [t.id for t in db.list_todos(sort=TodoSort.PRIORITY)]
    assert ids.index(first.id) < ids.index(second.id)


def test_list_todos_priority_sort_done_demoted_below_active(db):
    """Completed tasks appear after all active tasks regardless of priority."""
    done_high = db.add(Todo.new("done high"))
    db.set_priority(done_high.id, Priority.HIGH)
    db.set_completed(done_high.id, True)

    active_none = db.add(Todo.new("active none"))  # no priority

    result = db.list_todos(sort=TodoSort.PRIORITY)
    ids = [t.id for t in result]
    assert ids.index(active_none.id) < ids.index(done_high.id)


# --------------------------------------------------------------------------- #
# update() does not touch priority (Feature #6 guard)
# --------------------------------------------------------------------------- #


def test_update_leaves_priority_untouched(db):
    """db.update() (text edit) must not clobber or clear the priority."""
    saved = db.add(Todo.new("task"))
    db.set_priority(saved.id, Priority.HIGH)

    refreshed = db.get(saved.id)
    edited = db.update(replace(refreshed, text="renamed"))
    assert edited.priority is Priority.HIGH
    assert db.get(saved.id).priority is Priority.HIGH
