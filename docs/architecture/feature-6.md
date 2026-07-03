# Architecture: Feature #6 — Priority Levels

> Design proposal produced by the architect sub-agent (2026-07-03), built against the shipped
> Feature #5 code (`controller.py`, `db.py`, `models.py`, `widgets/todo_item.py`,
> `widgets/todo_list.py`, `screens/main.py`, `tasque.tcss`), the reserved slots in
> `docs/ux/main-screen.md`, and the seam narrative in `docs/architecture/feature-5.md`.
>
> **Scope:** a `priority` value on each task (none / low / medium / high), a `p`-key cycle that
> persists, colour-coded rendering through the already-reserved `#priority` slot + `.-priority-*`
> CSS, and a priority sort mode. One additive migration (`user_version` 1 → 2).
>
> **Boundary note:** this doc owns the *data model, persistence, control flow, and integration
> seams* only. The **specific visual token** shown in the `#priority` slot — the `(H)/(M)/(L)`
> letter tags used illustratively throughout — is a **researcher decision, not an architect one**,
> and is marked as a placeholder pending `docs/ux/` (see §7). The architecture holds regardless of
> which token the researcher lands on.

---

## Summary
Feature #6 fills in the four seams that Features #2–#5 deliberately left inert: `Todo.priority`
(already a nullable field), the `#priority` Static slot + `.-priority-*` CSS classes in `TodoItem`,
the `PriorityCycleRequested` message + `p` binding on `TodoList`, and `controller.cycle_priority`.
Every write routes through the existing `_apply(Command)` choke-point via a new
`_CyclePriorityCommand`, so Feature #9's undo stack picks up priority changes with zero call-site
edits. Persistence gets one additive migration (`ALTER TABLE todos ADD COLUMN priority INTEGER`,
nullable) and one new single-column setter (`db.set_priority`), mirroring `set_completed`. A
priority **sort mode** is added as view state on `MainScreen` (not controller data), with the actual
`ORDER BY` living in `db.py` to respect the persistence boundary.

Grounding note: the shipped `db.update()` writes only `text` + `completed` — it does **not** touch
`priority`. This design keeps that true (editing text never clobbers priority) and gives priority its
own dedicated setter, exactly as `completed` has `set_completed`. See §4.

---

## Encoding decision — CONFIRM the ascending `{1: low, 2: medium, 3: high}` placeholder

**Decision: confirm, do not override.** The reserved `_PRIORITY_WORDS` map in `todo_item.py`
(shipped as `{3: "high priority", 2: "medium priority", 1: "low priority"}` — the same ascending
encoding the PLAN note describes) is adopted as the real model, promoted to a typed `IntEnum`.

- **Shape: `IntEnum`, stored as `int`, "none" = SQL `NULL` / Python `None`.** Not a string, and not a
  zero-valued `NONE` enum member. Reasons:
  - **Sort comes for free and correct.** Ascending int = ascending urgency, so `ORDER BY priority
    DESC` yields high → medium → low, and SQLite sorts `NULL` last under `DESC` — i.e. "no priority"
    naturally falls to the bottom without a special case. A string encoding
    (`"high"/"medium"/"low"`) would sort lexically wrong (`high < low < medium`) and leak magic
    strings across layers.
  - **`None` stays distinct from "a level."** The model, DB column, and UX all already treat absence
    as a first-class state (`priority is None` → blank slot, per `main-screen.md`). A `NONE = 0`
    member would blur "unset" with "explicitly lowest," and force every `is None` check to become a
    value check. Nullable column + `None` is the honest representation and matches the shipped
    `Todo.priority: int | None` placeholder and `_row_to_todo`'s defensive `col("priority")`.
  - **`IntEnum` (not bare `int`)** gives the cycle/rendering code named members (`Priority.HIGH`)
    while remaining an `int` subclass, so it binds to SQLite as an integer with no adapter (avoids the
    Python-3.12 adapter-deprecation trap noted in LEARNINGS) and `Priority(row_value)` round-trips
    cleanly.
