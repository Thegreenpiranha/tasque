# PLAN.md

The feature ledger. Moves features through **Backlog → In Progress → Done**. This file is the project's memory of what's been built and what's next, surviving every `/clear`.

---

## Status Legend

- 📋 **Backlog** — defined but not started
- 🚧 **In Progress** — currently being built
- ✅ **Done** — implemented, tested, reviewed

## Done

### ✅ Feature #1 — Project Scaffolding — _completed 2026-06-29_

uv/pyproject for Python 3.12 (deps: textual; dev: pytest, pytest-asyncio, ruff). Package
`src/tasque/` with `__init__.py`, `__main__.py`, minimal `TasqueApp` (placeholder banner,
quits on `q`), empty `tasque.tcss`, and `widgets/` + `screens/` packages. Smoke tests green,
ruff clean.

### ✅ Feature #2 — Todo Data Model — _completed 2026-06-29_

Frozen `Todo` dataclass in `models.py` (`text`, `id`, `completed`, `created_at` + nullable
placeholders `priority`/`due_date`/`category_id`/`list_id`), `Todo.new()` factory for unsaved
items with injectable `created_at`. Pure stdlib module — no DB/Textual imports. Unit tests
cover defaults, full construction, immutability, and `replace`.

### ✅ Feature #3 — SQLite Persistence Layer — _completed 2026-06-29_

