# UX Spec: Main Screen (TodoList + TodoItem)

> Scope: the main screen layout, the `TodoList` widget, and the `TodoItem` widget.
> Built against by Features #4 (main screen + TodoList/TodoItem), #5 (InputBar: add/toggle/edit/delete),
> and #6 (priority). Due-date (#7) and category (#8) visuals are **reserved** in the row layout here so the
> implementer leaves room, but are explicitly marked "not built until #7/#8" — do not build them early.

## References

- **lazygit** — *bordered panels with a title + count in the border, an always-visible bottom key-hint bar, and vim-style `j/k` navigation with `g/G` jumps.* We borrow the titled-border panel (list name + counts live in the border), the persistent footer of context-sensitive key hints, and the `?` full-help overlay convention. (Lazygit's views are boxes with consistent per-context keybindings shown in the footer.)
- **k9s** — *a header/breadcrumb context line above the list, dense single-line rows, color-coding by state, and `/` to filter / `:` for command mode.* We borrow the context line ("which list am I in, how many items"), one-line-per-item density, and reserving `/` for filtering. k9s pairs a status word with its color (Running/Terminating/Error) rather than relying on hue alone — we copy that "symbol/word + color" pairing.
- **taskwarrior-tui** — *the closest analog: a task table with priority and due columns, urgency-driven coloring, and a cursor row that is the thing actions apply to.* We borrow: the cursor row **is** the selection (single-item action target), priority shown as a short tag, due dates shown relative, and overdue items visually escalated. taskwarrior-tui shows priority/due/urgency as columns and colors overdue/high-urgency rows; we adapt that to a single flex row.
- **Textual `ListView`** — *built-in vertical list of `ListItem`s with a reactive `index` "highlighted" cursor, `Highlighted`/`Selected` messages, and default `up`/`down`/`enter` bindings.* We build `TodoList` on `ListView` so the cursor/highlight model, focus styling (`:focus`), and keyboard plumbing come for free; each `ListItem` wraps one `TodoItem` widget.

## Design Principles

1. **Keyboard-first, mouse-optional.** Every action has a key. The mouse may click a row to move the cursor and click the footer, but nothing *requires* it.
2. **One line per task (density).** Like k9s and taskwarrior-tui, a task is a single row so a screenful shows many tasks. No multi-line cards.
3. **The cursor is the selection.** There is exactly one "current" task — the highlighted row. All single-item actions (toggle/edit/delete/priority) act on it. Multi-select is explicitly out of scope for #4–#6 (reserved: `space`-to-mark is a future idea; here `space` toggles completion).
4. **Color is an enhancement, never the only signal.** Every state that uses color also uses a symbol, a text tag, or a style (dim/strike) so the screen is fully legible in monochrome and to color-blind users.
5. **Theme-token styling, in CSS only.** Colors are Textual theme variables (`$primary`, `$error`, …) declared in `tasque.tcss`, so the app adapts to Textual's dark and light themes automatically. No inline color mutation — state is expressed via CSS classes toggled as reactive state (`-done`, `-overdue`, `-priority-high`, …).

## Layout

Full main screen. Three stacked regions: **Header** (top, 1 row), **List panel** (flex, fills remaining height), **Footer** (bottom, 1 row). A context/breadcrumb line sits just inside the list panel's top border (lazygit-style border title), so it costs no extra row.

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Tasque                                                          2026-06-29   │  ← Header (Textual Header): app title + clock
├─ Inbox · 3 active · 1 done ────────────────────────────────────────────────┤  ← List panel border title (active list + counts)
│ ▸ [ ] (H) Finish the quarterly report               #work        due today   │  ← cursor row (highlighted)
│   [ ] (M) Buy groceries                              #home        06-30       │
│   [ ] (!) Renew passport                             #admin       OVERDUE 06-20│  ← overdue (escalated)
│   [x] (L) Water the plants                           #home        ──          │  ← done (dimmed + strike)
│   [ ]     Read Textual docs                                                   │  ← no priority, no category, no due
│                                                                              │
│                                  (free space)                                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
 a Add   ␣ Toggle   e Edit   d Delete   p Priority   ? Help   q Quit            ← Footer (Textual Footer): key hints
```

### Region allocation
- **Header** — fixed `height: 1`. Textual `Header()` (left: title "Tasque"; right: clock, optional). Provides the app's identity; no interaction.
- **List panel** — `height: 1fr` (consumes everything between header and footer). A bordered container (`border: round $primary;` focused, `$panel`/muted when blurred) whose `border-title` holds the **context line**: `"{list name} · {N} active · {M} done"`. The `TodoList` (`ListView`) scrolls inside it.
- **Footer** — fixed `height: 1`. Textual `Footer()` rendering the visible `BINDINGS`. Mirrors lazygit/k9s: `key  label` pairs, separated by spacing, in priority order.

### Per-row column layout (the `TodoItem` anatomy)
Left-to-right, single line:

```
 ▸ [x] (H) <title text, flexes to fill>           #category        <due>
 └┬┘ └┬┘ └┬┘ └──────────┬───────────┘             └───┬───┘        └─┬─┘
cursor│   │            title (1fr, ellipsis on overflow)            due (right)
   checkbox  priority                          category tag
```

| Slot | Width | Content | Lands in |
| --- | --- | --- | --- |
| Cursor gutter | 2 | `▸ ` on the highlighted row, blank otherwise | #4 (via ListView highlight) |
| Checkbox | 4 | `[ ]` open / `[x]` done | #4 |
| Priority tag | 4 | `(H)`/`(M)`/`(L)`/`(!)`, or blank for none | #6 |
| Title | `1fr` | task text; truncate with `…` when narrow | #4 |
| Category tag | auto | `#name`, right-grouped, dim | **#8 — reserve space, do not build now** |
| Due | auto (~10) | relative/abs date, right-aligned | **#7 — reserve space, do not build now** |

> For #4 only the cursor gutter, checkbox, and title render. For #6 the priority tag activates. The category and due slots stay empty until #8/#7; the layout already accommodates them (right-aligned group), so adding them later is non-breaking.

### Resize / narrow terminals
- The title slot is the only flexible (`1fr`) column; it absorbs/yields width. It truncates with an ellipsis (`text-overflow: ellipsis`) rather than wrapping — density principle.
- **< ~50 cols:** drop the due and category slots first (they are right-aligned and optional), then the priority tag's parentheses can stay (it is only 4 cols). The checkbox + title always survive.
- **Very short height:** the `ListView` scrolls; the header and footer are pinned. There is no minimum item count assumption.
- The context line in the border truncates from the right (`Inbox · 3 active …`) if the terminal is too narrow to show full counts.

## TodoList Widget

A `ListView` subclass. Renders one `ListItem` per `Todo`, each `ListItem` containing one `TodoItem` widget. Data arrives from the **controller** (`controller.list_todos()` → `list[Todo]`); the widget never imports `db.py`.

- **Source of truth:** the widget holds no persistent copy of task data — it rebuilds (or diff-updates) its children from the controller's dataclasses. Ephemeral UI state it *does* own: which row is highlighted (the `ListView.index`) and any in-progress inline edit.
- **Cursor / highlight model:** `ListView`'s reactive `index` is the single "current" task. Moving the cursor posts `ListView.Highlighted`; the parent screen reads `highlighted_child` to know the target of the next action. There is no separate multi-selection in this spec.
- **Focus vs. highlight (the two distinct concepts):**
  - **Focus** = does the `TodoList` widget hold keyboard focus (Textual `:focus`). Only one widget in the app is focused. When focus moves to the InputBar (#5) or a modal, the list is *blurred*.
  - **Highlight** = which row the cursor sits on *within* the list. It persists even when the list is blurred.
  - Visual distinction: a **focused + highlighted** row gets the full accent background and the `▸` cursor; a **blurred + highlighted** row keeps the `▸` cursor but the background dims to a muted tint (so the user still sees where they'll return). This mirrors lazygit dimming the inactive panel's selection.
- **Scrolling:** native `ListView` scrolling; the highlighted row stays in view (auto-scroll on `cursor_up`/`cursor_down`). Page and top/bottom jumps supported (see keybindings).
- **Communication upward:** the list never mutates data. User intents become Textual **`Message` subclasses** posted to the screen/controller (e.g. `TodoList.ToggleRequested(todo_id)`, `EditRequested`, `DeleteRequested`, `PriorityCycleRequested`). The controller performs the mutation and the list refreshes. This keeps the undo seam (#9) in the controller.

### Empty vs. populated
- **Populated:** the `ListView` of rows as above.
- **Empty:** the `ListView` is replaced (or overlaid) by a centered empty-state block inside the same panel — see *States → Empty*. The context line reads `Inbox · 0 active · 0 done`.

## TodoItem Widget

One row, composed of the slots in the layout table. Stateless re: persistence — it is given a `Todo` dataclass and renders it. State is expressed through **CSS classes** toggled from the bound `Todo`'s fields (reactive), never inline styles:

| `Todo` field → | CSS class on the row | Visual effect |
| --- | --- | --- |
| `completed=True` | `-done` | checkbox `[x]`, title dimmed + strikethrough, priority/category/due dimmed |
| `priority == high` | `-priority-high` | priority tag `(H)` colored `$error` |
| `priority == medium` | `-priority-medium` | `(M)` colored `$warning` |
| `priority == low` | `-priority-low` | `(L)` colored `$primary`/muted |
| `priority is None` | *(none)* | priority slot blank |
| `due_date < today` & not done | `-overdue` | due shown as `OVERDUE <date>`, colored `$error`, bold (**#7**) |
| `due_date == today` & not done | `-due-today` | due shown as `due today`, colored `$warning` (**#7**) |

The checkbox glyphs are plain ASCII (`[ ]` / `[x]`) for maximum terminal compatibility (see Degradation). Priority uses letter tags, not just color, so completion and priority read in monochrome.

## Color Scheme

Declared as Textual theme tokens in `tasque.tcss` so dark/light themes both work without a second palette. Concrete hex shown for Textual's default **dark** and **light** themes for reference; the implementer should reference the **token**, not the hex, so theme switching Just Works.

| Role | Token | Dark (ref) | Light (ref) | Paired non-color signal |
| --- | --- | --- | --- | --- |
| Screen background | `$background` | `#1e1e2e`-ish | `#f5f5f5`-ish | — |
| Panel surface | `$surface` / `$panel` | dark grey | light grey | — |
| Default text | `$text` | near-white | near-black | — |
| Muted / metadata (category, dates) | `$text-muted` | dim grey | dim grey | tag prefix `#`, label `due` |
| Done text | `$text-disabled` | dimmest | dimmest | `[x]` + strikethrough |
| Cursor / focus highlight (focused) | `$accent` (bg) on `$text` | accent fill | accent fill | `▸` cursor glyph |
| Cursor highlight (blurred list) | `$boost` / muted tint | faint fill | faint fill | `▸` cursor glyph |
| Panel border (focused) | `$primary` | accent | accent | thicker `round` border + title |
| Panel border (blurred) | `$panel-darken-1` | muted | muted | — |
| Priority high | `$error` | red | red | text tag `(H)` |
| Priority medium | `$warning` | amber/yellow | amber | text tag `(M)` |
| Priority low | `$primary` (muted) | blue | blue | text tag `(L)` |
| Overdue | `$error` bold | red | red | word `OVERDUE` + `(!)` priority echo |
| Due today | `$warning` | amber | amber | words `due today` |
| Success / confirmation toast | `$success` | green | green | toast text + `✓`/`Done:` label |
| Error toast | `$error` | red | red | toast text + `Error:` label |

Accessibility note on color: **no state is conveyed by hue alone.** Completion = `[x]` + strike; priority = `(H/M/L)` letters; overdue = the literal word `OVERDUE`; the cursor = the `▸` glyph and position. Contrast: rely on Textual theme tokens, which target WCAG-ish contrast for `$text` on `$surface`; the one custom pairing to verify is the focused-row `$text`-on-`$accent` (aim for ≥ 4.5:1 — Textual's default accent passes, but re-check if a custom theme is added).

## States

### Empty (first run / no tasks)
Centered inside the list panel (content-align center middle):

```
┌─ Inbox · 0 active · 0 done ─────────────────────────────┐
│                                                         │
│                     No tasks yet                        │
│            Press  a  to add your first task             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```
- Primary text `No tasks yet` in `$text`; the call-to-action `Press a to add…` in `$text-muted` with the key `a` styled like a footer key. This is where new users live — it names the next action explicitly (the `a`/add binding lands in #5; until then show just `No tasks yet`).

### Populated
The normal case — rows as in the Layout wireframe. Newest-at-top or sort order is a controller concern (priority sort arrives in #6); default is creation order.

### Focused item (cursor row, list focused)
- `▸ ` cursor glyph in the gutter, full `$accent` background across the row, `$text` foreground. The whole row, including its tags, is readable against the accent fill.

### Focused item, list blurred
- `▸ ` cursor retained, background drops to the muted `$boost` tint, foreground returns to normal `$text`. Signals "this is where you are, but you're typing elsewhere."

### Completed / done item
```
   [x] (L) Water the plants                              #home        ──
```
- `[x]` checkbox, title `$text-disabled` + `strikethrough`, all tags dimmed. Due slot shows `──` (em-dashes) rather than a stale date. A done item can still be the cursor row (so it can be toggled back / deleted).

### Overdue item (#7 — reserved)
```
   [ ] (!) Renew passport                                #admin    OVERDUE 06-20
```
- Due slot renders `OVERDUE <date>` in `$error` bold. The priority tag echoes urgency as `(!)` when no explicit priority is set but the task is overdue (taskwarrior "urgency" idea), or keeps its real `(H/M/L)` if set. Overdue never applies to a `-done` row.

### High-priority item (#6)
```
 ▸ [ ] (H) Finish the quarterly report                   #work       due today
```
- `(H)` tag in `$error`. Note: priority colors the **tag only**, not the whole row, so it composes with the cursor highlight and with overdue coloring without clashing.

### Loading
- The controller read is local SQLite and effectively instant, so no spinner by default. If a refresh is ever async, show the panel border title as `Inbox · loading…` rather than blanking the list (avoid layout jump). No skeleton rows needed for a local DB.

### Error
- Persistence errors (`TasqueError` subclasses) are caught by the controller and surfaced as a Textual **toast/notification** (`app.notify(...)`, `severity="error"`), styled `$error`, prefixed `Error:`. The list keeps its last good render. Widgets never see raw `sqlite3` exceptions (per CLAUDE.md).

## Interaction Flow & Keybindings

`▸` = visible in the footer hint bar (lazygit/k9s style). Navigation keys are intentionally **not** all shown in the footer (implied, to keep it short) — they appear in the `?` help overlay.

| Action | Key(s) | System response | Footer? | Feature |
| --- | --- | --- | --- | --- |
| Move cursor down | `j` / `↓` | Highlight next row; auto-scroll to keep in view | no | #4 |
| Move cursor up | `k` / `↑` | Highlight previous row | no | #4 |
| Page down | `Ctrl+d` / `PgDn` | Cursor down ~one page | no | #4 |
| Page up | `Ctrl+u` / `PgUp` | Cursor up ~one page | no | #4 |
| Jump to top | `g` / `Home` | Highlight first row | no | #4 |
| Jump to bottom | `G` / `End` | Highlight last row | no | #4 |
| Toggle complete | `Space` / `Enter` | Post toggle intent → controller flips `completed`, persists, row re-renders `[ ]`↔`[x]` | `▸` | #5 |
| Add task | `a` | Open `InputBar` at bottom; on `Enter` create via controller, new row appears + becomes cursor; `Esc` cancels | `▸` | #5 |
| Edit task | `e` | Inline-edit the cursor row's title; `Enter` persists, `Esc` cancels | `▸` | #5 |
| Delete task | `d` | Confirm prompt (`Delete "…"?  y/n`); `y` deletes via controller + toast, `n`/`Esc` aborts | `▸` | #5 |
| Cycle priority | `p` | Cursor row priority none→low→med→high→none; persists; tag re-renders | `▸` | #6 |
| Filter (reserved) | `/` | Filter input over the list (k9s convention) | no | future |
| Help overlay | `?` | Modal listing all keybindings (lazygit) | `▸` | #4 |
| Quit | `q` | Exit app | `▸` | #4 (exists) |

Footer order (mirrors the wireframe): `a Add · ␣ Toggle · e Edit · d Delete · p Priority · ? Help · q Quit`. Enter is an alias for toggle (it is `ListView`'s native `Selected` trigger — we map `Selected` → toggle so the built-in binding is meaningful rather than dead).

### Mouse (optional)
- Click a row → moves the cursor to it (no toggle, to avoid accidental completion).
- Scroll wheel → scrolls the list.
- Click a footer hint → triggers that binding (Textual `Footer` supports this).

## Edge Cases

- **Single item:** `g`/`G`/`j`/`k` are all no-ops past the one row; cursor stays put. Counts read `1 active`.
- **10,000 items:** `ListView` virtualizes/scrolls; only on-screen rows paint. Avoid full rebuilds on every keypress — diff-update children when the controller returns a new list. Navigation must stay responsive (no per-row DB calls; one `list_todos()` read).
- **Cursor on a deleted row:** after delete, move the cursor to the next row (or previous if it was last); never leave it on a stale index. If the list becomes empty, show the Empty state.
- **Key spam (holding `j` / mashing `Space`):** navigation is idempotent and bounded by list ends. Rapid toggles each go through the controller; the undo stack (#9) records each — acceptable. Debounce is not required for local SQLite, but a toggle should not fire if an inline edit/confirm modal is open (modal captures keys).
- **Very narrow terminal:** drop due → category → (keep checkbox + truncated title). Never horizontal-scroll a row.
- **Long title:** truncate with `…`; full text visible on edit (`e`). No wrap.
- **Toggling a done overdue item:** completing clears the overdue escalation (overdue never shows on `-done`); un-completing restores it.

## Accessibility & Degradation

- **Keyboard-only path:** Launch → list has focus → `j`/`k` to the target → `Space` toggle / `e` edit / `d` delete / `p` priority / `a` add. Every function is reachable with no mouse. `Tab` moves focus between the list and the InputBar (when open); `Esc` always backs out of an edit/confirm/filter to the list.
- **Color-blind safety:** every colored state is paired with a glyph/word — `[x]` (done), `(H)/(M)/(L)/(!)` (priority/urgency), `OVERDUE`/`due today` (dates), `▸` (cursor). The screen is fully usable with color disabled.
- **Monochrome / 16-color terminals:** all glyphs are ASCII (`[ ] [x] ( ) ▸ # …`); `▸` falls back to `>` if needed. On 16-color terminals Textual maps theme tokens to the nearest ANSI color; because meaning is carried by symbols, a token collapsing to a near color loses no information. Strikethrough/dim for done degrade to dim-only if strike is unsupported, still distinguishable by `[x]`.
- **Screen reader / labels:** each `TodoItem` exposes a text label combining state into one readable string, e.g. `"incomplete, high priority, Finish the quarterly report, due today"` so a row is meaningful read aloud, not just visual glyphs. The list panel's border title (`Inbox · 3 active · 1 done`) gives orientation. The cursor row should be announced on `Highlighted`.
- **Contrast:** lean on Textual theme tokens (designed for adequate contrast on both themes). The single pairing to verify when adding any custom theme is `$text` on the `$accent` focus fill — target ≥ 4.5:1.

## Open Questions / Assumptions

1. **Toggle key:** assumed `Space` (primary) + `Enter` (alias via `ListView.Selected`), with `e` for edit. If the architect prefers `Enter` = edit (some editors' convention), surface it — but the `Selected` message makes `Enter` = toggle the cheaper, more idiomatic Textual choice.
2. **Sort order:** assumed creation order for #4; priority sort is a #6 concern and toggled by a key TBD (`s`?). Not specified here to avoid pre-empting #6's design.
3. **`▸` cursor glyph vs. relying solely on background:** assumed we render an explicit `▸` gutter (not just the highlight background) so the cursor survives monochrome and the blurred-list dim state. Costs 2 columns. Confirm acceptable.
4. **Due format (#7):** assumed relative-ish (`due today`, `OVERDUE 06-20`, else `MM-DD`). Final format is a #7 decision; reserve the slot now.
5. **Category display (#8):** assumed a single `#name` tag right of the title. Multi-category is out of scope; confirm one-category-per-task holds (the model has a single `category_id`, so yes).
6. **Empty-state CTA timing:** the `Press a to add…` line names a binding that does not exist until #5. Assume #4 ships the line as just `No tasks yet`, and #5 adds the CTA. Flag if the implementer wants the full line stubbed earlier.
