# UX Spec: InputBar — the Add flow (Feature #5)

> Scope: how adding a task looks and feels — the `InputBar` widget, its invocation
> (`a`), its docked position, the add-intent seam, and every state of the bar.
> Sibling specs: `edit-screen.md` (the `e` flow reuses this same bar) and
> `delete-confirmation.md` (the `d` flow). Stays consistent with `main-screen.md`:
> bordered panels with border-title context lines, semantic theme tokens (never hex),
> symbol+color pairing, the persistent footer key-hint bar, and `-highlight`/`-done`
> state-class conventions.

## References

- **taskwarrior-tui** — *`a` opens an add prompt on a single bottom line where you type the task and press Enter; `m` opens the same style of prompt pre-filled for modify.* We borrow the **bottom-docked, single-line prompt** as the one place text entry happens, and the idea that add and edit are the *same surface* in two modes (see `edit-screen.md`). ([keybindings](https://kdheepak.com/taskwarrior-tui/keybindings/))
- **lazygit** — *a persistent bottom prompt/command line and a footer of context-sensitive key hints that swaps to match the active mode.* We borrow the **bottom prompt line docked above the footer** and the **footer-hint swap** while the prompt is active.
- **k9s** — *the `:` command line docks at the bottom, is invoked by a single key, and is dismissed with Esc; the rest of the UI stays visible above it.* We borrow **modeless bottom entry** (the list stays visible and keeps its cursor context) rather than a full-screen takeover for the common "add a task" action. ([commands](https://k9scli.io/topics/commands/))
- **Textual `Input`** — *posts `Submitted` on Enter and `Changed` on each keystroke; `placeholder`, `value`, and `cursor_position` are reactive; focusing is `input.focus()`.* We build `InputBar` around one `Input`, mapping `Submitted` → add-intent and `Blurred`/`Escape` → cancel. ([Input](https://textual.textualize.io/widgets/input/))

## Design decision — docked bottom bar, not an inline row

**Decision: the InputBar is a bordered bar docked at the bottom of the screen, between the list panel and the Footer — not a row spliced into the list.**

Justification:
1. **The layout constraint forces it.** `TodoList` is a `ListView`, and `ListView` sets `can_focus_children=False` (see `edit-screen.md` for the full analysis). A literal in-row `Input` cannot take keyboard focus without a workaround. A docked bar lives *outside* the `ListView` subtree, so its `Input` focuses normally.
2. **Density stays intact.** `main-screen.md`'s principle #2 is one line per task. Splicing an editable row in would push rows around and break the "a screenful shows many tasks" density during the most frequent action.
3. **It matches every reference.** taskwarrior-tui, lazygit, and k9s all put transient text entry on a docked bottom line while the list stays visible above — so the user keeps their place.

The bar is its own bordered panel (a lazygit-style titled box), so it reads as the same product as the list panel above it. It occupies **3 rows** when active (top border+title, the input line, bottom border) and **0 rows** when idle (`display: none`), so idle screens are unchanged from Feature #4.

## Layout

Idle (Feature #4 main screen, unchanged — the bar is not mounted-visible):

```
┌─ Inbox · 3 active · 1 done ──────────────────────────────────┐
│ ▸ [ ] Finish the quarterly report                            │
│   [ ] Buy groceries                                          │
│   [x] Water the plants                                       │
│                          (free space)                        │
└──────────────────────────────────────────────────────────────┘
 a Add   ␣ Toggle   e Edit   d Delete   p Priority   ? Help   q Quit
```

Active (after pressing `a`) — the bar slides in below the list, the list keeps its cursor:

```
┌─ Inbox · 3 active · 1 done ──────────────────────────────────┐
│ ▸ [ ] Finish the quarterly report                            │  ← ▸ cursor retained,
│   [ ] Buy groceries                                          │    row now shows the
│   [x] Water the plants                                       │    blurred-highlight dim
│                          (free space)                        │    (list is blurred)
└──────────────────────────────────────────────────────────────┘
┌─ New task ───────────────────────────────────────────────────┐  ← border-title = mode label
│ › Add a task and press Enter…                                │  ← placeholder ($text-muted)
└──────────────────────────────────────────────────────────────┘
 ⏎ Add task   Esc Done
```

- **Border title:** `New task` (the mode label). Add mode only; the edit flow (`edit-screen.md`) swaps this to `Edit task`. The label — not color — is what tells add from edit.
- **Prompt glyph:** a leading `› ` (paired with the accent border) marks the input line, echoing the list's `▸` cursor language without colliding with it. ASCII fallback `> ` on terminals lacking `›`.
- **Placeholder:** `Add a task and press Enter…` in `$text-muted`. Disappears as soon as the user types (Textual `Input` placeholder behavior).
- **Border:** `round $accent` when the input holds focus (mirrors the list panel's focused `round $primary`; accent distinguishes "you are typing here" from "the list is here").

## Invocation, confirm, and dismiss

| Trigger | Behavior |
| --- | --- |
| `a` (on `MainScreen`, list focused) | Mount/show the bar in **add mode**, clear its value, `input.focus()`. The list blurs (keeps `▸` at its dim-highlight). |
| `Enter` (bar focused, non-empty) | Post the add intent; the new todo is created via the controller; the bar **stays open and clears** for the next entry (see decision below). |
| `Enter` (bar focused, empty/whitespace) | No-op. The bar stays open; a brief `$error` border pulse + footer hint signals "nothing to add" (see States → Error). Nothing is persisted. |
| `Esc` (bar focused) | Close the bar (`display: none`), return focus to the `TodoList`, re-focus the row that was highlighted (its `▸` returns to the full focused highlight). |
| `Tab` (bar focused) | **Inert** — no-op (the bar is a single field; it does *not* close, unlike `Esc`). Per the canonical app-wide `Tab` convention in `main-screen.md § Accessibility & Degradation`; reserved for a future multi-field add. |

### Decision — Enter keeps the bar open for rapid multi-add

**Decision: after a successful add, the bar stays open and clears so the user can type the next task immediately. `Esc` is the single, explicit way to leave add mode.**

Justification: Feature #5 is "the core interaction loop," and the dominant first-run action is entering *several* tasks in a row (the empty state literally exists to bootstrap a fresh list). Forcing a re-press of `a` between every task triples the keystrokes for bulk capture. This is the "quick-capture" pattern common to task tools, and it keeps the flow: `a` → type → `⏎` → type → `⏎` → `Esc`. The cost — the bar doesn't auto-dismiss — is made obvious by the footer hint reading `Esc Done` (not `Esc Cancel`) once at least one task has been added this session.

> Open question flagged for the architect: some users expect Enter to close (single-shot add). If preferred, this is a one-line behavior change (dismiss on Submitted). The spec picks stay-open because bulk capture is the #5 use case; edit mode (`edit-screen.md`) explicitly closes on Enter since you edit one item at a time.

## Live-update behavior — where the new row lands and where the cursor goes

On a successful add:
1. `InputBar` posts its submit message; `MainScreen` calls `controller.add_todo(text)` → returns the persisted `Todo`.
2. `MainScreen.refresh_todos()` runs (or a targeted append): the new row appears **at the bottom of the list** (controller returns todos in creation order — `main-screen.md` §Populated: default is creation order).
3. **The list's `▸` cursor moves to the new row** so it is visibly confirmed, but because the bar still holds focus the row shows the **blurred-highlight dim** (per `main-screen.md`: `▸` retained, muted `$boost` tint). When the user finally `Esc`s, focus returns to the list and that row lights to the full focused highlight.
4. The panel border-title count updates live: `Inbox · 4 active · 1 done`.

This gives immediate feedback (the row exists, the cursor points at it) without stealing focus from the still-open bar.

## Relationship to the EmptyState CTA

`EmptyState` already exposes a `cta` reactive seam (Feature #4). Feature #5 sets it:

```
empty_state.cta = "Press  a  to add your first task"
```

which renders (per `EmptyState.watch_cta`):

```
┌─ Inbox · 0 active · 0 done ──────────────────────────────────┐
│                                                              │
│                        No tasks yet                          │
│              Press  a  to add your first task                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
 a Add   ? Help   q Quit
```

- The `a` in the CTA is styled like a footer key (matching `main-screen.md` §Empty). Pressing `a` from the empty state opens the InputBar exactly as it does from a populated list; the first successful add hides `EmptyState`, shows `TodoList`, and lands the cursor on the new row.
- **No focus trap on empty:** with zero rows the list can't be navigated, but `a` (a `MainScreen` binding, not a list binding) still works, so the empty state is never a dead end.

## Footer hints

The footer swaps to match the mode (lazygit convention), using `main-screen.md`'s `key  label · …` style:

| Context | Footer string |
| --- | --- |
| List focused (idle) | `a Add · ␣ Toggle · e Edit · d Delete · p Priority · ? Help · q Quit` |
| Add bar active, empty | `⏎ Add task · Esc Cancel` |
| Add bar active, ≥1 added this session | `⏎ Add task · Esc Done` |

`⏎` denotes Enter. The swap is driven by the same reactive that shows the bar, so hints never lie about the current mode.

## States

Reactive/CSS surface the implementer toggles (no inline styling):

| State | Reactive / class | Visual |
| --- | --- | --- |
| **Idle** | `InputBar` has `-hidden` (`display: none`) | Bar not visible; Feature #4 screen unchanged. |
| **Active (add)** | `-hidden` removed; `mode = "add"` | Bordered bar, title `New task`, `round $accent` border, placeholder in `$text-muted`, `input.focus()`. |
| **Typing** | `Input.Changed` fires | Placeholder gone, live text in `$text`, cursor block. No validation gating per keystroke. |
| **Submitting** | on `Input.Submitted` | Local SQLite write is effectively instant, so **no spinner**. The row appears and the field clears in the same frame. (Matches `main-screen.md` §Loading: no skeletons for a local DB.) |
| **Error (empty submit)** | class `-invalid` added for ~600ms then removed | Border pulses `$error`; footer/inline hint `Empty — type a task first`. The word plus color (not color alone) carries the meaning. Nothing persists; the bar stays open. |
| **Error (persistence)** | controller raises `TasqueError` | Controller catches it and calls `app.notify(..., severity="error")` — a `$error` toast prefixed `Error:` (per `main-screen.md` §Error). The bar stays open with the typed text intact so the user can retry; the list keeps its last good render. |

## Interaction flow & keybindings

| User action | System response | Keyboard | Mouse |
| --- | --- | --- | --- |
| Open add bar | Show bar (add mode), blur list, focus input | `a` | click `a` footer hint |
| Type | Live text; placeholder clears | any text | — |
| Confirm add | `controller.add_todo`; row appended; cursor → new row; bar clears, stays open | `Enter` | — |
| Reject empty | `-invalid` pulse; no persist | `Enter` on empty | — |
| Leave add mode | Close bar; focus returns to list; highlighted row lights fully | `Esc` | click a list row |
| Move cursor while bar open | Blocked — the bar holds focus; list keys do nothing until `Esc` | — | — |

## Message / seam names (for the implementer)

The add intent is the InputBar's own concern (the reserved `TodoList.EditRequested` seam is for the *edit* flow, not add). Define on `InputBar`:

- `InputBar.Submitted(value: str, mode: str)` — posted on Enter with non-empty, trimmed text. `mode` is `"add"` or `"edit"` so one handler on `MainScreen` serves both flows.
- `InputBar.Cancelled(mode: str)` — posted on Esc.

`MainScreen` handles `InputBar.Submitted`: for `mode == "add"` it calls `controller.add_todo(value)` then refreshes. All mutation stays in the controller (CLAUDE.md); the widget never imports `db.py`. The controller's `add_todo` seam already exists (`controller.py`) awaiting implementation.

Reactive attributes on `InputBar` the implementer will toggle: `mode: reactive[str]` (`"add"`/`"edit"`), plus a boolean drive for the `-hidden`/`-invalid` classes. Editing pre-fill (`value`, `cursor_position`) is covered in `edit-screen.md`.

## Edge cases

- **Whitespace-only input:** trimmed to empty → treated as the empty-submit no-op. Never create a blank task.
- **Very long input:** the `Input` scrolls horizontally within the bar (native Textual `Input`). The stored text is untruncated; the list row truncates with `…` on display (per `main-screen.md`).
- **Key spam (mashing `⏎`):** each non-empty Enter is one add; the field clears between them, so a held Enter on an empty field is a stream of harmless no-ops. Adds route through the controller so Feature #9 can record each.
- **`a` pressed while a modal (delete confirm) is open:** the modal traps input (`ModalScreen`), so `a` does nothing until the modal is dismissed. No stacked bars.
- **10,000 rows, then add:** the new row appends; auto-scroll brings the cursor into view. Refresh is one `list_todos()` read, not a per-row rebuild (per `main-screen.md` perf note).
- **Terminal too short for 3 extra rows:** the list panel yields height to the docked bar (Textual vertical layout); the list scrolls. The bar is never clipped — text entry always fully visible.

## Accessibility

- **Keyboard-only path:** `a` → type → `⏎` (repeat) → `Esc`. No mouse needed; `Esc` always backs out to the list.
- **Color-blind safety:** mode is the border **title word** (`New task`); the error state is the **word** `Empty…` plus the `-invalid` pulse, never hue alone. The prompt glyph `›` marks the input line independent of color.
- **Screen reader:** the bar's border-title (`New task`) names the mode; the `Input` exposes its placeholder as an accessible prompt. On successful add, the cursor moving to the new row triggers the list's `Highlighted` announcement (per `main-screen.md`).
- **Contrast:** `$text` on `$surface` for typed text (Textual theme default, ≥4.5:1); the `$accent` border is decorative, not load-bearing for meaning.

## Open questions / assumptions

1. **Stay-open vs. close on Enter (add mode):** spec chose **stay-open for rapid multi-add**, `Esc` to leave. Flag if the architect prefers single-shot (close on Enter). One-line change.
2. **`Tab` in the bar:** ~~open question~~ **resolved** — `Tab` is inert (no-op), per the canonical app-wide `Tab` convention now documented in `main-screen.md § Accessibility & Degradation`. Reserved for a future multi-field add (priority/due inline).
3. **New-row placement:** assumed **append at bottom** (creation order, per `main-screen.md`). If Feature #6's priority sort later reorders, an added row may jump position after refresh — acceptable, but flag for #6's design.
4. **Bar position when the terminal is very short:** assumed the list yields height and scrolls. Confirm no minimum list height is required.