- **Alignment check (all three agree):** the cycle direction `none → low → medium → high → none`
  (PLAN + `main-screen.md` keybindings), the placeholder map's ascending keys, and the "high on top"
  sort all point the same way. No reconciliation is needed — the placeholder was correct; #6 makes it
  live.

> Note: the commented-out example entry in `LEARNINGS.md` ("Priority stored as IntEnum, not string")
> is illustrative boilerplate shipped with the template, **not** a prior decision. This section is the
> real decision, reached independently against the shipped code; the implementer should replace that
> example block with a real dated entry recording it.

```python
# models.py
class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
```

`Todo.priority` annotation tightens from `int | None` to `Priority | None` (frozen dataclass, no other
change). `Todo.new()` is untouched — new tasks are created with `priority=None`.

---

## 1. Module / file plan

**No new files.** Every touch point is an existing reserved seam.

**Modified files**
- `src/tasque/models.py` — add `class Priority(IntEnum)`; retype `Todo.priority` to `Priority | None`;
  add a pure `next_priority(current) -> Priority | None` helper (the cycle transition, kept in the
  pure model layer so both controller and tests use one definition — no DB, no Textual).
- `src/tasque/db.py` — append `_migration_0002_add_priority`; convert `int → Priority` in
  `_row_to_todo`; add `set_priority(todo_id, priority)`; add priority ordering to `list_todos`
  (a `sort` parameter, `ORDER BY` built here). `add()` and `update()` are **unchanged**.
- `src/tasque/controller.py` — implement `cycle_priority` (was `NotImplementedError`); add private
  `_CyclePriorityCommand`; thread `sort` through `list_todos`.
- `src/tasque/widgets/todo_item.py` — render the `#priority` tag in `compose` + `watch_todo`; set the
  correct `.-priority-*` class in `_sync_classes`; retype `_PRIORITY_WORDS` to the enum. The
  accessible-label seam already folds priority in — it simply starts firing.
- `src/tasque/widgets/todo_list.py` — add `Binding("p", "cycle_priority", "Priority", show=True)` and
  `action_cycle_priority` (posts the existing `PriorityCycleRequested`). Optionally add the sort-toggle
  binding (see §3 — recommend `s` on `MainScreen`, not here).
- `src/tasque/screens/main.py` — add `on_todo_list_priority_cycle_requested`; hold the sort-mode view
  state + `s` toggle; thread `sort` into `refresh_todos`.
