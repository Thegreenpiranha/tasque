# LEARNINGS.md

A running journal of discoveries, gotchas, and design decisions made during development. Read by sub-agents before starting work so the same problem isn't solved twice.

> Empty at the start of a project. Grows as you build.

---

## Format

Each entry is dated and tagged. Keep entries short — one paragraph or a few bullets. The point is searchable signal, not a diary.

```
### YYYY-MM-DD — [tag] short title

What we discovered. What we tried. What we settled on. Why.
```

Tags suggested: `[gotcha]` `[decision]` `[perf]` `[ux]` `[security]` `[dep]` `[migration]` `[testing]`

---

## Entries

### 2026-06-29 — [decision] Migrations keyed on `PRAGMA user_version`, append-only

`db.py` holds an ordered `_MIGRATIONS` list; `user_version` is the count applied. On open we run
`_MIGRATIONS[version:]` and bump `user_version` after each. The v1 `todos` table is intentionally
minimal (`id`, `text`, `completed`, `created_at`) — `priority`/`due_date`/`category_id`/`list_id`
arrive via their *own* additive migrations (Features #6/#7/#8/#10), which is what keeps those
features' "adds a migration" criteria meaningful. `_row_to_todo` reads columns defensively
(`name in row.keys()`) so the same mapper works before and after each column lands. Never edit a
shipped migration; only append.

### 2026-06-29 — [decision] `Database` class over module-level functions

CLAUDE.md says "go through db.py's functions," but a class wins here: a `:memory:` DB only lives as
long as its connection, so one long-lived connection on an instance is required (open/close-per-call
would hand back an empty DB every time). It also lets tests inject `":memory:"`/tmp-path with no
global to monkeypatch. The methods are the public surface the rule asks for. `delete` returns the
deleted `Todo` so Feature #9 (undo) can restore it without a re-read.

### 2026-06-29 — [gotcha] Textual 8.x: `Static.renderable` is gone

The smoke test asserted on `Static.renderable` — `AttributeError` on Textual 8.2.7. Use
`Static.render()` (returns the visual; `str()` it to assert on text content).

### 2026-06-29 — [gotcha] Python 3.12 deprecates sqlite3 datetime adapters

The default `sqlite3` date/datetime adapters are deprecated in 3.12. We store `created_at` as an
explicit ISO-8601 string and convert at the `db.py` boundary (`.isoformat()` on write,
`datetime.fromisoformat()` in `_row_to_todo`) rather than relying on `detect_types`. Same pattern
will apply to `due_date` (stored as ISO date string) when Feature #7 lands.

### 2026-06-29 — [dep] Toolchain: `uv` provisions Python 3.12 itself

Dev box had only Python 3.13 and no `uv`/`ruff`. Installed `uv` via `pip install --user uv`
(invoke as `python -m uv`). Because `pyproject.toml` pins `requires-python = ">=3.12,<3.13"`,
`uv run`/`uv sync` downloads and uses CPython 3.12 automatically — no manual 3.12 install needed.
`ruff` comes in as a dev dependency. Coverage baseline established at 96% via `pytest-cov`.

### 2026-07-01 — [gotcha] Rich Console Markup silently strips `[x]` and similar bracket tokens

Textual `Static` widgets have `markup=True` by default, which delegates to Rich's Console Markup
parser. Strings like `"[x]"` and `"(H)"` are parsed as unknown markup tags and **silently
stripped** — `str(Static("[x]").render())` returns `""`. Fix: pass `markup=False` on all
`Static` widgets that display literal ASCII symbols (checkbox glyphs, priority tags, cursor
`▸`). The watcher's `update()` call inherits `_render_markup` from `__init__`, so setting it
once is sufficient.

### 2026-07-01 — [gotcha] `App.query()` does not traverse pushed screens

In Textual 8.x, `App.query_one(SomeWidget)` and `App.query(SomeWidget)` search the app's
**own** compose subtree (the default screen), not screens pushed via `push_screen()`. In tests
that push a `MainScreen`, always query from `app.screen` (the active screen) instead:
`app.screen.query_one(EmptyState)` not `app.query_one(EmptyState)`. The `app.screen` property
correctly returns the topmost pushed screen.

### 2026-07-01 — [gotcha] Textual CSS `text-style: strikethrough` is invalid; use `strike`

Textual's CSS engine accepts only short-form text-style flags. `strikethrough` causes a
`StylesheetParseError`; the correct value is `strike` (matching Rich's canonical name).
Permitted values: `bold`, `dim`, `italic`, `underline` (`u`), `strike`, `overline` (`o`),
`blink`, `reverse`, `none`.

### 2026-07-01 — [decision] `TodoItem` reactive `todo` uses `init=False` to avoid watcher before compose

Setting `todo: reactive[Todo | None] = reactive(None, init=False)` prevents Textual from calling
`watch_todo(None)` during mount before `compose()` has created child widgets. The `on_mount`
hook sets `self.todo = self._initial_todo` once children exist, which triggers `watch_todo`
correctly. This pattern (store initial data in `_initial_todo`, compose from it directly, then
set the reactive in `on_mount`) is the standard way to initialize reactive-driven children.

### 2026-07-01 — [dep] platformdirs provides cross-platform `%LOCALAPPDATA%\Tasque` on Windows

`user_data_dir("Tasque", appauthor=False)` returns `%LOCALAPPDATA%\Tasque` on Windows, the
conventional location for per-user app data. `appauthor=False` omits the extra author subfolder
that platformdirs would otherwise add. Tests always inject a `controller=` to bypass disk I/O.

### 2026-07-01 — [ux] Delete-confirmation copy deliberately defers the undo hint to Feature #9

The Feature #5 delete-confirmation dialog (`docs/ux/delete-confirmation.md`) and its success toast
intentionally use **neutral wording** — no "permanently", and *no* "can be undone / press `u` to
undo" claim — because undo does not exist until Feature #9. `db.delete()` already returns the
deleted `Todo` (the undo seam), so the copy must not over-promise permanence either. **Action for
Feature #9:** when the undo/redo stack lands, revisit the delete flow and add the `undo with u`
hint to the success toast (and any equivalent copy), so the promise appears exactly when it becomes
true. This entry is the reminder that the wording is provisional by design, not an oversight.

### 2026-07-01 — [decision] Canonical app-wide `Tab` convention lives in `main-screen.md`

`Tab` behaviour was drifting across specs (main-screen said "moves focus between list and InputBar",
input-bar said "same as Esc" in one place and "no-op" in another). Resolved to a single canonical
rule documented in `main-screen.md § Accessibility & Degradation`: `Tab`/`Shift+Tab` cycles focus
**only among controls within the currently active surface** and never leaves it — in the
delete-confirm modal it moves `Cancel`↔`Delete`; in the single-field `InputBar` it is **inert**
(does nothing, does *not* close the bar — `Esc` does that). Other specs defer to that section rather
than restating it. If a future multi-field add form lands, `Tab` gains meaning inside the `InputBar`
surface only.

<!--
Example entries (delete these once you have real ones):

### 2026-01-15 — [gotcha] Textual reactive props don't fire on first mount

Setting a reactive property in `__init__` doesn't trigger the watcher. Has to be set
in `on_mount` if you want the watch_* method to run. Cost an afternoon.

### 2026-01-18 — [decision] Priority stored as IntEnum, not string

Considered string ("high"/"medium"/"low") for readability vs IntEnum for sorting.
Settled on IntEnum — sorting is the common case and converting to display label
is one line. Magic strings would have leaked through the codebase.

### 2026-01-22 — [ux] Modal close returns focus to last list item, not first

The default Textual modal behaviour returns focus to the first focusable widget.
Users found this disorienting after editing item 47 in a long list. Override
`on_unmount` on the modal to push focus back to `self.previous_focused`.
-->
