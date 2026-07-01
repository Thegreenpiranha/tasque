# Architecture: Feature #5 — InputBar: Add, Toggle Complete, Edit, Delete

> Design proposal produced by the architect sub-agent (2026-07-01), built against the shipped
> Feature #4 code and the three UX specs (`docs/ux/input-bar.md`, `edit-screen.md`,
> `delete-confirmation.md`) and the base visual language in `docs/ux/main-screen.md`.
>
> **Resolved open questions (by the user, 2026-07-01):**
> 1. Delete screen filename → `screens/delete_confirm.py` (matches the `main.py`-for-`MainScreen` precedent).
> 2. `controller.get_todo(id)` read wrapper → yes, added on the controller (layer-honest source for edit pre-fill + dialog text).
> 3. Footer relabel `Esc Cancel` → `Esc Done` after ≥1 add → keep in-spec (per `input-bar.md`), not deferred.

---

## Summary
Feature #5 wires the four core mutations through the already-shipped seams: a new docked `InputBar` widget (shared add/edit surface), a new `DeleteConfirmScreen(ModalScreen[bool])`, list-level bindings on `TodoList` that post the existing `ToggleRequested`/`EditRequested`/`DeleteRequested` intents, and real controller bodies that route every write through the `_apply(Command)` choke-point so Feature #9's undo stack hooks in with zero call-site changes. No schema change: everything fits the v1 `todos` table.

A note grounding the design in the real shipped code: the shipped `Command` Protocol in `controller.py` uses **`execute()` / `undo()`**, not `do()/undo()` — this design targets the real code. And `_apply`'s shipped signature returns `None`, so the mutation result is carried on the command object (`command.result`), not returned by `_apply`. That is what keeps the seam honest (see §4).

---

## 1. Module / file plan

**New files**
- `src/tasque/widgets/input_bar.py` → `class InputBar(Widget)` — the docked add/edit bar. (snake_case of class, matches `todo_item.py` precedent.)
- `src/tasque/screens/delete_confirm.py` → `class DeleteConfirmScreen(ModalScreen[bool])`.
  - *Naming:* `delete-confirmation.md` suggested `delete_confirm_screen.py`, but the repo precedent is `screens/main.py` for `MainScreen` (the `Screen` suffix is dropped from the filename). Use `delete_confirm.py` to match. **(Resolved: use `delete_confirm.py`.)**

**Modified files**
- `src/tasque/controller.py` — implement `add_todo`/`toggle_todo`/`edit_todo`/`delete_todo` and `_apply`; add four private `_Command` classes; add a small `get_todo()` read (needed for edit pre-fill and delete-dialog text).
- `src/tasque/screens/main.py` — compose the `InputBar`; add `space`/`enter` toggle handling; add message handlers for `ToggleRequested`/`EditRequested`/`DeleteRequested` and `InputBar.Submitted`/`Cancelled`; delete-confirm callback + post-delete focus rule; error-toast guard.
- `src/tasque/widgets/todo_list.py` — add `Binding`s for `space`/`enter`→toggle, `e`→edit, `d`→delete, each posting the existing intent message via `current_todo_id`.
- `src/tasque/tasque.tcss` — `InputBar` (docked, `$accent` border, `-invalid`, prompt glyph), `#confirm-dialog` modal styling.
- `src/tasque/widgets/__init__.py` — export `InputBar`.
- `src/tasque/screens/__init__.py` — export `DeleteConfirmScreen`.

**`app.py`: no change.** `q` stays on the app, `a`/`?` stay on `MainScreen`, list actions live on `TodoList`. No binding needs to move up.

---

## 2. `InputBar` widget interface

`src/tasque/widgets/input_bar.py`:

```python
class InputBar(Widget):
    mode: reactive[str] = reactive("add", init=False)   # "add" | "edit"
    editing_id: int | None                              # set in edit mode, else None

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("tab", "noop", show=False),             # Tab inert (canonical convention)
        Binding("shift+tab", "noop", show=False),
    ]

    class Submitted(Message):
        def __init__(self, value: str, mode: str) -> None: ...   # value is trimmed, non-empty
    class Cancelled(Message):
        def __init__(self, mode: str) -> None: ...

    def compose(self) -> ComposeResult:
        # Horizontal: Static("› ", id="prompt", markup=False)  +  Input(id="bar-input")

    def open_add(self) -> None: ...     # mode="add", editing_id=None, value="", remove -hidden, input.focus()
    def open_edit(self, todo_id: int, text: str) -> None: ...  # mode="edit", value=text, cursor at end
    def clear_for_next_add(self) -> None: ...   # value="", keep open + focused (add stay-open)
    def close(self) -> None: ...        # add -hidden (display:none)

    def watch_mode(self, mode: str) -> None: ...  # border_title + placeholder swap
    def on_input_submitted(self, event: Input.Submitted) -> None: ...  # validate → post Submitted / pulse / Cancelled
    def action_cancel(self) -> None: ...  # post Cancelled(self.mode)
    def action_noop(self) -> None: ...
```