- `src/tasque/tasque.tcss` — **no change required.** The `.-priority-high/-medium/-low > #priority`
  colour rules already exist (§7 confirms they are complete for #6).

`app.py`: no change. `p` lives on `TodoList` (list-focused), `s` on `MainScreen`.

---

## 2. Priority data model (see the encoding decision above)

`models.py`:

```python
class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


_CYCLE: tuple[Priority | None, ...] = (None, Priority.LOW, Priority.MEDIUM, Priority.HIGH)

def next_priority(current: Priority | None) -> Priority | None:
    """none → low → medium → high → none. Pure; the single source of the cycle order."""
    return _CYCLE[(_CYCLE.index(current) + 1) % len(_CYCLE)]
```

- `next_priority` is a **pure function in the model layer**, not logic buried in the command or the
  widget, so (a) the cycle direction is defined once, (b) it is unit-testable without a DB or a pilot,
  and (c) `todo_item.py`'s render map and this transition can't drift out of agreement.
- `Todo.priority: Priority | None`. Because `Priority` is an `IntEnum`, existing equality/ordering and
  the `int(...)` write path keep working; the only new obligation is converting on read (§4).

---

## 3. Sort policy — explicit architect choice

The acceptance criterion is "list **can** sort by priority" — an available ordering, not a forced
reordering. Design:

- **Default is unchanged.** The resting view stays **creation order** (`ORDER BY id`). Feature #6 must
  not silently re-rank everyone's existing list on upgrade; the default `list_todos()` call returns the
  same order it does today.
- **A `sort` mode is view state on `MainScreen`**, not controller/DB state. SQLite is the source of
  truth for *task data*; the chosen ordering is an ephemeral UI preference, so it lives on the screen
  (`self._sort`), not in the controller (which "holds no long-lived mutable copy") and not persisted.
  `s` toggles it and re-runs `refresh_todos()`.
- **The `ORDER BY` itself lives in `db.py`** (persistence boundary: no SQL outside `db.py`). The
  controller passes a `sort` enum through; `db.list_todos(sort=...)` selects the clause.

**Priority ordering (the explicit choices), in `db.py`:**

```sql
-- TodoSort.PRIORITY
ORDER BY completed ASC, priority DESC NULLS LAST, id ASC
```

1. **`completed ASC` first — done items are demoted below active ones.** *This is the deliberate
   call:* in priority sort, a *completed* HIGH task should **not** sit above an *active* LOW task.
   Interleaving done items purely by priority (dropping this key) is the rejected alternative — it is
   one clause away if the user prefers it, but for a to-do app "still-to-do beats already-done" is the
   right default. (Note this differs from the creation-order view, which interleaves done items in
   place — intentional: the two modes answer different questions.)
2. **`priority DESC NULLS LAST` — high → medium → low → none.** The ascending encoding makes `DESC`
   correct; `NULLS LAST` is explicit (and matches SQLite's native `DESC` null placement) so "no
   priority" sinks under low.
3. **`id ASC` tie-break — stable creation order within a priority band.** Two HIGH tasks keep their
   relative creation order; no shuffling on re-sort.
4. **Filter vs. interleave:** priority sort **interleaves** — it never *hides* done or none-priority
   items. Filtering tasks out of view is a Feature #11 (search/filter) concern, explicitly not #6.

`TodoSort` is a small enum in `db.py` (`CREATED`, `PRIORITY`); the controller re-exports/accepts it so
the screen never imports `db.py`. (Alternatively define it in `models.py` if the controller prefers a
db-free import; either keeps the UI off `db.py`. Recommend `models.py` for symmetry with `Priority`.)

**Cursor preservation across re-sort (integration subtlety, see §5):** toggling sort — and cycling a
priority *while in priority mode* — changes row positions, so the cursor must be re-anchored to the
**same `todo_id`**, not the same index. `refresh_todos()` gains an optional "keep this id highlighted"
argument.

---

## 4. Persistence: migration + dedicated setter

### 4a. Migration (append-only; `user_version` 1 → 2)

```python
def _migration_0002_add_priority(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE todos ADD COLUMN priority INTEGER")  # nullable, no default → NULL

_MIGRATIONS = [
    _migration_0001_create_todos,
    _migration_0002_add_priority,   # appended, never edit 0001
]
```

- **Additive and non-destructive.** Existing rows get `priority = NULL` (= none), which is exactly the
  pre-feature behaviour, so upgrading a v1 DB is a no-op semantically. The migration ladder
  (`_MIGRATIONS[version:]`) runs *only* `0002` on an existing v1 DB and bumps `user_version` to 2 —
  the reopen/skip path from the Feature #3 LEARNINGS entry already covers this.
- **`_row_to_todo` already reads it defensively** (`col("priority")`), so the only mapper change is
  the type conversion:

```python
raw_priority = col("priority")
priority = Priority(raw_priority) if raw_priority is not None else None
```

### 4b. Writing priority — a dedicated setter, mirroring `set_completed`

```python
def set_priority(self, todo_id: int, priority: Priority | None) -> Todo:
    cur = self._conn.execute(
        "UPDATE todos SET priority = ? WHERE id = ?",
        (int(priority) if priority is not None else None, todo_id),
    )
    if cur.rowcount == 0:
        raise TodoNotFoundError(todo_id)
    self._conn.commit()
    return self.get(todo_id)
```

- **Why a setter, not widening `update()`:** the shipped `db.update()` deliberately writes only
  `text` + `completed`. Widening it to also write `priority` would couple the edit-text path to
  priority (risking a stale-priority clobber) and break the clean single-responsibility of the two
  existing setters. `set_completed` is the exact precedent; `set_priority` is its twin. **Trap flagged
  for the implementer:** do **not** add `priority` to `update()`'s `SET` list — text edits must leave
  priority untouched, and cycling goes through `set_priority`.
- **`add()` is unchanged.** New todos insert without a priority column value → `NULL` → none, matching
  `Todo.new(priority=None)`. If a future feature needs to *create* a task with a priority, `add()`'s
  INSERT would widen then — not needed now, noted so it isn't rediscovered.

---

## 5. Controller integration — `cycle_priority` through the `_apply` seam

Mirror the four shipped mutations exactly: build a private command, route through `_apply`, return
`command.result`.

```python
def cycle_priority(self, todo_id: int) -> Todo:
    command = _CyclePriorityCommand(self._db, todo_id)
    self._apply(command)
    assert command.result is not None
    return command.result
```

```python
class _CyclePriorityCommand:
    def __init__(self, db: Database, todo_id: int) -> None:
        self._db = db
        self._todo_id = todo_id
        self._prev: Priority | None = None
        self.result: Todo | None = None

    def execute(self) -> None:
        current = self._db.get(self._todo_id)          # raises TodoNotFoundError if gone
        self._prev = current.priority
        self.result = self._db.set_priority(self._todo_id, next_priority(current.priority))

    def undo(self) -> None:  # pragma: no cover - Feature #9 seam (no public undo yet)
        self._db.set_priority(self._todo_id, self._prev)
```

| Command | `execute()` (stores `self.result`) | `undo()` (Feature #9) |
| --- | --- | --- |
| `_CyclePriorityCommand(db, id)` | `cur = db.get(id)`; record `cur.priority`; `self.result = db.set_priority(id, next_priority(cur.priority))` | `db.set_priority(id, prev)` |

- **Seam stays honest:** `_apply` keeps its `-> None` signature; the result rides on `command.result`.
  Feature #9 changes only `_apply`'s body. The `undo()` body is directionally complete and carries the
  `# pragma: no cover` marker (no public `controller.undo()` until #9), consistent with the other four
  commands — and crucially, `set_priority` is a clean inverse (no new-id problem like `_DeleteCommand`),
  so #9's priority undo is trivial.
- **`list_todos` threads sort:** `def list_todos(self, sort: TodoSort = TodoSort.CREATED) -> list[Todo]:
  return self._db.list_todos(sort=sort)`. Default preserves every existing call site.

---

## 6. MainScreen + TodoList coordination and data flow

**The `p` cycle is the *only* way to set priority — confirmed, no divergence from the shipped flows.**
- **New tasks start with `priority = None` (none).** The InputBar *add* path calls
  `controller.add_todo(text)` → `_AddCommand` → `db.add(Todo.new(text))`; `Todo.new` sets
  `priority=None` and `db.add`'s INSERT omits the `priority` column (→ SQL `NULL`). The add flow is
  **not** widened to take a priority — a task is born with none and gets one only via `p`.
- **Edit mode does not expose priority.** The InputBar *edit* path (`e` → `edit_todo`) changes **text
  only** (`_EditCommand` → `db.update`, which writes `text`/`completed` and, per §4b, is deliberately
  **not** widened to write `priority`). So editing a task's text never shows, changes, or clobbers its
  priority.
- **Net:** priority is set/changed **exclusively** through the `p` cycle key on the focused row. This
  keeps the single-field InputBar single-field (consistent with the `Tab`-is-inert convention in
  `main-screen.md`) and defers any inline priority-in-the-add-form idea to a future multi-field bar.

**TodoList — new binding + action** (posts the existing `PriorityCycleRequested`, no-op if empty):
```python
Binding("p", "cycle_priority", "Priority", show=True)

def action_cycle_priority(self) -> None:
    todo_id = self.current_todo_id
    if todo_id is not None:
        self.post_message(self.PriorityCycleRequested(todo_id))
```

**MainScreen — cycle handler:**
```python
def on_todo_list_priority_cycle_requested(self, event: TodoList.PriorityCycleRequested) -> None:
    event.stop()
    try:
        updated = self._controller.cycle_priority(event.todo_id)
    except TasqueError as exc:
        self.app.notify(f"Error: {exc}", severity="error")
        return
    if self._sort is TodoSort.PRIORITY:
        # priority changed → row must re-sort; rebuild, keep the cursor on this task
        await self.refresh_todos(keep_id=updated.id)
    else:
        self.query_one(TodoList).update_todo(updated)   # position unchanged → in-place re-render
```

- **In-place vs. rebuild is sort-mode dependent** — the key integration subtlety. In creation order a
  cycle doesn't move the row, so the shipped `update_todo` single-row re-render (cursor preserved)
  suffices and is cheap. In priority mode the row can jump, so a full `refresh_todos` is required, and
  the cursor is re-anchored by `todo_id` (not index) via a new `keep_id` argument.
- **`TasqueError` guard** matches the four existing handlers (row vanished mid-cycle → error toast, no
  crash).

**Toggle-completion must become sort-aware (gap surfaced by the researcher, `priority.md` §Edge
cases / OQ4).** The shipped Feature #5 `on_todo_list_toggle_requested` handler does an in-place
`update_todo(updated)` — correct in creation order (the row doesn't move). But in **priority sort**,
completing/uncompleting a task moves it between the active and done bands, so an in-place re-render
would leave the list mis-ordered. The handler must branch on `self._sort`, like the cycle handler:
```python
def on_todo_list_toggle_requested(self, event) -> None:
    event.stop()
    todo_list = self.query_one(TodoList)
    index = todo_list.index                      # capture BEFORE the re-sort
    try:
        updated = self._controller.toggle_todo(event.todo_id)
    except TasqueError as exc:
        self.app.notify(f"Error: {exc}", severity="error"); return
    if self._sort is TodoSort.PRIORITY:
        await self.refresh_todos()               # re-sort; then land by INDEX, not id
        tl = self.query_one(TodoList)
        if len(tl) > 0:
            tl.index = min(index, len(tl) - 1)   # stay on position → next active slides in
    else:
        todo_list.update_todo(updated)           # creation order: in-place, cursor preserved
    self._update_counts(self._controller.list_todos())
```
**Cursor rule is deliberately different from the cycle handler.** The cycle handler uses
`keep_id` — the cursor *follows the task* it just re-prioritised (you're still working with that
task). The toggle handler uses **`keep_id`-free, index-based landing** — the cursor **stays on
position**, so the just-completed task slides down to the done band and the **next active task takes
its place** (user decision, 2026-07-03). This mirrors the post-delete cursor rule from
`feature-5.md` §5 ("land on the next row"): completing a task means "move on to the next thing," not
"follow it into the done pile." (Implementer note: the completing case slides the row *down*, so the
old index now holds the next active task; the uncompleting case slides *up* into the active band —
index-clamp still lands on a sensible neighbouring row. Don't reach for `keep_id` here.)

**Sort toggle (`s`) on MainScreen:**
```python
Binding("s", "cycle_sort", "Sort", show=True)   # add to MainScreen.BINDINGS

def action_cycle_sort(self) -> None:
    self._sort = TodoSort.PRIORITY if self._sort is TodoSort.CREATED else TodoSort.CREATED
    keep = self.query_one(TodoList).current_todo_id
    await self.refresh_todos(keep_id=keep)
    self.app.notify(f"Sorted by {self._sort.name.lower()}", severity="information")
```
Sort **is** the one place the cursor follows the task by `keep_id` (you asked to re-sort, and staying
on the same task across the reorder is the least disorienting).

**Persistent sort-mode indicator (`priority.md` §`s` / OQ2, user-confirmed):** the toast vanishes, so
the active mode is echoed in the panel **border-title** — but only when non-default, so creation order
stays clutter-free. `_update_counts` gains a suffix:
```python
title = f"Inbox · {active} active · {done} done"
if self._sort is TodoSort.PRIORITY:
    title += " · by priority"
self.query_one("#list-panel", Container).border_title = title
```
This extends `main-screen.md`'s border-title format (reconciled there); the `· by priority` suffix
right-truncates first on a narrow terminal (a soft cue the toast already delivered).

**`refresh_todos` gains `keep_id`:**
```python
async def refresh_todos(self, *, keep_id: int | None = None) -> None:
    todos = self._controller.list_todos(sort=self._sort)
    ...
    await todo_list.set_todos(todos)
    if keep_id is not None:
        todo_list.highlight_id(keep_id)   # small helper: index of the TodoItem with that id, else 0
    ...
```
`highlight_id` is a thin `TodoList` helper (find the `TodoItem` whose `todo_id == keep_id`, set
`index`; fall back to 0). This is the one small public-API addition to `TodoList`, and it's the
honest fix for "cursor must follow the task, not the slot" across a re-sort.

**Footer:** `p Priority` already appears in the `main-screen.md` wireframe/footer; `show=True` on the
`p` binding surfaces it. `s Sort` is a new footer hint (the wireframe reserved a `s?` sort key in Open
Question #2 — this realises it).

---

## 7. TodoItem rendering + CSS

> **⚠ Placeholder pending the researcher pass.** The specific glyph rendered in the `#priority`
> slot — `(H)/(M)/(L)` letter tags below — is **not an architect decision**. It is carried here only
> so the render wiring is concrete and testable. The **researcher** owns the final visual token and
> may confirm the letter tags or propose something better (e.g. coloured icons, pips `●●●`, or a
> colour+word pairing), saved to `docs/ux/` before UI code is written. Whatever they choose, the
> architecture is unaffected: it must (a) fit the `#priority` slot (currently `width: 4` — the
> researcher may adjust that width), (b) pair colour with a non-colour signal (Principle 4:
> colour-blind safety — so a bare colour swatch alone is out), and (c) map cleanly from
> `Priority | None`. The `_PRIORITY_TAGS` map, the slot width, and any `.tcss` colour tweaks are the
> seams the implementer wires to whatever the researcher specs — treat the values below as the
> *default fallback* if the researcher confirms the letter tags.

**Researcher outcome (`docs/ux/priority.md`, 2026-07-03):** the letter tags `(H)/(M)/(L)` and the
`width: 4` slot are **confirmed** as the token; render `(H) `/`(M) `/`(L) `/four-spaces into
`#priority`. Two CSS deltas were approved by the user and are now the spec — so §1's "no `.tcss`
change" is **superseded**: the stylesheet does change, in exactly two small ways:

1. **Low colour `$primary → $text-muted`** (user-confirmed): the severity ramp reads red → amber →
   calm; low recedes rather than competing on the accent hue.
   ```
   TodoItem.-priority-high   > #priority { color: $error; }        /* unchanged */
   TodoItem.-priority-medium > #priority { color: $warning; }      /* unchanged */
   TodoItem.-priority-low    > #priority { color: $text-muted; }   /* was $primary */
   ```
   This also edits `main-screen.md`'s Color Scheme table (reconciled in the same change) so the specs
   don't drift.
2. **Add a done-dims-priority rule** (correctness fix — the shipped `.-done` rules cover
   `#title`/`#checkbox`/`#meta` but miss `#priority`, though `main-screen.md` §Completed says priority
   dims too):
   ```
   TodoItem.-done > #priority { color: $text-disabled; }
   ```
   **Placement is load-bearing:** this has equal specificity to the `.-priority-*` rules (type + one
   class + id), so it **must appear *after* the `.-priority-*` block** in `tasque.tcss` — otherwise a
   done high-priority tag stays bright `$error` instead of dimming.

Colour is never the sole signal — the letter tag carries meaning in monochrome (Principle 4); priority
tints the *tag* only, so it composes with the cursor highlight and `-done` dim. The `(!)` overdue echo
is **Feature #7**, not #6 — #6 renders only the priority token or blank.

**`todo_item.py` changes** (activating the reserved slot):
```python
_PRIORITY_TAGS = {Priority.HIGH: "(H)", Priority.MEDIUM: "(M)", Priority.LOW: "(L)"}
_PRIORITY_CLASS = {Priority.HIGH: "-priority-high",
                   Priority.MEDIUM: "-priority-medium",
                   Priority.LOW: "-priority-low"}
_PRIORITY_WORDS = {Priority.HIGH: "high priority",
                   Priority.MEDIUM: "medium priority",
                   Priority.LOW: "low priority"}   # retyped from int keys; same mapping
```

- **`compose`:** render the tag into `#priority` from the initial todo:
  `Static(_priority_tag(t.priority), id="priority", markup=False)` where `_priority_tag` returns
  `"(H) "`/`"(M) "`/`"(L) "` (padded to the 4-wide slot) or `"    "` for none. `markup=False` already
  set — parentheses aren't markup, but keep it consistent with the LEARNINGS bracket-stripping gotcha.
- **`watch_todo`:** add one line alongside the checkbox/title updates —
  `self.query_one("#priority", Static).update(_priority_tag(new_todo.priority))`.
- **`_sync_classes`:** replace the unconditional `remove_class(...)` with set-exactly-one:
  ```python
  self.remove_class("-priority-high", "-priority-medium", "-priority-low")
  cls = _PRIORITY_CLASS.get(todo.priority)
  if cls:
      self.add_class(cls)
  ```
  (`-overdue`/`-due-today` stay removed — still #7.)
- **Accessible label** already folds priority via `_PRIORITY_WORDS.get(todo.priority)`; with real
  priorities it now emits e.g. `"incomplete, high priority, Finish the quarterly report"`. No new code
  in the label path — the seam simply activates.

---

## 8. State-guard (unchanged mechanism)

`p` is a **`TodoList` binding**, so it fires only while the list holds focus — when the `InputBar` is
open (list blurred, keys consumed by the `Input`) or the delete `ModalScreen` is up (input trapped),
`p` cannot fire behind them. `s` is a `MainScreen` binding; like `a`, it is reachable from the empty
state, so it is naturally a no-op when there's nothing to sort (list empty) and is shadowed by the
modal. No new guarding logic — this is the structural state-guard from `feature-5.md` §6, reused.

---

## 9. Testing seams

**`db.py` (`tests/test_db.py`):**
- Migration: fresh DB reaches `schema_version == 2` and has a `priority` column; a hand-built v1 DB,
  reopened, migrates to 2 with existing rows `priority IS NULL` (data preserved).
- `set_priority` round-trips each level and `None`; raises `TodoNotFoundError` for a missing id.
- `list_todos(sort=PRIORITY)` order: high→med→low→none; `NULL` last; `id ASC` tie-break within a band;
  completed items demoted below active regardless of priority. `sort=CREATED` (default) unchanged.
- `update()` (text edit) leaves `priority` untouched (guards the "don't widen update" decision).

**`controller.py` (`tests/test_controller.py`):**
- Replace `cycle_priority_raises_not_implemented` with: cycling from none returns LOW, then MEDIUM,
  then HIGH, then back to `None` (four calls returns to start); each returns the updated `Todo`;
  raises `TodoNotFoundError` for a missing id (asserts the `_apply` path propagates).
- `list_todos(sort=PRIORITY)` passthrough returns db order.
- `next_priority` pure-function table test (none→low→med→high→none) in `tests/test_models.py`.

**Pilot (`tests/widgets/test_todo_item.py`, `tests/screens/test_main.py`):**
- Press `p` on a row → `#priority` renders `(L)`, row gains `-priority-low`; press again → `(M)` /
  `-priority-medium`; four presses → blank slot, no `-priority-*` class. Assert on rendered `#priority`
  text and the class set (observable state), never private methods.
- In creation-order mode, cycling does **not** move the row (same `index`, cursor preserved).
- Sort toggle `s`: with mixed priorities, rows reorder high→…→none with done demoted; the cursor stays
  on the **same task** (assert `current_todo_id` unchanged across the toggle), proving `keep_id`.
- Cycling while in priority mode re-sorts and keeps the cursor on the cycled task.
- Accessible label of a HIGH row includes `"high priority"`.
- Failure path: `p` on a row whose id was deleted out from under the screen → error toast, no crash.

All pilot assertions query via `app.screen` (LEARNINGS: `App.query` doesn't traverse pushed screens)
and use a seeded `:memory:` controller.

---

## 10. Migration / schema impact — summary

| | |
| --- | --- |
| `user_version` | **1 → 2** (append `_migration_0002_add_priority`) |
| DDL | `ALTER TABLE todos ADD COLUMN priority INTEGER` (nullable, defaults `NULL` = none) |
| Destructive? | No. Additive; existing rows unaffected (`priority = NULL`). |
| Mapper | `_row_to_todo` converts `int → Priority` (else `None`); already reads the column defensively. |
| Write path | new `db.set_priority` (twin of `set_completed`); `add()`/`update()` untouched. |

---

## Alternatives Considered
- **`priority` as a string (`"high"/…`):** rejected — sorts lexically wrong, leaks magic strings,
  needs a mapping to sort anyway. `IntEnum` sorts correctly for free.
- **A `Priority.NONE = 0` member instead of `None`:** rejected — conflates "unset" with "lowest,"
  forces value-checks in place of the honest `is None`, and diverges from the shipped nullable field /
  `col("priority")` / "blank slot when None" UX.
- **Widen `db.update()` to also write `priority`:** rejected — couples the edit-text path to priority
  (stale-clobber risk) and breaks the single-column-setter symmetry. `set_priority` mirrors
  `set_completed`.
- **Sort mode stored in the DB / on the controller:** rejected — it's an ephemeral *view* preference,
  not task data; SQLite is the source of truth for data only. It lives on `MainScreen`. (If
  session-persistence of the chosen sort is ever wanted, that's a settings concern, not task schema.)
- **Priority sort ignoring completion (pure `priority DESC`):** rejected as the default — a *done* HIGH
  task above an *active* LOW task is wrong for a to-do app. Kept as a one-clause escape hatch; the
  `completed ASC` primary key is the deliberate choice (§3).
- **`update_todo` in-place after every cycle (never rebuild):** rejected in priority mode — the row
  can change rank, so the list would show a stale order; rebuild-with-`keep_id` is required there. In
  creation mode in-place is kept (cheaper, position is stable).
- **Put the cycle transition in the command/widget:** rejected — a pure `next_priority` in `models.py`
  defines the order once, is DB-free testable, and keeps the render map and transition from drifting.

---

## Resolved decisions (by the user, 2026-07-03)
All three open questions were resolved in favour of the recommended options; §3 and §6 above already
reflect them and are now settled, not tentative:
1. **Sort-toggle key + scope:** `s` on `MainScreen` cycles CREATED ↔ PRIORITY. **Creation order stays
   the default view** — #6 does not reorder existing lists on upgrade.
2. **Done-item placement in priority sort:** **demote done below active** — `ORDER BY completed ASC,
   priority DESC NULLS LAST, id ASC`. A completed HIGH task does not rank above an active one. (Pure
   priority ordering was rejected.)
3. **`s` footer visibility:** **`show=True`** — `s Sort` appears in the footer next to `p Priority`.
