# UX Spec: Delete confirmation (Feature #5)

> Scope: deleting the focused task behind a modal confirmation — invocation (`d`),
> the `ModalScreen` dialog, default-safe focus, the dimmed backdrop, the post-delete
> cursor rule, and the result seam. Consistent with `main-screen.md`: bordered panels,
> theme tokens, `▸` cursor, footer-hint bar, symbol+color pairing. Relates to Feature
> #9 (undo) — see the copy note.

## References

- **k9s** — *delete pops a confirmation dialog with OK/Cancel; a well-known bug ([#961](https://github.com/derailed/k9s/issues/961)) was that Enter on the OK button *cancelled* — the default-button behavior was unintuitive.* We take the **lesson**: default focus goes to the **safe** (Cancel) option, and the confirm action is deliberate, never a stray Enter. ([commands](https://k9scli.io/topics/commands/))
- **taskwarrior-tui / taskwarrior** — *`x`/delete asks for confirmation before removing a task.* Confirms that destructive actions on a keyboard TUI get a confirm step, not a bare keypress. ([keybindings](https://kdheepak.com/taskwarrior-tui/keybindings/))
- **lazygit** — *destructive actions raise a centered confirmation popup over a dimmed panel, with `y`/`n` (or Enter/Esc); the popup shows *what* will be affected.* We borrow the **centered bordered popup that names the target** and the `y`/`n` + Enter/Esc keying.
- **Textual `ModalScreen`** — *traps input to the dialog, auto-dims the screen behind via a semi-transparent background, and returns a typed result through `dismiss(result)` → the `push_screen(screen, callback)` callback.* We build the dialog as `ModalScreen[bool]`. ([screens](https://textual.textualize.io/guide/screens/))

## Layout

Pressing `d` on the highlighted row dims the main screen and centers the dialog:

```
┌─ Inbox · 3 active · 1 done ──────────────────────────────────┐
│ ▸ [ ] Finish the quarterly report                            │   (dimmed 50% behind
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │    the modal — the
│ ░░░░░░░░░┌─ Delete task? ──────────────────────┐░░░░░░░░░░░░░ │    ModalScreen backdrop)
│ ░░░░░░░░░│                                      │░░░░░░░░░░░░░ │
│ ░░░░░░░░░│  Delete this task?                   │░░░░░░░░░░░░░ │
│ ░░░░░░░░░│                                      │░░░░░░░░░░░░░ │
│ ░░░░░░░░░│    "Finish the quarterly report"     │░░░░░░░░░░░░░ │  ← the task text, quoted
│ ░░░░░░░░░│                                      │░░░░░░░░░░░░░ │
│ ░░░░░░░░░│      [ Delete ]     « Cancel »       │░░░░░░░░░░░░░ │  ← « » marks focused btn
│ ░░░░░░░░░└──────────────────────────────────────┘░░░░░░░░░░░░░ │    (default = Cancel)
└──────────────────────────────────────────────────────────────┘
 y Delete   n / Esc Cancel                                          ← modal footer hint
```

- **Container:** a centered bordered panel `#confirm-dialog`, `border: round $error` (destructive = the one place we border in `$error`, echoing `main-screen.md`'s error role), `border-title` = `Delete task?`. Auto-sized to content, `max-width` ~50 so long titles wrap rather than stretch edge-to-edge.
- **Prompt line:** `Delete this task?` in `$text`.
- **Target line:** the task text in **double quotes**, `$text` (or `$text-muted`), truncated with `…` if it exceeds the dialog width (full text isn't needed to confirm identity). Quoting it is what makes the action concrete (lazygit "names the target").
- **Buttons:** two Textual `Button`s — `Delete` (`variant="error"`) and `Cancel` (`variant="default"`). The **focused** button is marked both by Textual's focus styling **and** the `« … »` bracket glyphs so the focus reads without color. **Default focus = `Cancel`** (the safe option — the k9s lesson).

### Copy note — do not over-promise permanence (Feature #9 relationship)

The controller's `delete_todo` returns the deleted `Todo` (the undo seam), and Feature #9 will make deletion undoable. But **undo is not built at #5**. So the #5 copy must be honest in both directions:

- **At Feature #5 (now):** the body is just `Delete this task?` + the quoted title. **Do not** write "permanently" (it will become false at #9) and **do not** write "This can be undone" (it is not true yet at #5).
- **At Feature #9 (later):** add a `$text-muted` sub-line `Esc to keep it · undo with u afterward` (or similar) once `u` exists. Flagged as a #9 follow-up, not a #5 deliverable.

## Default focus & keyboard flow

Default focus is on **Cancel**, so a reflexive Enter is safe (it cancels, not deletes).

| Key | Action | Notes |
| --- | --- | --- |
| `y` or `d` | Confirm delete immediately | Explicit affirmative; `d` = "yes, the thing I pressed d for." Works regardless of which button is focused. |
| `n` or `Esc` | Cancel | Explicit negative; `Esc` is the universal back-out (matches every other flow). |
| `←` / `→` / `Tab` / `Shift+Tab` | Move focus between `Cancel` and `Delete` | For mouse-averse users who prefer to focus-then-Enter. |
| `Enter` | Activate the **focused** button | Default focus is Cancel, so Enter-by-reflex cancels. Only cancels-or-deletes based on where focus is — never a hidden default. |

This gives two safe paths (`Esc`/`n`, and Enter-on-default-Cancel) and two explicit-delete paths (`y`/`d`, or Tab-to-Delete then Enter). Destruction always takes a deliberate act.

## Post-action focus & `▸` cursor rules (the critical part)

Let `i` be the `ListView.index` of the deleted row before deletion, and `N` the count before deletion.

**After confirm (row removed):**
1. `controller.delete_todo(todo_id)` → the item is removed; `MainScreen` refreshes the list.
2. **The cursor lands on the row that now occupies index `i`** — i.e. the **next** item slides up into the deleted slot, so the `▸` cursor ends up on what was the following task. This keeps the user moving *down* a list as they clear items (the natural "delete, delete, delete" rhythm).
3. **If the deleted row was the last one** (`i == N-1`), there is no next item: clamp the cursor to the **new last row** (`i-1`, the previous item).
4. **If the list is now empty** (`N` was 1): show `EmptyState` (with its `Press a to add…` CTA), hide `TodoList`, update the border-title to `Inbox · 0 active · 0 done`. Focus moves to the screen/`MainScreen` so `a`/`?`/`q` still work (the empty list can't hold a row cursor).
5. Focus returns to the `TodoList` (the modal is dismissed); the landing row lights to the **full focused highlight** with `▸`.
6. A `$success` toast confirms: `✓ Deleted "Finish the quarterly report"` (per `main-screen.md`'s success-toast role, symbol `✓` + word `Deleted`). Once Feature #9 lands, this toast is the natural place for an `undo with u` hint.

**After cancel:**
- Nothing is deleted; the modal dismisses; focus returns to the `TodoList`; **the same row stays highlighted** (`ListView.index` never changed), relighting to full focused highlight with `▸`. The user is exactly where they were.

> This matches `main-screen.md` §Edge Cases: "after delete, move the cursor to the next row (or previous if it was last); never leave it on a stale index. If the list becomes empty, show the Empty state." This spec makes that rule exact.

## Footer hints

| Context | Footer string |
| --- | --- |
| List focused (idle) | `a Add · ␣ Toggle · e Edit · d Delete · p Priority · ? Help · q Quit` |
| Delete modal open | `y Delete · n / Esc Cancel` |

The modal's own footer (inside the `ModalScreen`) shows the confirm/cancel keys; the main footer is dimmed behind the backdrop.

## States

Reactive/CSS the implementer toggles (no inline styling):

| State | Class / reactive | Visual |
| --- | --- | --- |
| **Idle** | modal not pushed | Feature #4 screen. |
| **Active (confirming)** | `ModalScreen` pushed; `#confirm-dialog` has `-danger` | Backdrop dimmed 50% (ModalScreen auto-background), dialog centered, `round $error` border, Cancel focused (`« Cancel »`). Input trapped to the dialog. |
| **Confirmed** | on `dismiss(True)` | Modal closes; row removed; cursor lands per the rule; `$success` toast. Local write is instant — no spinner. |
| **Cancelled** | on `dismiss(False)` | Modal closes; nothing changes; cursor unchanged. |
| **Error (persistence)** | controller `TasqueError` | Modal closes (or stays — see edge case); `app.notify(severity="error")` `$error` toast `Error: could not delete task`; the list keeps its last good render. |
| **Error (row already gone)** | `TodoNotFoundError` | Toast `Error: task no longer exists`; refresh the list; cursor clamps to a valid index. |

## Interaction flow & keybindings

| User action | System response | Keyboard | Mouse |
| --- | --- | --- | --- |
| Request delete | `TodoList` posts `DeleteRequested(current_todo_id)`; `MainScreen` pushes the modal, Cancel focused | `d` | click `d` footer hint |
| Confirm | `dismiss(True)`; `controller.delete_todo`; cursor lands per rule; success toast | `y` / `d` | click `[ Delete ]` |
| Move focus | Toggle focus Cancel↔Delete | `←`/`→`/`Tab` | hover/click |
| Activate focused | Delete or Cancel per focus | `Enter` | click |
| Cancel | `dismiss(False)`; nothing changes; same row stays highlighted | `n` / `Esc` | click `« Cancel »` |

## Message / seam names (for the implementer)

- **Intent (already exists):** `TodoList.DeleteRequested(todo_id)` — post from a new `Binding("d", ...)` on `TodoList` using `current_todo_id`. Seam defined in `todo_list.py`; only the binding + `action_` are new.
- **The dialog:** a new `DeleteConfirmScreen(ModalScreen[bool])` in `src/tasque/screens/` (one screen per file, `delete_confirm_screen.py` → `class DeleteConfirmScreen`, per CLAUDE.md). It takes the task text for display, returns `bool` via `dismiss(True|False)`.
- **Wiring:** `MainScreen.on_todo_list_delete_requested` does `self.push_screen(DeleteConfirmScreen(text), self._on_delete_confirmed)`. The callback, on `True`, calls `controller.delete_todo(todo_id)` then applies the cursor-landing rule and refreshes. Mutation stays in the controller (`controller.delete_todo`, seam present in `controller.py`); the widget/screen never imports `db.py`. The controller's `delete` returns the deleted `Todo` — the Feature #9 undo seam is preserved untouched.

## Edge cases

- **Delete the only row:** confirm → empty list → `EmptyState` shown with CTA; focus to `MainScreen`. Cancel → the single row stays highlighted.
- **Delete the last row (bottom of a multi-item list):** cursor clamps to the new last row (previous item), never a stale index past the end.
- **Delete the first row (top):** next item slides up to index 0; cursor stays at index 0 on it.
- **Rapid delete (`d` then instinctive `y`, repeated):** each cycle is push-modal → confirm → land-cursor → next `d`. Because the cursor lands on the *next* item, repeated `d y d y` clears items top-to-bottom fluidly. Each delete is one controller call (one future undo entry).
- **`d` on an empty list:** no highlighted row (`current_todo_id is None`) → no-op; optionally a `Nothing to delete` toast. The modal never opens on nothing.
- **Key spam inside the modal (mashing `y`):** the modal dismisses on the first `y`; subsequent keys hit the list behind (which may move the cursor) — harmless, no second delete fires because the modal is already gone.
- **Very long task text:** the quoted target line truncates with `…` inside the dialog; identity is still clear from the visible prefix.
- **Delete a completed (`-done`) task:** identical flow; the quoted text shows the plain title (no strike inside the dialog). Counts update (`done` decrements).
- **Terminal too small for the dialog:** `ModalScreen` centers and the dialog uses `max-width`/`auto` height; on a tiny terminal it shrinks and the target text truncates, but the buttons and title always render (never clip the confirm/cancel affordance).

## Accessibility

- **Keyboard-only path:** `j`/`k` to the row → `d` → `y` (delete) or `Esc`/`n` (cancel). Default-safe focus means an accidental `Enter` cancels. No mouse required.
- **Color-blind safety:** the destructive framing is carried by the **title word** `Delete task?`, the quoted target text, and the `[ Delete ]` / `« Cancel »` labels — not by the `$error` border alone. The focused button is marked with `« … »` glyphs, so focus reads in monochrome.
- **Screen reader:** `ModalScreen` announces as a dialog; the border-title `Delete task?` and the quoted task text give full context; buttons expose their labels (`Delete`, `Cancel`) and focus state. On confirm, the success toast text is announced.
- **Contrast:** `$text` on the dialog surface (Textual default ≥4.5:1); the `$error` border and the error-variant `Delete` button are decorative reinforcements, with meaning always duplicated in text.

## Open questions / assumptions

1. **Post-delete cursor = next item (clamp to previous at the end).** Chosen for the top-to-bottom "clear the list" rhythm. Flag if the architect prefers "stay on previous item" instead.
2. **Confirm keys `y` **and** `d`:** spec allows both (`d` = "yes, delete the thing I pressed d for"). Confirm `d`-as-confirm is wanted, or restrict to `y`/Enter-on-Delete only.
3. **Success toast wording + undo hint:** at #5 the toast is `✓ Deleted "…"`. The `undo with u` hint is deferred to Feature #9 (when `u` exists). Confirm the toast should stay for #5 (some prefer silent delete since the row visibly vanishes).
4. **Confirmation copy:** deliberately omits "permanently" and any undo promise at #5 (honest given #9 isn't built). Confirm the neutral wording; revisit at #9.
5. **Skip-confirm option:** k9s offers a no-confirm delete variant; not specified here. A future `D` (capital) = delete-without-confirm could be added if power users ask. Out of scope for #5.
