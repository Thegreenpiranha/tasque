# Architecture: Feature #7 — Due Dates & Overdue Highlighting

> Design proposal produced by the architect sub-agent (2026-07-03), built against the shipped
> Feature #6 code (`models.py`, `db.py`, `controller.py`, `widgets/todo_item.py`,
> `widgets/todo_list.py`, `widgets/input_bar.py`, `screens/main.py`, `tasque.tcss`), the reserved
> slots in `docs/ux/main-screen.md`, and `docs/architecture/feature-6.md`.
>
> **Scope:** a `due_date` on each task (a calendar day, nullable), a keyboard flow to set/clear it
> via the docked `InputBar`, overdue / due-today highlighting through the already-reserved `#meta`
> slot + `.-overdue` / `.-due-today` CSS, and a **by-due sort mode**. One additive migration
> (`user_version` 2 → 3).
>
> **Boundary / honesty note — there is no "reserved due-date formatter."** The prompt refers to a
> "reserved due-date formatter from feature-6.md"; for the record, **no such function exists**.
> What Features #2–#6 actually reserved for #7 is: (a) the `Todo.due_date: date | None` field
> (`models.py`), (b) the `#meta` `Horizontal` containing an empty `#due` `Static`
> (`todo_item.py`), (c) the `.-overdue`/`.-due-today` CSS classes and the `_row_to_todo`
> conversion `date.fromisoformat(due_raw)` (both already in `db.py`/`tasque.tcss`), and (d) the
> `_priority_tag` function as a *pattern* to mirror. This doc **introduces** the due formatter
> (`_due_display`) as a fresh architect decision; the exact display **strings** (`OVERDUE 06-20`,
> `due today`, `06-30`) follow `main-screen.md`'s Open Question #4 assumption and remain a
> **researcher decision** (`docs/ux/due-dates.md`) — see §8. (Per the LEARNINGS 2026-07-02
> forward-notes rule: I record what was actually reserved, not a decision that was never made.)

---

## Summary

Feature #7 fills the last inert seam left by #2–#6. The heavy lifting is already done by prior
features: `Todo.due_date` is a typed field, `_row_to_todo` already parses the ISO string into a
`date`, and the `.-overdue`/`.-due-today`/`.-done > #meta` rules already ship in `tasque.tcss`.
What #7 adds is the **write path** (one additive migration + a `set_due_date` setter mirroring
`set_priority`), a **pure due-classification** helper in `models.py` (`due_state`, testable with a
fixed "now"), a **set/clear input flow** that reuses the docked `InputBar` via a new `"due"` mode,
**rendering** into the reserved `#due` slot, and a **by-due sort** added to the existing `TodoSort`
three-way cycle. Every write routes through the existing `_apply(Command)` choke-point via a new
`_SetDueDateCommand`, so Feature #9's undo stack picks up due-date changes with zero call-site
edits — and unlike `_DeleteCommand`, the inverse is clean (`set_due_date(id, prev)`), so #9's
due-date undo is trivial.

Grounding note: the shipped `db.update()` writes only `text` + `completed` — not `priority`, and
(this design) **not `due_date`**. Due dates get their own dedicated setter, exactly as `completed`
and `priority` do. Editing text never clobbers a due date. See §5.

---

## Data model decision — CONFIRM the shipped `due_date: date | None`

**Decision: confirm, do not change.** `models.py` already ships `due_date: date | None` on the
frozen `Todo` dataclass. This is the right shape and #7 adopts it as-is.

- **`date`, not `datetime`.** A to-do is due on a *calendar day* ("finish the report by July 5"),
  not at an instant. Modelling it as a `datetime` would invite a time-of-day and a timezone that
  the domain doesn't have, and would make "overdue" ambiguous (overdue at 00:00? 23:59? in which
  zone?). A bare `date` makes "overdue" exactly "the civil day has passed" — see §3.
- **`Optional` (`date | None`).** Absence is first-class: most tasks have no due date. `None` = SQL
  `NULL` = "no due date," rendered as a blank slot — identical in spirit to how `priority is None`
  is handled (`feature-6.md` encoding decision). There is no sentinel date for "none."
- **`Todo.new()` is untouched** — new tasks are born with `due_date=None` and acquire one only via
  the explicit set flow (§4). `add()`'s INSERT continues to omit the column → `NULL`.

No model *field* change is needed. #7 only **adds pure helpers** next to `next_priority`
(`parse_due_date`, `due_state`, `DueState`, `DueDateParseError`) and one enum member (`TodoSort.DUE`).

---

## 1. Module / file plan

**No new files.** Every touch point is an existing reserved seam.

**Modified files**
- `src/tasque/models.py` — add `DueDateParseError`, `DueState` enum, pure `parse_due_date(text, *,
  today)`, pure `due_state(due, today)`; add `TodoSort.DUE`. `Todo` unchanged.
- `src/tasque/db.py` — append `_migration_0003_add_due_date`; add `set_due_date(todo_id, due)`; add
  the `TodoSort.DUE` `ORDER BY` branch to `list_todos`. `_row_to_todo` is **already** correct
  (`date.fromisoformat`); `add()`/`update()` untouched.