Key behaviours:
- **Prompt glyph** `› ` is a non-focusable `Static`, so the bar stays single-field and `Tab` has nothing to cycle to (keeps `Tab` inert without special focus-trapping).
- **Show/hide** via the shared `-hidden` class (`display:none`, already in the stylesheet). Idle = 0 rows; active = auto height (3 with border), and `#list-panel` (`height:1fr`) yields.
- **mode** reactive drives `border_title` (`New task` / `Edit task`) and the Input placeholder — the *word* distinguishes the mode, never colour (color-blind safety).
- **Focus** enters via `input.focus()` in `open_*`; because the bar lives *outside* the `ListView` subtree, its `Input` focuses normally (this is the whole reason for the docked design vs. in-row — `ListView.can_focus_children=False`). Focus leaves only on `Esc`/submit, when `MainScreen` re-focuses the list.
- **Validation:** `on_input_submitted` trims; empty/whitespace → add `-invalid`, `set_timer(0.6, remove_class)`, do **not** post. Non-empty → post `Submitted(value, mode)`.
- **Unchanged edit:** `open_edit` records the original text; on Enter in edit mode with value unchanged, post `Cancelled("edit")` instead of `Submitted` (no write, no future undo entry — the close/refocus path is identical to cancel).
- **Clearing is `MainScreen`-driven:** the bar does *not* self-clear on submit, because on a persistence failure the typed text must survive for retry. `MainScreen` calls `clear_for_next_add()` only after a confirmed successful add.

CSS classes/reactives the implementer toggles: `-hidden`, `-invalid`, `mode` (reactive, not a class — drives title/placeholder). No inline styling.

---

## 3. `DeleteConfirmScreen(ModalScreen[bool])` interface

`src/tasque/screens/delete_confirm.py`:

```python
class DeleteConfirmScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("y", "confirm", show=True),   # y Delete
        Binding("d", "confirm", show=False),  # d = "yes, the thing I pressed d for"
        Binding("n", "cancel",  show=True),   # n / Esc Cancel
        Binding("escape", "cancel", show=False),
    ]

    def __init__(self, task_text: str) -> None: ...   # text shown quoted in the dialog

    def compose(self) -> ComposeResult:
        # Container(id="confirm-dialog"): prompt Static, quoted-target Static,
        # Horizontal(Button("Delete", id="delete-btn", variant="error"),
        #            Button("Cancel", id="cancel-btn", variant="default")),
        # Footer

    def on_mount(self) -> None: ...                 # query_one("#cancel-btn").focus()  → default-safe
    def action_confirm(self) -> None: self.dismiss(True)
    def action_cancel(self)  -> None: self.dismiss(False)
    def on_button_pressed(self, event: Button.Pressed) -> None: ...   # Enter/click → dismiss per button id
    def on_descendant_focus(self, event) -> None: ...  # wrap focused button label in « … »
```

