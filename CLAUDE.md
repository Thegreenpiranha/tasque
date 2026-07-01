# CLAUDE.md

This file is loaded into Claude Code's context at the start of every session. It carries the project's conventions forward across `/clear` resets so the conversation can be wiped without losing the rules.

---

## Project

**Name:** Tasque — a terminal to-do manager
**Purpose:** A keyboard-driven TUI to-do application for managing tasks, priorities, due dates, and multiple lists entirely from the terminal.
**Audience:** Terminal-comfortable users who want a fast, local, single-binary to-do app without leaving the keyboard. (Worked example from Linux Magazine, Issue 308, July 2026.)

## Tech Stack

- **Language:** Python 3.12
- **Framework:** [Textual](https://textual.textualize.io/) (TUI)
- **Database:** SQLite (via the stdlib `sqlite3` module), one local file on disk
- **Testing:** pytest (with `pytest-asyncio` for Textual's async test harness)
- **Lint/Format:** ruff (lint + format)
- **Build/Run:** uv for dependency management; run with `uv run python -m tasque`

## Directory Structure

```
.
├── CLAUDE.md          # this file — conventions
├── PLAN.md            # backlog / in progress / done
├── LEARNINGS.md       # discoveries logged as we go
├── pyproject.toml     # project metadata + dependencies (managed by uv)
├── .claude/
│   ├── agents/        # sub-agents (architect, researcher, implementer, tester, reviewer)
│   └── skills/        # procedural skills (new-feature, ui-component, testing)
├── docs/
│   ├── ux/            # UX specs the researcher saves here
│   └── architecture/  # architect design artefacts, one per feature (feature-<n>.md)
├── src/
│   └── tasque/
│       ├── __init__.py
│       ├── __main__.py        # entry point — `python -m tasque`
│       ├── app.py             # the Textual App subclass, bindings, screen wiring
│       ├── db.py              # persistence layer — the ONLY module that touches SQLite
│       ├── models.py          # dataclasses: Todo, Category, TodoList, etc.
│       ├── controller.py      # app logic / view-model between widgets and db
│       ├── widgets/           # reusable Textual widgets (TodoList, TodoItem, InputBar, …)
│       ├── screens/           # full-screen Textual screens (main, search, list picker, …)
│       └── tasque.tcss        # Textual CSS — all styling lives here, not inline
└── tests/                     # mirrors src/tasque/ structure
```

## Code Conventions

- **Files & naming:** snake_case for modules and functions; PascalCase for classes and Textual widgets/screens. One widget or screen per file, file named after the class in snake_case (`todo_item.py` → `class TodoItem`).
- **State location:** SQLite is the single source of truth for persisted data. The controller holds no long-lived mutable copy of the data — it reads from `db.py` and hands plain dataclasses to widgets. Widgets hold only their own ephemeral UI state (focus, expanded/collapsed, edit-in-progress). Never let two layers own the same fact.
- **Imports:** stdlib, then third-party (textual, etc.), then local — each group separated by a blank line. Use absolute imports within the package (`from tasque.models import Todo`), not relative.
- **Error handling:** Persistence errors raise custom exceptions defined in `db.py` (e.g. `TodoNotFoundError`, subclassing a base `TasqueError`). The controller catches them and turns them into user-facing messages; widgets never see raw `sqlite3` exceptions. Never swallow an exception silently — surface it via the app's notification/toast system.
- **Logging:** Use the stdlib `logging` module under the `tasque` logger. Never `print()` — it corrupts the TUI. Textual's `self.log()` is fine for dev-time tracing inside widgets.
- **Comments:** Only when the *why* isn't obvious from the code. No restating what the line does.
- **Public API shape:** Pass data as frozen dataclasses (`models.py`), not dicts. Functions that mutate persisted state live on `db.py` / the controller and return the updated dataclass (or `None`), not a bare row tuple.

## Architectural Rules

- **Persistence boundary:** `db.py` is the *only* module that imports `sqlite3` or writes SQL. Every other module goes through its functions. No SQL strings anywhere else.
- **Layer boundaries:** Widgets and screens do not import `db.py` directly — they go through the **controller**. Data flows `db → controller → widget`; user actions flow `widget → controller → db`. Widgets communicate upward via Textual **messages** (`Message` subclasses), not by reaching into parents.
- **Styling:** All styling lives in `tasque.tcss` (Textual CSS). No inline style mutation except for genuinely dynamic state that CSS classes can't express.
- **Schema changes:** Migrations are additive where possible. Each schema change bumps a `user_version` in SQLite and ships a migration step in `db.py`; destructive changes need an explicit migration. Never edit an existing migration after it has shipped.
- **Undo/redo:** All mutating operations route through a single command/undo stack in the controller so undo/redo stays consistent. No widget mutates state out-of-band.

## Testing Rules

- Tests live in `tests/` mirroring `src/tasque/` structure.
- Every new feature ships with unit tests **and** at least one integration test.
- Tests use an in-memory SQLite database (`:memory:`) or a tmp-path file fixture — **never** the dev/user DB.
- Widget/screen behaviour is tested through Textual's async `App.run_test()` pilot harness, asserting on observable state — not private methods.
- Tests describe behaviour, not implementation. Renaming a private function must not break a test.

## Definition of Done

A feature is **Done** in PLAN.md only when:

1. Code is written and merged to the working branch.
2. Tests pass (`uv run pytest`) and coverage hasn't dropped; lint is clean (`uv run ruff check`).
3. PLAN.md is updated (moved from In Progress → Done with the completion date).
4. LEARNINGS.md is updated if anything non-obvious was discovered.
5. If UI: the implementation matches the spec in `docs/ux/`.

## How to Work on This Project

1. Start every new feature with `/clear` to reset context. The project files carry forward.
2. Read `PLAN.md` to find the next backlog item whose dependencies are Done.
3. Follow the `new-feature` skill in `.claude/skills/new-feature/`.
4. Use sub-agents for the right roles — see `.claude/agents/` for who does what.
5. Save UX specs to `docs/ux/<feature>.md` before writing UI code.
6. Append discoveries to `LEARNINGS.md` as you find them.
7. Architect designs are saved to `docs/architecture/feature-<n>.md` and PLAN.md is moved to In Progress before the implementer starts. In-chat design state doesn't count as durable.