- `src/tasque/controller.py` — implement `set_due_date`; add private `_SetDueDateCommand`; re-export
  `parse_due_date` + `DueDateParseError` (so the screen imports them from the controller, not
  `models.py`/`db.py`).
- `src/tasque/widgets/todo_item.py` — render `#due` from a new `_due_display`; set `-overdue`/
  `-due-today` in `_sync_classes` (gated on `not completed`); fold the due word into
  `accessible_label`.
- `src/tasque/widgets/input_bar.py` — add a third `"due"` mode (border-title word, `submit_due`
  binding + footer label, `open_due`, empty-is-valid submit, public `flash_invalid`).
- `src/tasque/widgets/todo_list.py` — add the due-edit binding + `DueDateEditRequested` message +
  `action_edit_due`.
- `src/tasque/screens/main.py` — add `on_todo_list_due_date_edit_requested`; handle `"due"` in
  `on_input_bar_submitted`; make the sort cycle three-way and generalise the toggle-handler branch;
  add the `· by due` border-title suffix.
- `src/tasque/tasque.tcss` — **no change required.** The `.-overdue > #meta` / `.-due-today > #meta`
  / `.-done > #meta` rules already exist (§8 confirms they are complete for #7).

`app.py`: no change.

---

## 2. Storage format & timezone

### 2a. Storage format — ISO 8601 date **text** (already dictated by the shipped mapper)

**Decision: ISO 8601 date string `YYYY-MM-DD` in a nullable `TEXT` column.** This is not a free
choice — `_row_to_todo` already ships `due_date=date.fromisoformat(due_raw) if due_raw else None`,
so the read side already expects ISO text. #7's setter matches it with `due.isoformat()` on write.

- **Not a Unix timestamp.** A timestamp encodes an instant on a timeline; `due_date` is a civil day
  with no time. A timestamp would force an arbitrary time-of-day and reintroduce the timezone
  question. ISO text has none of that.
- **ISO text sorts chronologically as a plain string.** `YYYY-MM-DD` is lexicographically ordered
  the same as chronologically, so `ORDER BY due_date ASC` in `db.py` gives earliest-first with **no
  conversion** (§9). This is the same reasoning that made `IntEnum` free-to-sort for priority.
- **Consistent with `created_at`.** The project already stores dates/datetimes as explicit ISO
  strings and converts at the `db.py` boundary, deliberately avoiding the Python-3.12 `sqlite3`
  adapter-deprecation trap (LEARNINGS 2026-06-29). `due_date` follows the identical pattern —
  `.isoformat()` on write, `date.fromisoformat()` on read, both confined to `db.py`.

### 2b. Timezone — **naive local civil date, no timezone stored**

**Decision: store no timezone; interpret and compare against the user's local calendar day.**

- Because `due_date` is a `date` (no time), there is nothing to attach a zone to. `2026-07-05` means
  "July 5 in the user's own calendar," full stop.
- "Overdue" is evaluated at **render time** against `date.today()` (the local civil date), which
  rolls over at local midnight. This is exactly the "past-midnight-in-the-user's-tz" definition the
  PLAN asks for, and it needs no `tzinfo`, no UTC conversion, and no DST handling.
- **Rejected — store/compare in UTC.** A task due "today" would flip to "overdue" at 8 p.m. for a
  user in UTC−4 (when UTC crosses midnight), which is wrong for a personal, single-machine app.
  Local civil comparison is the correct model for a to-do due *on a day*.
- **Testability:** the comparison lives in a pure `due_state(due, today)` (§3) that takes `today`
  as an argument, so overdue detection is unit-tested with a **fixed** `today` (satisfying the
  acceptance criterion) while the widget passes the real `date.today()` at render.

---

## 3. Overdue definition & the pure `due_state` classifier

`models.py` (pure — no DB, no Textual, mirrors `next_priority`):

```python
class DueState(Enum):
    NONE = "none"
    OVERDUE = "overdue"
    TODAY = "today"
    FUTURE = "future"


def due_state(due: date | None, today: date) -> DueState:
    """Classify a due date relative to `today` (the local civil date).

    Pure and clock-free: `today` is injected, so overdue detection is testable
    with a fixed 'now'. Completion is NOT considered here — the widget gates the
    escalation off on done rows (overdue never shows on a completed task).
    """
    if due is None:
        return DueState.NONE
    if due < today:
        return DueState.OVERDUE
    if due == today:
        return DueState.TODAY
    return DueState.FUTURE
```

**Overdue definition (explicit):**

| Condition | State | Visual (see §8) |
| --- | --- | --- |
| `due is None` | `NONE` | blank `#due` slot, no class |
| `due < today` **and not completed** | `OVERDUE` | `-overdue` → `OVERDUE MM-DD`, `$error` bold |
| `due == today` **and not completed** | `TODAY` | `-due-today` → `due today`, `$warning` |
| `due > today` | `FUTURE` | plain `MM-DD`, muted (default `#meta`) |
| **completed** (any due) | — | escalation suppressed; `#due` shows `──` (dimmed) |

- **`< today` = strictly before the current civil day.** Yesterday and earlier are overdue; today is
  *due today*, not overdue. This matches `main-screen.md` §States (`OVERDUE` vs `due today`).
- **Completion suppresses escalation.** `main-screen.md` §Completed and §Overdue both state overdue
  never applies to a `-done` row. The classifier stays completion-agnostic (single responsibility);
  the **widget** applies `OVERDUE`/`TODAY` classes only when `not todo.completed` (§8). This is why
  there is **no CSS source-order landmine** here (contrast the priority done-dim, LEARNINGS
  2026-07-03): `-done` and `-overdue` can never co-occur on one row, so `.-done > #meta` and
  `.-overdue > #meta` never fight for the tie.

---

## 4. Input flow — reuse the docked `InputBar` via a new `"due"` mode

**Decision: extend the existing `InputBar` with a third mode `"due"`, opened by a row-scoped
binding; a modal date-picker is rejected as out-of-scope for #7.**

Why the `InputBar`, not a modal calendar picker or an inline-in-add field:

- **It is the app's established text-entry surface.** The `InputBar` already docks below the list,
  focuses cleanly (an in-row `Input` can't — `ListView.can_focus_children=False`, LEARNINGS
  2026-07-01), and drives add/edit through the same `mode` reactive + `check_action` footer swap.
  A due date is short free text (a date string); it fits the single-field bar exactly.
- **A modal calendar-grid picker is nicer but far heavier** — a new `ModalScreen`, grid navigation,
  its own UX spec — and the researcher hasn't specced it. Deferred as a possible future enhancement,
  not #7 (see Alternatives). #7 ships the keyboard-first text flow.
- **Not inline in the add form.** The add `InputBar` stays single-field (the `Tab`-is-inert
  convention, `main-screen.md` §Accessibility). A task is born with no due date and gets one via the
  explicit set flow — symmetric with how priority is `p`-only, never part of add/edit.

**The flow (mirrors `e` → edit exactly):**

1. `D` on the focused row (a `TodoList` binding, like `e`/`p`) posts `DueDateEditRequested(todo_id)`.
2. `MainScreen.on_todo_list_due_date_edit_requested` fetches the todo (via `controller.get_todo`,
   like edit does for pre-fill), and calls `InputBar.open_due(id, prefill)` where `prefill` is the
   current due date's ISO string (`"2026-07-05"`) or `""` if none.
3. The user edits the field and presses **Enter**:
   - **non-empty** → parsed by `parse_due_date` (§4a); on success `controller.set_due_date(id, due)`;
     on parse failure the bar pulses `-invalid` and stays open (input preserved).
   - **empty** → **clear** the due date (`set_due_date(id, None)`). Empty is *valid* in `"due"` mode
     (unlike add, where empty pulses invalid). This is the set/clear affordance in one field:
     type a date to set, blank the field to clear.
4. **Esc** cancels (closes the bar, no change) — same as edit.

**Binding key — `D` (RESOLVED, user 2026-07-03).** The natural mnemonic `d` is taken by Delete, so
the due key is its sibling **`D` (Shift+D)**: it reads as *attribute* vs *action* on the same row,
the shift-modified form as "the considered form," and a fat-finger recovers with `Esc`. Footer grows
to:

```
a Add · ␣ Toggle · e Edit · d Delete · p Priority · D Due · s Sort · ? Help · q Quit
```

(The Textual `Footer` elides trailing hints on a narrow terminal; the due hint is not load-bearing.)

### 4a. Parsing — a small, pure, testable grammar in `models.py`

```python
class DueDateParseError(ValueError):
    """Raised when a user-entered due-date string can't be parsed."""


def parse_due_date(text: str, *, today: date) -> date:
    """Parse a due-date string into a date. Raises DueDateParseError on junk.

    Accepts (case-insensitive): ISO `YYYY-MM-DD`, `today`, `tomorrow`, and
    relative `+N` (N days from today). Empty/blank is NOT handled here — the
    caller treats a blank field as 'clear' (set None). `today` is injected so
    the relative forms are testable with a fixed now.
    """
    s = text.strip().lower()
    if s == "today":
        return today
    if s == "tomorrow":
        return today + timedelta(days=1)
    if s.startswith("+") and s[1:].isdigit():
        return today + timedelta(days=int(s[1:]))
    try:
        return date.fromisoformat(text.strip())
    except ValueError as exc:
        raise DueDateParseError(f"Not a date: {text!r}") from exc
```

- **Deliberately small (architect default) — final breadth is RESEARCHER scope (Q3).** ISO +
  `today`/`tomorrow`/`+N` covers the common cases and is fully testable with a fixed `today`. Whether
  to broaden it (`next friday`, `in 2 weeks`) or trim it is a UX call the researcher makes in
  `docs/ux/due-dates.md`; the architecture is unaffected — any accepted token resolves to a `date`
  inside this one pure function.
- **`DueDateParseError` is input validation, not persistence** — it is a `ValueError`, *not* a
  `TasqueError`. It never reaches the toast path; the screen catches it locally and pulses the bar
  `-invalid` (the same feedback empty-add already uses). It is re-exported from the controller so
  the screen imports it from the layer it is allowed to (`controller`), symmetric with `TodoSort`.
- **The researcher owns the field placeholder/help copy** (`docs/ux/due-dates.md`) — e.g.
  "YYYY-MM-DD, today, tomorrow, +3 — blank to clear". Grammar above is the architect's; wording is
  the researcher's.

---

## 5. Persistence — migration + dedicated setter

### 5a. Migration (append-only; `user_version` 2 → 3)

```python
def _migration_0003_add_due_date(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE todos ADD COLUMN due_date TEXT")  # nullable, ISO 'YYYY-MM-DD' or NULL

_MIGRATIONS = [
    _migration_0001_create_todos,
    _migration_0002_add_priority,
    _migration_0003_add_due_date,   # appended, never edit 0001/0002
]
```

- **Additive and non-destructive.** Existing rows get `due_date = NULL` (= no due date), exactly the
  pre-feature behaviour. On an existing v2 DB the ladder (`_MIGRATIONS[version:]`) runs *only* `0003`
  and bumps `user_version` to 3 (the reopen/skip path from the Feature #3 LEARNINGS entry).
- **`_row_to_todo` needs NO change** — it already reads `due_raw = col("due_date")` and converts
  `date.fromisoformat(due_raw) if due_raw else None`. This is the one seam that was fully pre-wired;
  before `0003` the defensive `col()` returned `None`, and after it returns the stored ISO string.

### 5b. Writing due date — a dedicated setter, mirroring `set_priority`/`set_completed`

```python
def set_due_date(self, todo_id: int, due: date | None) -> Todo:
    cur = self._conn.execute(
        "UPDATE todos SET due_date = ? WHERE id = ?",
        (due.isoformat() if due is not None else None, todo_id),
    )
    if cur.rowcount == 0:
        raise TodoNotFoundError(todo_id)
    self._conn.commit()
    return self.get(todo_id)
```

- **Why a setter, not widening `update()`:** identical reasoning to `set_priority` — the shipped
  `db.update()` writes only `text` + `completed`; widening it would couple the edit-text path to the
  due date and risk a stale-value clobber. `set_completed`/`set_priority` are the precedents;
  `set_due_date` is the third of the family. **Trap flagged for the implementer:** do **not** add
  `due_date` to `update()`'s `SET` list.
- **`add()` unchanged** — new todos insert without the column → `NULL` → none.

---

## 6. Controller integration — `set_due_date` through the `_apply` seam

Mirror the five shipped mutations: build a private command, route through `_apply`, return
`command.result`.

```python
class _SetDueDateCommand:
    def __init__(self, db: Database, todo_id: int, due: date | None) -> None:
        self._db = db
        self._todo_id = todo_id
        self._due = due
        self._prev: date | None = None
        self.result: Todo | None = None

    def execute(self) -> None:
        current = self._db.get(self._todo_id)          # raises TodoNotFoundError if gone
        self._prev = current.due_date
        self.result = self._db.set_due_date(self._todo_id, self._due)

    def undo(self) -> None:  # pragma: no cover - Feature #9 seam (no public undo yet)
        self._db.set_due_date(self._todo_id, self._prev)


def set_due_date(self, todo_id: int, due: date | None) -> Todo:
    """Set (or clear, with `due=None`) a todo's due date and return it."""
    command = _SetDueDateCommand(self._db, todo_id, due)
    self._apply(command)
    assert command.result is not None
    return command.result
```

- **Set-to-value, not cycle.** Unlike `_CyclePriorityCommand` (which computes the next value), the
  target `due` is passed in — so the same command handles both set (`due` is a date) and clear
  (`due is None`). One method, one command, both affordances.
- **Seam stays honest:** `_apply` keeps its `-> None` signature; the result rides on
  `command.result`. The `undo()` body is a clean inverse (`set_due_date(id, prev)`) — no new-id
  problem like `_DeleteCommand` — so #9's due-date undo is trivial; it carries the `# pragma: no
  cover` marker consistent with the other commands (no public `controller.undo()` until #9).
- **Re-exports:** `controller.__all__` gains `"parse_due_date"` and `"DueDateParseError"` (imported
  from `models`) so `screens/main.py` gets them from the controller. `set_due_date` (the value)
  takes a `date`; the screen builds it via `parse_due_date`. `due_state`/`DueState` are **not**
  re-exported — they are used by the widget, which already imports `models` directly (as
  `todo_item.py` imports `Priority`).

---

## 7. MainScreen · TodoList · InputBar coordination

### 7a. TodoList — new binding + message + action (mirrors `e`/`p`)

```python
Binding("D", "edit_due", "Due", show=True),   # add to TodoList.BINDINGS

class DueDateEditRequested(Message):           # add alongside EditRequested / PriorityCycleRequested
    def __init__(self, todo_id: int) -> None:
        super().__init__()
        self.todo_id = todo_id

def action_edit_due(self) -> None:
    todo_id = self.current_todo_id
    if todo_id is not None:
        self.post_message(self.DueDateEditRequested(todo_id))
```

### 7b. InputBar — a third `"due"` mode

Extends the existing mode machinery (no new pattern — the same two-bindings-per-key + `check_action`
footer swap from LEARNINGS 2026-07-02):

- `mode` reactive gains `"due"`. `watch_mode`: `"due"` → `border_title = "Due date"`.
- **Enter label is a two-state Set/Clear swap** (researcher refinement, `due-dates.md` Q3): `⏎ Set
  due` when the field has text, `⏎ Clear due` when empty — so blank-to-clear is discoverable exactly
  when the user backspaces a date away. Two same-key `enter` bindings (`submit_due` / `clear_due`,
  both `priority=True`), with `check_action` gating on `mode == "due"` **and** field-emptiness; both
  call `self._submit()`. This reuses the existing check_action/refresh_bindings label-swap machinery
  (Add↔Save / Cancel↔Done, LEARNINGS 2026-07-02) plus **one small addition**: an `on_input_changed`
  handler that calls `refresh_bindings()` so the label tracks empty↔non-empty as the user types.
  (`Esc` reads "Cancel" via the existing non-add branch.)
- `open_due(todo_id, prefill)`: set `editing_id = todo_id` (reused as "the row the bar acts on";
  edit and due are mutually exclusive, so no new field), `mode = "due"`, set the field to `prefill`
  with caret at end, set the due placeholder (`due-dates.md`: `YYYY-MM-DD, today, tomorrow, +3`),
  un-hide, focus, `refresh_bindings()`.
- **`_submit` becomes mode-aware for empty:** in `"due"` mode, empty is **valid** and means clear —
  post `Submitted("", "due")` rather than pulsing. Non-empty posts `Submitted(value, "due")` (the
  screen parses). Add/edit keep their current empty-pulses-invalid behaviour.
- **`flash_invalid()`**: a thin public wrapper over the existing `_pulse_invalid()`, so the screen
  can pulse the bar on a **parse** failure (which it, not the bar, detects) while keeping it open.

### 7c. MainScreen — handlers

```python
def on_todo_list_due_date_edit_requested(self, event: TodoList.DueDateEditRequested) -> None:
    event.stop()
    try:
        todo = self._controller.get_todo(event.todo_id)
    except TasqueError as exc:
        self.app.notify(f"Error: {exc}", severity="error")
        return
    prefill = todo.due_date.isoformat() if todo.due_date else ""
    self.query_one(InputBar).open_due(todo.id, prefill)
```

`on_input_bar_submitted` dispatches the new mode:

```python
async def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
    event.stop()
    if event.mode == "add":
        await self._handle_add(event.value)
    elif event.mode == "edit":
        await self._handle_edit(event.value)
    else:  # "due"
        await self._handle_set_due(event.value)


async def _handle_set_due(self, raw: str) -> None:
    input_bar = self.query_one(InputBar)
    todo_list = self.query_one(TodoList)
    try:
        due = None if not raw else parse_due_date(raw, today=date.today())
    except DueDateParseError:
        input_bar.flash_invalid()          # keep bar open, input preserved
        return
    try:
        updated = self._controller.set_due_date(input_bar.editing_id, due)
    except TasqueError as exc:
        self.app.notify(f"Error: {exc}", severity="error")
        input_bar.close()
        await self.refresh_todos()
        todo_list.focus()
        return
    input_bar.close()
    if self._sort is TodoSort.DUE:
        await self.refresh_todos(keep_id=updated.id)   # row may re-rank → follow the task
    else:
        todo_list.update_todo(updated)                 # position stable → in-place re-render
    todo_list.focus()
```

- **In-place vs. rebuild is sort-mode dependent**, exactly like the priority cycle handler: in
  `DUE` sort a changed due date can move the row, so `refresh_todos(keep_id=updated.id)` follows the
  task; in `CREATED`/`PRIORITY` the row doesn't move, so the cheap `update_todo` re-render suffices
  (and it recomputes `#due` + `-overdue`/`-due-today` via `watch_todo`).
- **The `TasqueError` guard** matches the shipped handlers (row deleted mid-flow → toast, no crash).

### 7d. Sort cycle becomes three-way (generalising #6's toggle)

`TodoSort` gains `DUE`. The `s` action cycles `CREATED → PRIORITY → DUE → CREATED`:

```python
_SORT_CYCLE = (TodoSort.CREATED, TodoSort.PRIORITY, TodoSort.DUE)

async def action_cycle_sort(self) -> None:
    i = _SORT_CYCLE.index(self._sort)
    self._sort = _SORT_CYCLE[(i + 1) % len(_SORT_CYCLE)]
    keep = self.query_one(TodoList).current_todo_id
    await self.refresh_todos(keep_id=keep)
    self.app.notify(f"Sorted by {_SORT_LABEL[self._sort]}", severity="information")
```

with `_SORT_LABEL = {CREATED: "creation order", PRIORITY: "priority", DUE: "due date"}` (this also
corrects the shipped `"Sorted by created"` wording to `main-screen.md`/`priority.md`'s
"creation order"). Border-title suffix in `_update_counts` extends the same way:

```python
if self._sort is TodoSort.PRIORITY:
    title += " · by priority"
elif self._sort is TodoSort.DUE:
    title += " · by due"
```

`CREATED` stays suffix-free (default view = no clutter, per `priority.md` §`s`).

### 7e. Toggle handler — generalise the "demote done" branch

The shipped `on_todo_list_toggle_requested` branches `if self._sort is TodoSort.PRIORITY:` to
re-sort (because completing a task moves it between the active/done bands). **`DUE` sort has the same
`completed ASC` primary key**, so completing a task moves bands there too. The condition generalises:

```python
if self._sort is not TodoSort.CREATED:   # PRIORITY or DUE both demote done below active
    await self.refresh_todos()
    tl = self.query_one(TodoList)
    if len(tl) > 0:
        tl.index = min(index, len(tl) - 1)   # cursor holds position → next active slides in
else:
    todo_list.update_todo(updated)
    self._update_counts(self._controller.list_todos())
```

The **cursor rule is unchanged and deliberate** (`feature-6.md` §6 / `priority.md` OQ4): the toggle
handler lands by **index**, not `keep_id` — the just-completed task slides to the done band and the
next active task takes its place ("move on to the next thing"). Only the `p` cycle, `D` set-due, and
`s` sort follow the task by id.

`refresh_todos(keep_id=…)` and `TodoList.highlight_id` already exist (shipped in #6) — no new
cursor plumbing.

---

## 8. TodoItem rendering + CSS + accessible label

> **Display strings RESOLVED by `docs/ux/due-dates.md` (researcher, 2026-07-04).** The forms below
> are now the spec: `OVERDUE 06-20` / `due today` / `06-30` / `──`; **future stays absolute** (not
> relative `in 3d`), with a **year rule** — `MM-DD` in the current calendar year, full `YYYY-MM-DD`
> otherwise (overdue and future alike, e.g. `OVERDUE 2025-12-01` / `2027-01-15`). This resolves
> `main-screen.md` Open Question #4. The year rule threads `today` into `_due_display`/`_fmt_due`
> (below) — the widget passes the same `date.today()` it already computes for `due_state`, so no new
> clock read and it stays fixed-`today`-testable. Colour stays paired with a non-colour word
> (Principle 4).

**`todo_item.py` changes** (activating the reserved `#due` slot):

```python
def _fmt_due(due: date, today: date) -> str:
    # Year rule (due-dates.md Q4): MM-DD in the current year, full ISO otherwise.
    return due.strftime("%m-%d") if due.year == today.year else due.isoformat()


def _due_display(due: date | None, state: DueState, completed: bool, today: date) -> str:
    """The string for the reserved #due slot (due-dates.md Q4)."""
    if due is None:
        return ""                                     # blank slot — no due date
    if completed:
        return "──"                                   # done rows show no stale escalation
    if state is DueState.OVERDUE:
        return f"OVERDUE {_fmt_due(due, today)}"       # OVERDUE 06-20 / OVERDUE 2025-12-01
    if state is DueState.TODAY:
        return "due today"
    return _fmt_due(due, today)                         # future: 06-30 / 2027-01-15
```

- **`watch_todo`**: add beside the checkbox/priority/title updates —
  `today = date.today(); state = due_state(new_todo.due_date, today);
  self.query_one("#due", Static).update(_due_display(new_todo.due_date, state, new_todo.completed, today))`.
  (`#due` already exists in `compose` with `markup=False`; it just starts receiving content.)
- **`_sync_classes`** — replace the unconditional `remove_class("-overdue", "-due-today")` with
  set-exactly-the-right-one, **gated on completion**:
  ```python
  today = date.today()
  state = due_state(todo.due_date, today)
  self.set_class(not todo.completed and state is DueState.OVERDUE, "-overdue")
  self.set_class(not todo.completed and state is DueState.TODAY, "-due-today")
  ```
  The `not todo.completed` gate is what guarantees `-overdue`/`-due-today` never co-occur with
  `-done` — so there is **no CSS source-order requirement** for `.-done > #meta` vs
  `.-overdue > #meta` (unlike the priority done-dim, which *did* need ordering because a done task
  keeps its priority). This is the design paying attention to the LEARNINGS 2026-07-03 tie-break
  lesson and structurally avoiding the trap.
- **Accessible label** — fold the due word in *after* the text (matching `main-screen.md`'s example
  `"incomplete, high priority, Finish the quarterly report, due today"`):
  ```python
  # in _compose_accessible_label, after appending todo.text:
  due_word = _due_word(todo.due_date, due_state(todo.due_date, date.today()), todo.completed)
  if due_word is not None:
      parts.append(due_word)
  ```
  where `_due_word` returns `"overdue"` / `"due today"` / `"due 2026-06-30"` (future uses **full ISO**
  for unambiguous read-aloud, `due-dates.md` Q4) / `None` (none or completed → omitted). Label order
  becomes **completion, priority, text, due**.

**CSS — no change required.** `tasque.tcss` already ships:

```
TodoItem.-overdue   > #meta { color: $error; text-style: bold; }   /* activated by #7 */
TodoItem.-due-today > #meta { color: $warning; }                   /* activated by #7 */
TodoItem.-done      > #meta { color: $text-disabled; }             /* shipped #4/#6 */
```

`#due` lives inside `#meta` (a `Horizontal`), so these `> #meta` rules colour the due text via
inheritance. **Forward-note for Feature #8 (context, not a decision):** `#meta` will also hold the
`#category` tag; when #8 lands, decide whether an overdue row should tint the category too (keep the
`> #meta`-wide rule) or only the date (narrow to `#meta > #due`). For #7, `#due` is the only
populated child, so the shipped rule is correct as-is — no premature narrowing.

**Slot width:** `#meta` is `width: auto` and flexes; the title (`1fr`) yields, so `OVERDUE 06-20`
(12 cols) fits without a CSS change. On a narrow terminal `main-screen.md` §Resize drops the due
slot first — acceptable, it is optional meta.

---

## 9. Sort / filter policy

**Sort by due — delivered in #7.** `TodoSort.DUE`, `ORDER BY` in `db.py` (persistence boundary):

```sql
-- TodoSort.DUE
ORDER BY completed ASC, due_date ASC NULLS LAST, id ASC
```

1. **`completed ASC` — done demoted below active**, identical to priority sort and the same
   deliberate call (a completed task, however overdue it *was*, should not sit above active work).
2. **`due_date ASC NULLS LAST` — earliest first.** ISO text sorts chronologically (§2a), so `ASC`
   puts the most-overdue/soonest task at the top of the active band; `NULLS LAST` sinks no-due-date
   tasks below all dated ones (explicit, matching priority's `NULLS LAST` style).
3. **`id ASC` tie-break** — two tasks due the same day keep creation order; stable re-sort.

Default stays `CREATED`; #7 does not silently re-rank existing lists on upgrade.

**Filter — deferred to Feature #11 (surfaced, not silently dropped).** The acceptance criterion
reads "Sort/**filter** by due date available." A true attribute *filter* (e.g. "show only overdue")
is a cross-cutting concern that Feature #11 (Global Search / filter) owns — `feature-6.md` made the
same call for priority, deferring filtering to #11 and delivering only sort. **RESOLVED (user
2026-07-03): by-due sort ships in #7; real filtering is deferred to #11** as a unified filter across
priority / due / category. The constraint is recorded on #11's PLAN.md entry so it travels with that
feature, rather than being scattered as per-attribute filters into #6/#7/#8.

---

## 10. State-guard (unchanged mechanism)

`D` is a **`TodoList` binding**, so it fires only while the list holds focus — when the `InputBar`
is open (list blurred, keys consumed by the `Input`) or the delete `ModalScreen` is up, `D` cannot
fire behind them (the structural state-guard, `feature-5.md` §6). While the bar is open in `"due"`
mode, a stray `D` types the literal character into the field. `s` remains a `MainScreen` binding
(reachable from the empty state, a no-op when nothing to sort). No new guarding logic.

---

## 11. Testing seams

**`models.py` (`tests/test_models.py`):**
- `due_state` table test with a **fixed** `today`: past → OVERDUE, `today` → TODAY, future → FUTURE,
  `None` → NONE. (This is the acceptance criterion's "overdue detection with a fixed now.")
- `parse_due_date` with a fixed `today`: ISO round-trips; `today`/`tomorrow`/`+3` resolve correctly;
  junk (`"soon"`, `"2026-13-40"`) raises `DueDateParseError`.

**`db.py` (`tests/test_db.py`):**
- Migration: a fresh DB reaches `schema_version == 3` and has a `due_date` column; a hand-built v2
  DB, reopened, migrates to 3 with existing rows `due_date IS NULL` (data preserved).
- `set_due_date` round-trips a date and `None` (clear); raises `TodoNotFoundError` for a missing id;
  stores the ISO string (assert the raw column value).
- `list_todos(sort=DUE)` order: earliest-first among active, `NULL` last, `id ASC` tie-break within
  a day, done demoted below active. `sort=CREATED`/`PRIORITY` unchanged.
- `update()` (text edit) leaves `due_date` untouched (guards the "don't widen update" decision).

**`controller.py` (`tests/test_controller.py`):**
- `set_due_date(id, d)` returns the updated `Todo` with `due_date == d`; `set_due_date(id, None)`
  clears; raises `TodoNotFoundError` for a missing id (asserts the `_apply` path propagates).
- `parse_due_date` / `DueDateParseError` reachable via the controller re-export.

**Pilot (`tests/widgets/test_todo_item.py`, `tests/screens/test_main.py`):**
- Seed a todo with `due_date = date.today() - timedelta(days=1)` → row renders `OVERDUE …` and gains
  `-overdue`; `date.today()` → `due today` + `-due-today`; a future date → `MM-DD`, no class; `None`
  → blank `#due`, no class. (Relative-to-real-today seeding keeps the pilot deterministic without
  freezing the clock; the fixed-now unit tests above own the boundary precision.)
- Completing an overdue row **clears** `-overdue` (escalation suppressed on done; `#due` → `──`);
  un-completing restores it.
- `D` on a row → `InputBar` opens in `"due"` mode, pre-filled with the current ISO date (or empty);
  typing `2026-07-10` + Enter persists and re-renders; blank + Enter clears; junk + Enter pulses
  `-invalid` and keeps the bar open.
- `s` cycles CREATED → PRIORITY → DUE → CREATED; in DUE the border-title shows `· by due` and rows
  order earliest-first with done demoted; the cursor follows the same task (`keep_id`).
- Setting a due date while in DUE sort re-ranks the row and the cursor follows it; in CREATED it
  stays put.
- Accessible label of an overdue row includes `"overdue"`; a due-today row includes `"due today"`.
- Failure path: `D` then Enter on a row whose id was deleted out from under the screen → error
  toast, no crash.

All pilot assertions query via `app.screen` (LEARNINGS: `App.query` doesn't traverse pushed
screens) and use a seeded `:memory:` controller. Where correctness rides on the resolved `#meta`
colour (overdue `$error` vs due-today `$warning`), assert the computed `styles.color` under the real
`TasqueApp` (so `tasque.tcss` loads), per the LEARNINGS 2026-07-03 computed-colour rule.

---

## 12. Migration / schema impact — summary

| | |
| --- | --- |
| `user_version` | **2 → 3** (append `_migration_0003_add_due_date`) |
| DDL | `ALTER TABLE todos ADD COLUMN due_date TEXT` (nullable, ISO `YYYY-MM-DD`, defaults `NULL` = none) |
| Destructive? | No. Additive; existing rows unaffected (`due_date = NULL`). |
| Mapper | `_row_to_todo` **already** converts `date.fromisoformat(due_raw)` — no change. |
| Write path | new `db.set_due_date` (third of the `set_completed`/`set_priority` family); `add()`/`update()` untouched. |
| CSS | **No change** — `.-overdue`/`.-due-today`/`.-done > #meta` already ship. |

---

## Alternatives Considered

- **`due_date` as a `datetime` / Unix timestamp:** rejected — a to-do is due on a *day*, not an
  instant; both reintroduce a time-of-day and timezone the domain doesn't have and make "overdue"
  ambiguous. A `date` + ISO text + local-civil comparison is unambiguous and sorts for free.
- **Store/compare due dates in UTC:** rejected — flips "today" to "overdue" hours early for
  negative-offset users. Local civil `date.today()` comparison (rolls at local midnight) is correct
  for a personal single-machine app.
- **A modal calendar-grid date picker:** rejected for #7 as far heavier (new `ModalScreen`, grid
  nav, its own UX spec) than the value; the docked-`InputBar` text flow is keyboard-first and reuses
  shipped machinery. A picker is a fine *future* enhancement layered on the same `set_due_date`.
- **Inline due field in the add form:** rejected — keeps the single-field `InputBar` single-field
  (the `Tab`-inert convention) and matches priority being `p`-only. A task is born with no due date.
- **Widen `db.update()` to also write `due_date`:** rejected — couples the edit-text path to the due
  date (stale-clobber risk) and breaks the single-column-setter symmetry. `set_due_date` mirrors
  `set_completed`/`set_priority`.
- **Sort mode stored in the DB / on the controller:** rejected (same as #6) — it's an ephemeral
  *view* preference, not task data; it lives on `MainScreen._sort`, not persisted.
- **By-due sort ignoring completion (pure `due_date ASC`):** rejected as the default — a *done*
  overdue task above active work is wrong for a to-do app. `completed ASC` primary key is the
  deliberate choice, symmetric with priority sort.
- **Put overdue classification in the widget / a raw `date.today()` compare inline:** rejected — a
  pure `due_state(due, today)` in `models.py` defines the rule once, is clock-free unit-testable with
  a fixed now (the acceptance criterion), and keeps the widget a thin renderer.

---

## Resolved decisions (user, 2026-07-03)

1. **Due-edit key → `D` (Shift+D).** `d` is Delete, so due takes the sibling `D` — attribute vs
   action on the same row; the shift-modified form reads as "the considered form"; `Esc` recovers a
   fat-finger. Reflected in §4 and §7a.
2. **Sort vs. filter → by-due *sort* in #7; real *filter* deferred to #11.** `TodoSort.DUE` ships in
   #7's sort cycle (§9); a unified filter across priority / due / category is Feature #11's, and the
   constraint is now recorded on #11's PLAN.md entry so it travels with that feature.

## Researcher scope (handed to the researcher — not architect questions)

These are UX decisions, not architecture. They do **not** block the design; the implementer wires the
seams (`models.parse_due_date`, `_due_display`) to whatever `docs/ux/due-dates.md` specifies.
Recorded here so the handoff is explicit rather than an unowned "open question."

3. **Parse-grammar breadth + field placeholder/help copy.** Architect default: ISO `YYYY-MM-DD` +
   `today` / `tomorrow` / `+N` (§4a) — enough for #7 and testable with a fixed now. The researcher
   decides the final accepted set (add `next friday` / `in 2 weeks`, or trim) and the placeholder
   wording. Any accepted token resolves to a `date` inside `parse_due_date`, so the architecture is
   unaffected by the breadth chosen.
4. **Display strings for the `#due` slot.** Architect default follows `main-screen.md` §States —
   `OVERDUE 06-20` (overdue), `due today` (today), `06-30` (future), `──` (done). The exact wording,
   any relative form (`in 3d`), and far-future year handling (`MM-DD` drops the year) are the
   researcher's to finalise via `_due_display` (§8) — colour must stay paired with a non-colour word
   (Principle 4).