`db.py` owns SQLite exclusively. A `Database` class wraps one long-lived connection (keeps
`:memory:` alive, lets tests inject a path); `user_version`-based append-only migration ladder
(v1 `todos` table is minimal — later features add columns via their own migrations). CRUD:
`add`/`get`/`list_todos`/`update`/`delete`/`set_completed` returning `Todo` dataclasses; `delete`
returns the deleted item (seam for undo, Feature #9). Exceptions `TasqueError` →
`TodoNotFoundError`/`MigrationError`/`PersistenceError`; raw `sqlite3` errors never escape.
Tests use `:memory:`/tmp-path: CRUD round-trips, not-found paths, reopen+migration-skip, error
wrappers. Coverage 96% (db.py 100%).

### ✅ Feature #4 — Main Screen: TodoList & TodoItem Widgets — _completed 2026-07-01_

`platformdirs` added for cross-platform DB path; `controller.py` introduced (`TodoController`)
as the layer between the UI and `db.py` — `list_todos()` implemented, mutation methods are
`NotImplementedError` seams for #5/#6, `_apply` + `Command` protocol seams for #9. New widgets:
`TodoItem(ListItem)` — single-line row with gutter/checkbox/priority/title/meta slots, reactive
`todo` drives checkbox+title+done-class updates, gutter shows `▸` on highlight; `TodoList(ListView)`
— `set_todos()` (async clear + mount), `update_todo()` (single-row re-render), `current_todo_id`,
vim `j/k/g/G/ctrl+d/ctrl+u` navigation, four intent-message seams for #5/#6;
`EmptyState(Static)` — shows "No tasks yet", `cta` reactive seam for #5.
`MainScreen(Screen)` — Header/`#list-panel`(border-title counts)/Footer, async `refresh_todos()`
toggles `TodoList`/`EmptyState` via `-hidden` class, `on_list_view_highlighted` wired.
`TasqueApp` now accepts `controller=` injection (tests) or builds from `default_user_db_path()`
(platformdirs), pushes `MainScreen` on mount; banner removed.
75 tests, 93% coverage (all modules ≥80%), ruff clean.

### ✅ Feature #5 — InputBar: Add, Toggle Complete, Edit, Delete — _completed 2026-07-01_

The core interaction loop. `controller.py` mutations implemented — `add`/`toggle`/`edit`/
`delete` each build a private `_*Command` (`execute()`/`undo()` + `result`) and route through
`_apply` (still `-> None`; result rides on `command.result`), so Feature #9 hooks the undo
stack with zero call-site changes; `get_todo()` read added for edit pre-fill / delete text.
New `InputBar(Widget)` — docked bottom bar shared by add/edit, `mode` reactive
(`always_update=True`) drives the border-title word, `-hidden`/`-invalid` classes, posts
`Submitted(value, mode)`/`Cancelled(mode)`; add stays open+clears for rapid multi-add, edit
closes, unchanged-edit posts `Cancelled`, empty/whitespace pulses `-invalid`. New
`DeleteConfirmScreen(ModalScreen[bool])` — neutral copy, Cancel-focused default (k9s lesson),
`« »` focus marker, `y`/`d` confirm · `n`/`Esc` cancel. `TodoList` gained `space`/`enter`→toggle,
`e`→edit, `d`→delete bindings posting the existing intents. `MainScreen` composes the bar, wires
all four flows through the controller, post-delete cursor rule (next row, clamp to prev if last,
EmptyState when empty), and `TasqueError`→error-toast guards. Design artefacts:
`docs/ux/{input-bar,edit-screen,delete-confirmation}.md`, `docs/architecture/feature-5.md`.
No schema change (`user_version` stays 1). 126 tests, 94% coverage (all modules ≥80%,
controller 100%), ruff clean.

## In Progress

_Nothing in progress._

## Backlog

Ordered by dependency. Pick the topmost item whose dependencies are all Done.

---

### Feature #6 — Priority Levels

**Goal:** Let tasks carry a priority and surface it visually.

**Acceptance criteria:**
- Additive migration adds `priority` (e.g. none/low/medium/high) to the schema.
- Set/cycle priority on the focused item via keybinding; persists.
- `TodoItem` shows priority (color/marker via `tasque.tcss` classes); list can sort by priority.
- Tests cover persistence, cycling, and sort order.

**Depends on:** Feature #5

---

### Feature #7 — Due Dates

**Goal:** Attach due dates to tasks and highlight overdue ones.

**Acceptance criteria:**
- Additive migration adds `due_date` (ISO date string, nullable).
- Set/clear a due date on the focused item; persists.
- `TodoItem` displays the due date; overdue tasks are visually distinct.
- Sort/filter by due date available.
- Tests cover set/clear, overdue detection (with a fixed "now"), and sort.

**Depends on:** Feature #5

---

### Feature #8 — Categories

**Goal:** Group tasks under user-defined categories.

**Acceptance criteria:**
- Additive migration adds a `categories` table and `todo.category_id` FK.
- Create/assign/remove a category on a task; persists.
- `TodoItem` shows its category; main screen can filter by category.
- Tests cover category CRUD, assignment, and filtering.

**Depends on:** Feature #5

---

### Feature #9 — Undo / Redo

**Goal:** A consistent undo/redo stack across all mutating operations.

**Acceptance criteria:**
- A single command/undo stack in the controller; every mutation (add/edit/delete/toggle/priority/due/category) is undoable and redoable.
- Keybindings for undo and redo; the list reflects the result.
- Stack survives within a session; behaviour at stack boundaries is defined (no-op).
- Tests cover undo/redo for each mutation type and boundary conditions.

**Depends on:** Features #6, #7, #8

**Notes:** Implementing this after the mutation set is known avoids retrofitting commands later. This is why all mutations were funneled through the controller from Feature #5.

---

### Feature #10 — Multiple Lists

**Goal:** Support more than one to-do list and switch between them.

**Acceptance criteria:**
- Additive migration adds a `lists` table and `todo.list_id` FK; existing todos migrate into a default list.
- Create, rename, delete, and switch lists (a list-picker screen or panel).
- The main screen scopes to the active list; undo/redo respects list context.
- Tests cover list CRUD, scoping, and the default-list migration.

**Depends on:** Feature #9

---

### Feature #11 — Global Search

**Goal:** Find tasks across all lists by text and attributes.

**Acceptance criteria:**
- Search screen/overlay queries across lists by text, and optionally by priority / due / category.
- Results are navigable; selecting a result jumps to the task in its list.
- Search goes through the controller → `db.py` (no SQL in the UI).
- Tests cover text search, attribute filters, and cross-list results.

**Depends on:** Feature #10

---

### Feature #12 — Export / Import

**Goal:** Move data in and out of the app via a portable file format.

**Acceptance criteria:**
- Export all lists/tasks (with priority, due, category) to a portable format (e.g. JSON; CSV optional).
- Import from the same format, round-tripping without data loss; defined conflict/merge behaviour.
- Errors (malformed file, version mismatch) surface as user-facing messages, never raw tracebacks.
- Tests cover export→import round-trip, malformed input, and merge behaviour.

**Depends on:** Feature #11

---

## How to Use This File

1. Pick the top item from **Backlog** that has its dependencies marked Done.
2. Move it to **In Progress**.
3. Follow the `new-feature` skill.
4. When the Definition of Done is met (see CLAUDE.md), move it to **Done** and add the completion date.
5. Append any discoveries to LEARNINGS.md.

**Important:** Never delete items from Done. They are the project's history.
