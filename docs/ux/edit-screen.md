# UX Spec: Edit flow (Feature #5)

> Scope: editing the focused task's text — invocation (`e`), the focus constraint,
> the three candidate approaches, the chosen approach fully specified, and the
> result seam. Reuses the `InputBar` defined in `input-bar.md`. Consistent with
> `main-screen.md`: bordered panels, theme tokens, `▸` cursor, footer-hint bar,
> `-highlight`/`-done` conventions.

## References

- **taskwarrior-tui** — *`m` (modify) opens the same bottom-line prompt as add, but **pre-filled** with the selected task so you edit and press Enter.* This is the model we adopt: edit is add-mode's twin on the same docked surface. ([keybindings](https://kdheepak.com/taskwarrior-tui/keybindings/))
- **lazygit** — *rename/edit actions open the docked bottom prompt pre-populated with the current value; Esc cancels, Enter confirms.* Confirms the "reuse the one prompt line, pre-filled" pattern.
- **Textual `Input`** — *`value` and `cursor_position` are writable reactives, so a pre-filled field with the caret placed deliberately is native.* ([Input](https://textual.textualize.io/widgets/input/))
- **Textual `ListView`** — *sets `can_focus_children=False`, so widgets mounted **inside** a list item cannot take keyboard focus.* This is the hard constraint the whole decision turns on.

## The hard constraint

`TodoList` is a `ListView` subclass, and `ListView.can_focus_children = False`. That flag means **any `Input` mounted inside a `TodoItem` row will not accept keyboard focus** — Textual routes keys to the `ListView` itself, not to descendants of its items. So the naive "swap the row's title `Static` for an `Input` in place" does not work without deliberately overriding focus behavior, and fighting the framework here risks breaking the cursor/highlight model that Feature #4 already ships.

## Three options weighed

### (a) Modal edit screen (`ModalScreen` with a centered input)
- **Pros:** focus trapping is free (`ModalScreen`); no interaction with `can_focus_children`; a clean `dismiss(result)` seam.
- **Cons:** heavyweight for a one-field text tweak. Dims the whole list, so you **lose sight of the row you're editing** and its neighbors — the opposite of taskwarrior-tui's in-context feel. Inconsistent to have edit be a full-screen modal while add is a docked bar; two different surfaces for two nearly identical actions. Overkill.

### (b) Inline-edit via the InputBar (reuse the docked bottom bar, pre-filled) — **CHOSEN**
- **Pros:** **sidesteps the constraint entirely** — the `Input` lives in the docked `InputBar` (outside the `ListView` subtree), where it focuses normally. **One surface, two modes** — add and edit share the bar, the seam, and the muscle memory (matches taskwarrior-tui `a`/`m`). The list stays visible above with its `▸` cursor still pointing at the row being edited (blurred-highlight dim), so context is preserved. Minimal new code — the bar already exists from the add flow.
- **Cons (the trade-off accepted):** the edit does **not happen literally on the row** — the text you're changing appears at the bottom of the screen, a few rows away from the highlighted item. We mitigate this by (1) keeping the row's `▸` cursor visibly anchored at the item, and (2) titling the bar `Edit task` so the mode is unambiguous.

### (c) Floating/overlay input positioned over the row
- **Pros:** looks the most "in place."
- **Cons:** Textual has no first-class "anchor an overlay to a moving list row" primitive; you'd compute the row's screen offset and reposition on scroll/resize — fragile, and still bumping against focus routing near the `ListView`. High effort, high breakage risk, for a cosmetic gain over (b).

## Decision

**Chosen: (b) inline-edit via the InputBar — reuse the docked bottom bar, pre-filled with the task text.**

One-line justification: it sidesteps `ListView.can_focus_children=False` by editing outside the list subtree while keeping the row visible and cursor-anchored, and it makes edit the mirror of add on one shared surface (taskwarrior-tui's `a`/`m` model).

Trade-off explicitly accepted: editing happens in the bottom bar, not on the row itself; the row's retained `▸` cursor and the `Edit task` title are how we keep the user oriented.

> Reconciliation note (flagged): `main-screen.md`'s keybinding table calls `e` "inline-edit the cursor row's title." We interpret "inline" as **modeless bottom-bar editing** (the list stays live above), not a modal and not literally in-row. This is a realization of that intent, not a contradiction — but the architect should confirm the wording is acceptable, or `main-screen.md` should be nudged to say "edit via the docked bar."

## Layout

Pressing `e` on the highlighted row:

```
┌─ Inbox · 3 active · 1 done ──────────────────────────────────┐
│ ▸ [ ] Finish the quarterly report                            │  ← ▸ retained; row shows
│   [ ] Buy groceries                                          │    blurred-highlight dim
│   [x] Water the plants                                       │    (list blurred)
└──────────────────────────────────────────────────────────────┘
┌─ Edit task ──────────────────────────────────────────────────┐  ← title = mode label
│ › Finish the quarterly report█                               │  ← pre-filled, caret at END
└──────────────────────────────────────────────────────────────┘
 ⏎ Save   Esc Cancel
```

- **Border title:** `Edit task` (vs. add mode's `New task`). The **word** distinguishes the mode, not color; the border stays `round $accent`.
- **Pre-filled value:** the current task text, loaded via `input.value = todo.text`.
- **Caret position:** placed at the **end of the text** (`cursor_position = len(text)`) — the common case is appending or tweaking the tail. The full text is selectable/navigable with normal `Input` keys (`Home`/`End`/arrows).
- The bar is the *same* `InputBar` widget as the add flow, in `mode = "edit"` with `editing_id` set.

## Invocation, confirm, cancel

| Trigger | Behavior |
| --- | --- |
| `e` (list focused, a row highlighted) | `TodoList` posts `EditRequested(current_todo_id)`. `MainScreen` opens the bar in **edit mode**, sets `value` = the todo's text, caret at end, `input.focus()`. The list blurs, row keeps `▸` at dim-highlight. |
| `e` (empty list) | No-op (no highlighted row → `current_todo_id is None`). Optionally a `$text-muted` toast `Nothing to edit`. |
| `Enter` (non-empty, changed) | Post the submit intent; `controller.edit_todo(editing_id, text)`; the row re-renders in place; **the bar closes** (edit is one-at-a-time). Focus returns to the list, row lights to full focused highlight. |
| `Enter` (non-empty, unchanged) | Treated as a confirm no-op: close the bar, no controller call (nothing changed), focus returns. Cheap and non-surprising. |
| `Enter` (empty/whitespace) | **Rejected** — an empty edit is not a delete. `-invalid` border pulse + hint `Task text can't be empty`; the bar stays open with the text for the user to fix. Nothing persists. |
| `Esc` | Cancel: discard the edit, close the bar, focus returns to the list, the row is unchanged and lights to full focused highlight. |

### What persists, and when

- Persistence happens **only on `Enter` with non-empty, changed text**, via `controller.edit_todo` → `db.update`. There is no live/per-keystroke save (avoids partial writes and keeps Feature #9's undo one command per confirmed edit).
- On success the controller returns the updated `Todo`; `MainScreen` calls `todo_list.update_todo(updated)` (the existing single-row re-render seam) so the row refreshes **without** rebuilding the whole list and **without** moving the cursor (`update_todo` preserves `index`).

### Where focus and the `▸` cursor return

- **After confirm or cancel:** focus returns to the `TodoList`; the **same row stays highlighted** (the `▸` cursor never left it — it was dim during the edit and relights). `update_todo` explicitly does not change `ListView.index`, so the user lands exactly where they were. This matches `main-screen.md` §"Modal close returns focus to last list item" reasoning — never disorient the user after editing item 47.

## Footer hints

| Context | Footer string |
| --- | --- |
| List focused (idle) | `a Add · ␣ Toggle · e Edit · d Delete · p Priority · ? Help · q Quit` |
| Edit bar active | `⏎ Save · Esc Cancel` |
| Edit bar active, empty (invalid) | `Task text can't be empty · Esc Cancel` |

Note the label is `Save` (not `Add task`) so the mode reads correctly in the footer, matching lazygit's mode-sensitive hint swap.

## States

Reactive/CSS the implementer toggles (no inline styling; the bar shares `input-bar.md`'s classes):

| State | Reactive / class | Visual |
| --- | --- | --- |
| **Idle** | bar has `-hidden` | Not visible; Feature #4 screen. |
| **Active (edit)** | `-hidden` removed; `mode = "edit"`; `editing_id` set | Bordered bar, title `Edit task`, `round $accent`, value pre-filled, caret at end, focused. Edited row shows blurred-highlight dim with `▸`. |
| **Typing** | `Input.Changed` | Live text in `$text`. |
| **Submitting** | on `Submitted` | Instant local write; `update_todo` re-renders the one row; bar closes same frame. No spinner. |
| **Error (empty edit)** | `-invalid` pulse (~600ms) | `$error` border pulse + word `Task text can't be empty`. Bar stays open; nothing persists. |
| **Error (persistence)** | controller `TasqueError` | `app.notify(severity="error")` `$error` toast prefixed `Error:`; bar stays open with text intact; the row keeps its old value. |
| **Error (row deleted mid-edit)** | `TodoNotFoundError` from controller | Toast `Error: task no longer exists`; close the bar; refresh the list. (Edge case below.) |

## Interaction flow & keybindings

| User action | System response | Keyboard | Mouse |
| --- | --- | --- | --- |
| Start edit | `EditRequested`; bar opens pre-filled, list blurs | `e` | click `e` footer hint |
| Edit text | Live text; `Home`/`End`/arrows navigate the value | text keys | — |
| Confirm | `controller.edit_todo`; `update_todo`; bar closes; focus + `▸` return to same row | `Enter` | — |
| Reject empty | `-invalid` pulse; stays open | `Enter` on empty | — |
| Cancel | Discard; bar closes; row unchanged; focus + `▸` return | `Esc` | click a list row |

## Message / seam names (for the implementer)

- **Intent (already exists):** `TodoList.EditRequested(todo_id)` — post this from a new `Binding("e", ...)` on `TodoList`, using `current_todo_id`. The seam is defined in `todo_list.py`; only the binding and the `action_` that posts it are new.
- **The bar:** reuse `InputBar` in `mode = "edit"` with an `editing_id: int | None` attribute; it posts `InputBar.Submitted(value, mode="edit")` and `InputBar.Cancelled(mode="edit")` (defined in `input-bar.md`). `MainScreen`'s single `on_input_bar_submitted` handler branches on `mode`: `"edit"` → `controller.edit_todo(bar.editing_id, value)` → `todo_list.update_todo(result)`.
- **Mutation stays in the controller** (`controller.edit_todo`, seam already present in `controller.py`); the widget never touches `db.py`. This keeps Feature #9's undo hook in one place.

## Edge cases

- **Unchanged text + Enter:** no controller call, bar closes — avoids a no-op undo entry and a pointless write.
- **Editing a completed (`-done`) row:** allowed. The bar shows plain text (no strike); on save the row re-renders and re-applies `-done` (still completed). Completion state is untouched by an edit.
- **Row deleted or DB-changed while the bar is open:** on Enter the controller raises `TodoNotFoundError`; catch → error toast, close bar, refresh. (In a single-user local app this is rare, but the seam must not crash.)
- **Very long edit:** the `Input` scrolls horizontally; stored text is untruncated; the list row truncates with `…`.
- **`e` pressed with a modal open (delete confirm):** the modal traps input; `e` does nothing until dismissed.
- **`e` on an empty list:** no highlighted row → no-op (optionally a `Nothing to edit` toast).
- **Key spam / double `e`:** the bar is already open on the second `e`; since the list is blurred, the second `e` goes to the `Input` as a literal character (types "e"). Acceptable and expected — you're in a text field.

## Accessibility

- **Keyboard-only path:** `j`/`k` to the row → `e` → edit → `⏎` (save) or `Esc` (cancel). Focus returns to the same row every time.
- **Color-blind safety:** mode is the title **word** `Edit task`; the empty-edit error is the **word** `Task text can't be empty` plus the `-invalid` pulse — never hue alone.
- **Screen reader:** the bar's border-title announces `Edit task`; the pre-filled `Input` reads its current value; on save, the row's re-render triggers the list's `Highlighted` announcement with the new text.
- **Contrast:** `$text` on `$surface` for the field (Textual default ≥4.5:1); the retained `▸` on the dim-highlighted row keeps the edit target locatable without relying on the accent fill.

## Open questions / assumptions

1. **"Inline" wording:** we realize `main-screen.md`'s "inline-edit" as **docked-bar edit**. Confirm acceptable or update `main-screen.md`'s keybinding-table wording. (Flagged above.)
2. **Caret at end vs. select-all:** spec chose **caret at end** (append/tweak is the common case). Alternative is select-all-on-open (fast full replace). Confirm the default; select-all could be a later refinement.
3. **Unchanged-text Enter:** treated as a silent confirm/no-op (no write, no undo entry). Confirm this is preferred over always writing.
4. **Empty-edit semantics:** spec **rejects** empty (an edit is never a delete). Confirm deletion is reserved to the explicit `d` flow (`delete-confirmation.md`).