- **Result contract:** returns `bool` via `dismiss(True|False)`. `True` = delete confirmed, `False` = cancelled.
- **Default focus = Cancel** (`on_mount`), so a reflexive `Enter` (activates focused button) cancels — the k9s lesson.
- **`Tab` cycle:** `ModalScreen` traps input; `Tab`/`Shift+Tab`/`←`/`→` move between the only two focusables (`Cancel`↔`Delete`) and never leave the modal. Enter activates the focused button via `Button.Pressed`.
- **`« »` brackets:** CSS cannot inject text, so the focused-button marker is done in Python — `on_descendant_focus` rewrites the two button labels (`« Cancel »` / `Delete`, or vice-versa). This is dynamic state CSS can't express, so it is a permitted exception to the styling rule.
- **Copy:** neutral — `Delete this task?` + quoted title only. No "permanently", no undo hint (deferred to #9 per LEARNINGS).

**How `MainScreen` consumes it:**
```python
def on_todo_list_delete_requested(self, event) -> None:
    todo = self._controller.get_todo(event.todo_id)          # for the quoted text; guarded (see §5)
    index = self.query_one(TodoList).index
    self.push_screen(
        DeleteConfirmScreen(todo.text),
        lambda ok: self._on_delete_confirmed(ok, event.todo_id, index),
    )
```
The push-screen callback form (not `await`) is used so the handler stays synchronous. Post-confirm focus logic in §5.

---

## 4. Controller integration — the honest `_apply` / `Command` seam

`src/tasque/controller.py`. Reads (`get_todo`) added; four mutation seams implemented; `_apply` implemented as a pass-through.

```python
def get_todo(self, todo_id: int) -> Todo:            # new thin read
    return self._db.get(todo_id)

def add_todo(self, text: str) -> Todo:
    cmd = _AddCommand(self._db, text)
    self._apply(cmd)
    return cmd.result

def toggle_todo(self, todo_id: int) -> Todo:
    cmd = _ToggleCommand(self._db, todo_id); self._apply(cmd); return cmd.result

def edit_todo(self, todo_id: int, text: str) -> Todo:
    cmd = _EditCommand(self._db, todo_id, text); self._apply(cmd); return cmd.result

def delete_todo(self, todo_id: int) -> Todo:
    cmd = _DeleteCommand(self._db, todo_id); self._apply(cmd); return cmd.result

def _apply(self, command: Command) -> None:
    command.execute()      # Feature #9 adds: self._undo.append(command); self._redo.clear()
```

The four commands (private, controller-internal — they may call `db.py`'s public methods since only *SQL* is forbidden outside `db.py`):

| Command | `execute()` (stores `self.result: Todo`) | `undo()` |
| --- | --- | --- |
| `_AddCommand(db, text)` | `self.result = db.add(Todo.new(text))` | `db.delete(self.result.id)` |
| `_ToggleCommand(db, id)` | `cur = db.get(id)`; record `cur.completed`; `self.result = db.set_completed(id, not cur.completed)` | `db.set_completed(id, prev)` |
| `_EditCommand(db, id, text)` | `cur = db.get(id)`; record `cur.text`; `self.result = db.update(replace(cur, text=text))` | `db.update(replace(current, text=old))` |
| `_DeleteCommand(db, id)` | `self.result = db.delete(id)` (returns the deleted `Todo`; raises `TodoNotFoundError` if gone) | `db.add(self.result)` |

Each satisfies the `Command` Protocol (`execute()`/`undo()` → `None`), plus a `result: Todo | None` attribute.

**Why the seam stays honest without building #9:**
- `_apply` keeps its shipped `-> None` signature; the result travels on `command.result`, which the four public methods read and return. `db.delete` still returns the deleted `Todo`, preserving the undo data.
- Feature #9 changes **only** the body of `_apply` (append to an undo stack, clear redo) and adds undo/redo methods. **No call site changes** — the mutation methods already build a `Command` and read `cmd.result`.
- `undo()` bodies are directionally complete today (never invoked at #5). **One #9 detail flagged:** `_DeleteCommand.undo` re-inserts via `db.add`, which assigns a **new** id. Restoring the original id is a #9 concern (may want a `db.insert_with_id` or resurrection path). Not built now; noted so #9 doesn't rediscover it.

---

## 5. MainScreen coordination + data flow

**TodoList new bindings** (each posts an existing intent message using `current_todo_id`; no-op if `None`):
```python
Binding("space", "toggle"), Binding("enter", "toggle"),   # overrides ListView's native select
Binding("e", "edit"), Binding("d", "delete"),
# action_toggle/edit/delete: post ToggleRequested/EditRequested/DeleteRequested(current_todo_id)
```

**Toggle** (`space`/`enter` → `ToggleRequested` → controller → single-row re-render):
`on_todo_list_toggle_requested` → `updated = controller.toggle_todo(id)` → `todo_list.update_todo(updated)` (in-place, cursor preserved) → `self._refresh_counts()` (border-title only; active↔done shifted). No full rebuild.

**Add** (`a` → show bar → `Submitted(value,"add")` → append, bar stays open):
`action_add_todo` → `input_bar.open_add()` (also sets `empty_state.cta = "Press  a  to add your first task"`). On `InputBar.Submitted` with `mode=="add"`: `controller.add_todo(value)` → `await refresh_todos()` (full reload; new row appends in creation order + counts update) → `todo_list.index = len-1` (cursor → new row, shows blurred-dim since bar keeps focus) → `input_bar.clear_for_next_add()`. Bar stays open and focused.

**Edit** (`e` → `EditRequested` → pre-fill → `Submitted(value,"edit")` → single-row re-render → focus returns):
`on_todo_list_edit_requested` → `todo = controller.get_todo(id)` → `input_bar.open_edit(id, todo.text)` (caret at end, list blurs). On `Submitted` with `mode=="edit"`: `updated = controller.edit_todo(bar.editing_id, value)` → `todo_list.update_todo(updated)` (cursor unmoved) → `input_bar.close()` → `todo_list.focus()`. Unchanged text arrives as `Cancelled("edit")` → close + refocus, no write.

**Delete** (`d` → `DeleteRequested` → modal → `True`: delete + focus rule; `False`: no-op):
See §3 for the push. In the callback:
```python
def _on_delete_confirmed(self, ok, todo_id, index):
    if not ok:
        self.query_one(TodoList).focus(); return     # same row stays highlighted
    n = len(self._controller.list_todos())            # count BEFORE delete
    self._controller.delete_todo(todo_id)
    await self.refresh_todos()                        # rebuild + counts; empties → EmptyState
    todos = self._controller.list_todos()
    if not todos:
        self.focus()                                  # empty: focus screen so a/?/q work
    else:
        tl = self.query_one(TodoList)
        tl.index = min(index, n - 2)                  # next row (clamp to prev if last)
        tl.focus()
    self.app.notify(f'✓ Deleted "{...}"', severity="information")
```
`min(index, n-2)`: deleted-last (`index==n-1`) → `n-2` (previous); deleted-middle/first → `index` (next slides up). Empty → `EmptyState` (refresh already toggles `-hidden`).

**Failure path (row vanished mid-edit/delete):** `controller.get_todo`/`edit_todo`/`delete_todo` raise `TodoNotFoundError` (a `TasqueError`). Each `MainScreen` handler wraps the controller call:
```python
try:
    updated = self._controller.edit_todo(bar.editing_id, value)
except TasqueError as exc:
    self.app.notify(f"Error: {exc}", severity="error")
    self._input_bar.close(); await self.refresh_todos(); return
todo_list.update_todo(updated)
```
The list keeps its last good render; the toast is `$error`-styled with the `Error:` prefix.

*Reconciliation with CLAUDE.md:* CLAUDE.md says "the controller catches them and turns them into user-facing messages," but the controller has no `app` handle. The intent is satisfied structurally: `db.py` already converts `sqlite3` → typed `TasqueError` (raw DB errors never escape), and the **screen** — the only layer with `self.app` — renders the toast. All three UX specs assign the toast to the screen. This is the design, not an open question.

---

## 6. State-guard (keys inert while bar/modal open)

Primary mechanism is **structural**, free from Textual:
- `space`/`e`/`d`/`enter` are **`TodoList` bindings** — they fire only when `TodoList` holds focus. When the `InputBar`'s `Input` is focused, those keys are consumed as literal characters by the `Input` and never bubble to the list (the list is blurred). So no toggle/edit/delete fires while the bar is open.
- `DeleteConfirmScreen` is a `ModalScreen`, which traps all input — `j/k/a/space/e/d` never reach `MainScreen` behind it.

Defense-in-depth for `a` (the one action bound on `MainScreen`, needed even from the empty state where the list can't be focused): add a guard at the top of `action_add_todo`:
```python
if not self._input_bar.has_class("-hidden"):
    return          # bar already open; ignore a second `a`
```
This covers the theoretical case where `a` reaches `MainScreen` while the bar is open. `ModalScreen` already blocks `a` when the delete dialog is up. Together these satisfy `main-screen.md`'s edge case ("a toggle should not fire if an inline edit/confirm modal is open").

---

## 7. CSS / reactive plan

`tasque.tcss` additions (all semantic tokens; symbol+colour pairing):

```
InputBar        { height: auto; border: round $accent; }   /* $accent = "you type here" vs list's $primary */
InputBar.-hidden{ display: none; }
InputBar.-invalid { border: round $error; }                /* ~600ms pulse, word "Empty…" carries meaning too */
InputBar #prompt  { width: 2; color: $accent; }            /* › glyph, ASCII › fallback > */
InputBar #bar-input { border: none; background: $surface; }

#confirm-dialog { border: round $error; padding: 1 2; width: auto; max-width: 50;
                  background: $surface; }                   /* $error border = destructive */
#confirm-dialog Button { margin: 0 1; }
```
Reactives/classes toggled from Python: `InputBar.mode` (title/placeholder), `-hidden`, `-invalid`; `DeleteConfirmScreen` focused-button `« »` labels; `EmptyState.cta`. Colour is never the sole signal: mode = title word, error = word + `-invalid`, cursor = `▸`, focused button = `« »`, checkbox = `[ ]`/`[x]`. `ModalScreen` supplies the dimmed 50% backdrop automatically.

---

## 8. Testing seams (pilot `App.run_test()`, seeded `:memory:` controller, query via `app.screen`)

Controller unit tests (`tests/test_controller.py`): replace the four `*_raises_not_implemented` tests with round-trips — `add_todo` returns a `Todo` with an id and persists; `toggle_todo` flips `completed`; `edit_todo` changes text and preserves `completed`; `delete_todo` returns the deleted `Todo` and it's gone from `list_todos`; each raises `TodoNotFoundError` for a missing id (asserting the `_apply` path propagates).

Integration/pilot tests (`tests/screens/test_main.py`, new `tests/widgets/test_input_bar.py`, `tests/screens/test_delete_confirm.py`):
- **Add:** press `a`, type text, press `enter` → a new `TodoItem` exists at the bottom with that text; the `InputBar` is still visible (not `-hidden`) and its input value is empty (stays open, cleared).
- **Empty-input add rejected:** `a`, `enter` on empty → no new `TodoItem`; bar carries `-invalid`.
- **Toggle:** focus list, `space` → target `TodoItem` gains `-done` and its checkbox renders `[x]`; press again → `-done` removed, `[ ]`; border-title counts updated.
- **Edit:** `e` → bar visible, input value equals the row's text; type + `enter` → the same `TodoItem` (same `todo_id`, same `index`) shows new text; bar hidden; assert `TodoList` regained focus.
- **Delete → Yes:** `d` (modal appears), `y` → row removed; assert cursor lands on the row that took the deleted index (or previous if last); success toast.
- **Delete → No:** `d`, `esc` → same `todo_id` still highlighted, count unchanged.
- **Delete only row:** `EmptyState` no longer `-hidden`, `TodoList` `-hidden`, focus on screen.
- **State-guard:** open bar with `a`, then press `d`/`e` → no modal pushed, no new `-done`; assert only literal text entered.
- **Failure toast:** monkeypatch/seed so `edit_todo` raises `TodoNotFoundError` → assert an error notification is raised and the row keeps its old text.

All assertions are on observable state (DOM classes, rendered text, `index`, visibility, notifications) — never private methods.

---

## 9. Migration / schema impact

**None.** Toggle uses `completed`, add/edit use `text`, delete removes a row — all columns exist in the v1 `todos` table (`id`/`text`/`completed`/`created_at`). No `db.py` migration is added; `_MIGRATIONS` is untouched and `user_version` **stays 1**. `priority`/`due_date`/etc. remain deferred to their own features.

---

## Alternatives Considered
- **Return the `Todo` from `_apply` (change its signature):** rejected — mutating the shipped `_apply(...) -> None` seam is riskier and weakens the "no call-site change at #9" guarantee. Carrying the result on `command.result` leaves the seam byte-for-byte compatible.
- **Enrich `EditRequested`/`DeleteRequested` with the todo text, or read it off the highlighted `TodoItem`:** rejected — the seams are fixed as `(todo_id)` and reading widget internals violates the `db → controller → widget` flow. A thin `controller.get_todo(id)` read is the layer-honest source and is independently testable.
- **`enter` handled via `ListView.Selected` message instead of overriding the binding:** viable, but a direct `Binding("enter","toggle")` keeps toggle uniform with `space` in one place. Kept `Selected` as the fallback if overriding the native binding proves awkward.
- **InputBar self-clears on submit:** rejected — on a persistence failure the typed text must survive for retry (per spec), so clearing is `MainScreen`-driven after confirmed success.
- **Commands in a separate `commands.py`:** viable for cohesion, but keeping the four small private command classes next to `_apply` in `controller.py` keeps the undo-seam narrative in one file. Split them out at #9 if the file grows.
