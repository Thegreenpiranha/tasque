# UX Spec: Due dates & overdue highlighting (Feature #7)

> Scope: the **display strings** shown in the reserved `#due` slot for none/overdue/due-today/future/done,
> their colour tokens and paired non-colour signals; the **parse grammar** and the InputBar `"due"`-mode
> field copy (placeholder / footer / invalid feedback); the `D` set/clear affordance, the `s` sort's new
> `by due` mode, and every due-related state and edge case. This spec completes the two seams the architect
> handed to the researcher in `docs/architecture/feature-7.md` §8 / §4a (Q4 display strings, Q3 grammar +
> copy) and confirms the shipped `#meta` CSS.
>
> It **defers to `main-screen.md`** for the row/column layout, the reserved `#due` slot, the cursor/`▸`
> language, the `-done` dim+strike, the theme-token / colour-blind rules (Principle 4), the footer style,
> and the border-title format; and to `input-bar.md` / `edit-screen.md` for the docked-bar mechanics
> (docked `round $accent` bar, `›` prompt glyph, `-invalid` pulse, caret-at-end pre-fill, `Esc` cancel).
> It does not restate them. Data model, migration, sort SQL, `parse_due_date`/`due_state`/`_due_display`
> signatures, and control flow are the architect's (`feature-7.md`); this doc only fills the wording those
> seams render. `main-screen.md` Open Question #4 (due-format assumption) is **resolved here**.

## References

- **taskwarrior / taskwarrior-tui** — *due is a first-class attribute entered as an ISO date **or** a large
  named/relative grammar (`today`, `tomorrow`, `eom`, weekday names, `now+3d`), and the TUI colours overdue
  rows and ranks them by urgency, pairing the colour with the row's position, not hue alone.* We borrow (a)
  the **ISO-or-shortcut entry** model, (b) the **`today`/`tomorrow` named anchors** and a **relative day
  offset** (`now+3d` → our `+3`), and (c) overdue = **visual escalation on the date cell**. We deliberately
  **do not** adopt taskwarrior's full named-date grammar (weekdays, `eom`, holidays) — see Q3. ([dates](https://taskwarrior.org/docs/dates/), [named dates](https://taskwarrior.org/docs/named_dates/), [taskwarrior-tui](https://github.com/kdheepak/taskwarrior-tui))
- **todo.txt** — *due date is the `due:YYYY-MM-DD` key/value tag; the reference `todo.sh` due extension
  lists tasks "overdue or due today" and "due in the next N days".* We borrow the **ISO `YYYY-MM-DD` as the
  canonical stored/typed form** (already dictated by the shipped `date.fromisoformat` mapper) and the
  three-band **overdue / due-today / upcoming** salience split that drives our escalation states. ([todo.txt](https://github.com/todotxt/todo.txt), [swiftodo due syntax](https://swiftodoapp.com/todotxt-syntax/due-dates-and-threshold-dates/))
- **dstask** — *a git-backed terminal to-do that keeps date handling deliberately lean and shows due
  proximity as a compact relative cue.* Confirms that a **small, predictable date vocabulary** (not a full
  NL parser) is the right weight for a single-binary terminal to-do. ([dstask](https://github.com/naggie/dstask))
- **Todoist / Things** — *GUI to-do apps with rich natural-language date entry ("next friday", "in 2 weeks")
  and friendly relative labels ("Today", "Tomorrow", then absolute dates).* We borrow the insight that
  **`today`/`tomorrow` are the two anchors worth spelling out** and that escalation reads as a **word**, but
  we **reject** their free-form NL parsing as disproportionate for #7 (needs a locale-aware parser; not pure
  or fixed-`today`-testable) — see Q3. ([Todoist quick add](https://todoist.com/help/articles/use-task-quick-add-in-todoist-va4Lhpzz), [Things](https://culturedcode.com/things/))

## Design Principles (due-specific; defers to `main-screen.md`)

1. **A word carries the state; colour only reinforces (Principle 4).** Overdue and due-today are the only
   two *escalated* states, and each is announced by a literal word (`OVERDUE`, `due today`) so the row reads
   in monochrome and to colour-blind users. `$error`/`$warning` merely echo the word. A future date is not an
   escalation, so it is *plain muted data* (a bare date), exactly like the category tag.
2. **Escalation never survives completion.** A `-done` row shows no `OVERDUE`/`due today` and no colour
   escalation — the `#due` slot reads `──`. A completed task's deadline is moot; showing it as still-overdue
   would be a lie. (Mirrors `main-screen.md` §Completed / §Overdue.)
3. **One slot, one grammar family.** Due lives in the reserved `#due` slot inside `#meta`, right-grouped
   after the title (`main-screen.md` per-row table). It never changes the row's shape; on a narrow terminal
   it is the **first** thing dropped (optional meta), per `main-screen.md` §Resize.
4. **Type it or clear it in one field.** Setting and clearing a due date are the same affordance in the same
   docked bar: type a date to set, blank the field to clear. No second key, no modal calendar (rejected in
   `feature-7.md` §4 as out-of-scope for #7).

---

## Q3 — Parse grammar + InputBar `"due"`-mode copy (DECISION)

**Decision: confirm the architect's small grammar exactly — ISO `YYYY-MM-DD`, `today`, `tomorrow`, and
`+N` (N calendar days from today) — and do *not* broaden it for #7.** Any accepted token resolves to a
`date` inside the one pure `models.parse_due_date(text, *, today)`, so this choice is contained.

| Typed (case-insensitive, trimmed) | Resolves to | Grounded in |
| --- | --- | --- |
| `2026-07-10` (ISO `YYYY-MM-DD`) | that exact date | todo.txt `due:` / the shipped `date.fromisoformat` mapper |
| `today` | `today` | taskwarrior `sod`, Todoist/Things "Today" |
| `tomorrow` | `today + 1 day` | taskwarrior `tomorrow`, Todoist/Things "Tomorrow" |
| `+3` (`+N`, N = whole days) | `today + N days` | taskwarrior relative duration `now+3d`, simplified to whole days |
| *(anything else — `soon`, `next fri`, `2026-13-40`)* | **`DueDateParseError`** → `-invalid` pulse | — |

**Why not broaden to weekday names / `next friday` / `in 2 weeks` (Todoist/taskwarrior style):**

1. **Testability & purity.** `parse_due_date` is a pure function taking an injected `today` so overdue/relative
   resolution is unit-tested with a fixed now (the acceptance criterion; `feature-7.md` §11). ISO + two named
   anchors + `+N` are trivially fixed-`today`-testable. A weekday/NL grammar drags in "nearest future" rules,
   ambiguity ("friday" = this or next?), and locale/word-order concerns — a real date parser, disproportionate
   for a single-binary #7. taskwarrior *can* carry that grammar because date parsing is its core competency;
   Tasque's #7 target is the common case.
2. **The common case is already covered.** An exact deadline (ISO), "today", "tomorrow", and an arbitrary
   near-future offset (`+N`) cover the overwhelming majority of entries. `todo.sh`'s own due extension centres
   on exactly this shape (ISO plus "due today / next N days"). dstask confirms lean-vocabulary is right-weight.
3. **The grammar is unbounded later at zero UX cost.** Because every token collapses to a `date` inside one
   function, a future feature can add `yesterday`, `+Nd`/`+Nw`, or weekday names without touching this spec,
   the slot, or the CSS. Deliberately deferred, not foreclosed. (`yesterday` and a `-N` back-date are the
   cheapest future additions; both omitted now as low-value — one rarely gives a task a past deadline.)

**Field copy (exact strings the user sees).** The `"due"` mode reuses the docked bar from `input-bar.md`
(`round $accent`, leading `› ` prompt glyph, `Esc` cancels), with:

- **Border title:** `Due date`. (The *word* names the mode — add=`New task`, edit=`Edit task`, due=`Due date` —
  never colour.)
- **Pre-fill & caret:** opens pre-filled with the task's current due date as ISO (`2026-07-10`), caret at end
  (matching edit); or **empty** if the task has no due date (placeholder then shows).
- **Placeholder (shown while the field is empty):**

  ```
  › YYYY-MM-DD, today, tomorrow, +3
  ```

  in `$text-muted`. It teaches the exact grammar; it reappears if the user blanks a pre-filled date.
- **Footer — a two-state Set/Clear swap** (extends `feature-7.md` §7b's single `Set due` label; the swap uses
  the existing `check_action` + `refresh_bindings` mechanism the bar already runs for Add↔Save / Cancel↔Done,
  LEARNINGS 2026-07-02, driven here by `Input.Changed` flipping on empty↔non-empty):

  | Field state | Footer |
  | --- | --- |
  | non-empty | `⏎ Set due · Esc Cancel` |
  | empty | `⏎ Clear due · Esc Cancel` |

  This is how **blank-to-clear** is made discoverable *when it matters* — the moment a date is present and the
  user backspaces it away, the Enter hint reads `Clear due`. (On an undated task, an empty field's `Clear due`
  + Enter is a harmless no-op close — clearing an absent date changes nothing.)
- **Invalid-parse feedback (reusing `input-bar.md`'s empty-add pulse):** on a non-empty value that
  `parse_due_date` rejects, the bar pulses its border `$error` via the `-invalid` class for ~600 ms and
  **stays open with the typed text intact**; the footer/inline hint reads:

  ```
  Can't read that date — try YYYY-MM-DD, today, +3
  ```

  Meaning is in the words + the pulse, never hue alone. Nothing persists; the user fixes the text and re-Enters.
  (The screen detects the parse failure and calls the bar's public `flash_invalid()`, `feature-7.md` §7b/§7c.)

---

## Q4 — `#due` display strings (DECISION)

**Decision: confirm `main-screen.md`'s reserved forms, keep future dates *absolute* (not relative), and add a
single year rule that shows the year only when it is not the current calendar year.** This resolves
`main-screen.md` Open Question #4. Rendered into the reserved `#due` `Static` (`markup=False`; the `──` dashes
and digits are not Rich markup, but `markup=False` is retained per the bracket-strip gotcha, LEARNINGS 2026-07-01).

| `due_state` (and completion) | `#due` slot content | CSS class on row | Colour token | Accessible-label word |
| --- | --- | --- | --- | --- |
| `NONE` | `` (empty slot) | *(none)* | — | *(omitted)* |
| `OVERDUE`, not done, **current year** | `OVERDUE 06-20` | `-overdue` | `$error` **bold** | `overdue` |
| `OVERDUE`, not done, **other year** | `OVERDUE 2025-12-01` | `-overdue` | `$error` **bold** | `overdue` |
| `TODAY`, not done | `due today` | `-due-today` | `$warning` | `due today` |
| `FUTURE`, **current year** | `06-30` | *(none)* | `$text-muted` (default `#meta`) | `due 2026-06-30` |
| `FUTURE`, **other year** | `2027-01-15` | *(none)* | `$text-muted` (default `#meta`) | `due 2027-01-15` |
| **completed** (any due) | `──` | *(none — escalation suppressed)* | `$text-disabled` (`.-done > #meta`) | *(omitted)* |

**The year rule (resolves the `MM-DD`-drops-the-year ambiguity).** Show `MM-DD` when the due date is in the
**current** calendar year; show full ISO `YYYY-MM-DD` when it is any other year — applied identically to
overdue (`OVERDUE 2025-12-01`) and future (`2027-01-15`). This is the widely-used "omit the year until it
differs" convention (`ls -l`, `git log`, GitHub timestamps): the common case stays compact (`06-30`) while a
date months/years out is never ambiguous. It requires `_due_display`/`_due_word` to know the current year, so
they take the **`today`** the widget already computes for `due_state` (a small refinement of `feature-7.md`
§8's `_due_display(due, state, completed)` → `_due_display(due, state, completed, today)`; the widget passes
its existing `today = date.today()`). No new clock read; still fixed-`today`-testable.

**Why future dates stay absolute (not relative `in 3d`).** taskwarrior-tui / Todoist / Things all lean on
relative future labels, and they read nicely — but `main-screen.md` **reserved** the absolute `MM-DD` form for
this slot, and *coherence with the already-shipped visual language is the decisive factor* (the same reasoning
`priority.md` used to confirm `(H)/(M)/(L)`). Absolute is also more precise for planning ("in 12d" hides the
actual date) and avoids the slot's text churning every day. The escalation words (`OVERDUE`, `due today`) are
the one relative touch, and they earn it: they are *status announcements* (they get colour), whereas a future
date is neutral metadata (no colour), so a bare date is the honest treatment. **Rejected: a relative future
form** (`in 3d`) — would contradict `main-screen.md`'s reservation for a marginal glance-value gain.

**Why done shows `──`, not the historical date.** A completed row is `[x]` + dim + strike and sits in the
demoted done band (DUE sort); its deadline is moot. `──` says "no active due signal" unambiguously. **Rejected:
a dimmed historical date** on the done row — it preserves trivia at the cost of a date that can read as a live
deadline, and `main-screen.md` explicitly reserved `──` here. (A done row that *never* had a due date shows the
empty slot, not `──`; `──` means "had a deadline, now moot" — an honest, if subtle, distinction.)

**Accessible-label refinement.** For a *future* row the label uses the **full ISO** (`due 2026-06-30`), not the
visual `MM-DD`, so a screen reader reads an unambiguous date rather than two loose numbers (a small refinement
of `feature-7.md` §8's `due 06-30`). Label order is **completion, priority, text, due** — e.g.
`"incomplete, high priority, Finish the quarterly report, due today"` (`main-screen.md` §Screen reader).
`overdue` and `due today` announce the escalation; none and done contribute nothing (absence, not "no due").

---

## States

- **None.** Empty `#due` slot, no class, label omits due. Indistinguishable from an unset field because it is one.
- **Overdue (active row).** `OVERDUE MM-DD` (or full ISO for a prior year) in `$error` **bold**, `-overdue` set.
  The word `OVERDUE` is the meaning; colour reinforces. The date after the word tells you *when* it was due.
- **Due today (active row).** `due today` in `$warning`, `-due-today` set. Lower-case + amber reads *calmer*
  than the `OVERDUE` shout — today is not yet late.
- **Future (active row).** Bare `MM-DD` (or full ISO for another year) in the default muted `#meta` colour — no
  class, no escalation. Just data, like the category tag.
- **Focused cursor row + due.** `▸ [ ] (H) Finish the quarterly report … due today` — `▸` gutter, `$accent` row
  fill, the `#due` text still tinted `$warning`/`$error` on top of the accent (colour on `#meta` only, never
  the whole row, so it composes with the cursor highlight — `main-screen.md` §High-priority item). The word
  guarantees legibility even where date-on-accent contrast is imperfect.
- **Focused cursor row, list blurred (bar open).** `▸` retained, row drops to the muted `$boost` tint; the
  `#due` state text is unchanged. This is the state while the `Due date` bar is open on that row
  (`input-bar.md` blurred-highlight).
- **Done (any due).** `[x]` + title dim+strike, `#due` = `──` in `$text-disabled`. **No** `-overdue`/`-due-today`
  (the widget gates both on `not completed`, `feature-7.md` §8), so an overdue task loses its escalation the
  instant it is completed and regains it if un-completed.
- **Loading / error.** No due-specific loading — the read is local SQLite (`main-screen.md` §Loading). A failed
  set (row deleted mid-flow) surfaces as the standard controller `TasqueError` toast `Error: …`; the row keeps
  its last good render (`feature-7.md` §7c).

## Interaction & affordances

### `D` (Shift+D) — set / clear due on the focused row (key RESOLVED, `feature-7.md` §4)

- `D` on the highlighted row opens the docked bar in `"due"` mode, pre-filled with the current ISO date (caret
  at end) or empty (placeholder shown). `d` stays Delete; `D` is its attribute sibling on the same row.
- **Enter, non-empty, parses** → `controller.set_due_date(id, date)`; bar closes; row re-renders. **Enter,
  empty** → `set_due_date(id, None)` (clear); bar closes. **Enter, non-empty, junk** → `-invalid` pulse, bar
  stays open (Q3). **Esc** → cancel, no change. (`feature-7.md` §4 / §7.)
- **Feedback is the row changing in place** (or re-ranking in DUE sort) — no toast, matching the app's
  no-noise-for-instant-ops convention (`priority.md` §`p`; `main-screen.md` §Loading).
- **Unchanged + Enter** re-commits the same date (one harmless write / future-undo entry). An optional no-op
  guard is possible but not required — kept simple, unlike edit's changed-text check, because a due re-set is
  idempotent and cheap.
- **In-place vs. re-rank** (mirrors the `p` cycle, `feature-7.md` §7c): in CREATED/PRIORITY sort the row does
  not move → cheap `update_todo`; in DUE sort the row may re-rank → `refresh_todos(keep_id=…)` so the **cursor
  follows the task**, not the vacated slot.

### `s` — sort gains a third mode `by due`

- The `s` cycle becomes three-way: `creation order → by priority → by due → creation order` (`feature-7.md`
  §7d). DUE sort orders earliest-first among active tasks, `NULLS LAST`, done demoted below active (§9 SQL).
- **Transient feedback:** the standard `app.notify(…, severity="information")` toast `Sorted by due date`
  (meaning in the words, not colour; `notify` has no "success" severity, LEARNINGS 2026-07-01).
- **Persistent active-mode cue** (extends `priority.md`'s border-title convention): the panel border-title
  gains a ` · by due` suffix in DUE sort — `Inbox · 3 active · 1 done · by due`. Creation order (default) stays
  suffix-free. Right-truncates first on a narrow terminal, like ` · by priority`.

### Footer

`D Due` joins the list-focused footer between `p Priority` (its attribute sibling) and `s Sort`:

```
a Add · ␣ Toggle · e Edit · d Delete · p Priority · D Due · s Sort · ? Help · q Quit
```

**The footer is now crowded (9 hints).** This is acceptable for #7 because Textual's `Footer` elides trailing
hints on a narrow terminal and the `D`/`s` hints are non-load-bearing (both are also in `?` help). **Surfaced,
not solved:** when Feature #8 (category) adds another key, the footer will need a rethink — likely grouping
attribute keys or moving lower-frequency hints into `?`-help only. Flagged for #8's design, not decided here.

The `"due"`-mode footer is the Set/Clear swap specced in Q3 (`⏎ Set due` / `⏎ Clear due` · `Esc Cancel`).

## CSS — confirm the shipped rules (no change)

The three `#meta` rules already ship in `tasque.tcss` and are correct for #7 as-is:

```
TodoItem.-overdue   > #meta { color: $error; text-style: bold; }   /* activated by #7 */
TodoItem.-due-today > #meta { color: $warning; }                   /* activated by #7 */
TodoItem.-done      > #meta { color: $text-disabled; }             /* shipped #4/#6 */
```

- **Confirm all three; no edit recommended.** `$error` bold (alarm) for overdue, `$warning` (caution) for
  today, `$text-disabled` (moot) for done — the correct severity ramp, and consistent with the priority
  `$error`/`$warning` hues.
- **No source-order landmine here** (unlike the priority done-dim, LEARNINGS 2026-07-03). Because the widget
  gates `-overdue`/`-due-today` on `not completed`, a row is **never** simultaneously `-done` and
  `-overdue`/`-due-today`, so `.-done > #meta` and `.-overdue > #meta` never tie for the same cell — the
  design structurally avoids the equal-specificity trap rather than ordering around it. (Contrast priority,
  where a *done* row keeps its priority, forcing `.-done > #priority` to sit after `.-priority-*`.)
- **`#due` currently lives inside `#meta` as its only populated child**, so the `> #meta`-wide rules colour it
  by inheritance and are exactly right. **Forward-note for Feature #8 (context, not a decision):** when
  `#category` also populates `#meta`, #8 decides whether an overdue row tints the category too (keep
  `> #meta`) or only the date (narrow to `#meta > #due`). No premature narrowing for #7.
- **Testing note (LEARNINGS 2026-07-03):** overdue-vs-today correctness rides on the *resolved* `#meta` colour
  (`$error` vs `$warning`), which class-presence tests can't catch — assert `styles.color` under the real
  `TasqueApp` so `tasque.tcss` loads (`feature-7.md` §11).

## Edge cases

- **Rapid re-set (`D` … Enter, `D` … Enter):** each Enter is one controller command = one future-undo entry
  (#9); bounded, no debounce needed for local SQLite. In CREATED/PRIORITY the tag flickers in place; in DUE the
  row hops to its new rank each time, cursor following via `keep_id`.
- **Set / clear while in DUE sort:** the row re-ranks (earlier date → up, `None` → `NULLS LAST` bottom) and the
  **cursor follows the task** (`refresh_todos(keep_id=updated.id)`, `feature-7.md` §7c) — visible confirmation
  the date changed. In CREATED/PRIORITY the row stays put (`update_todo`).
- **Toggle completion while in DUE sort:** completing demotes the task to the done band (DUE shares
  `completed ASC` primary key), so the list re-sorts, and — matching the priority toggle rule (`priority.md`
  OQ4 / `feature-6.md` §6) — the **cursor holds its index** (the next active task slides in, "move on to the
  next thing"), *not* `keep_id`. Only `D` set-due and `s` sort follow the task by id. Completing also clears any
  `-overdue`/`-due-today` and flips `#due` to `──`; un-completing restores the escalation.
- **Narrow terminal:** the `#due` slot is the **first** dropped (right-aligned optional meta, `main-screen.md`
  §Resize), before category and before the priority tag. Its colour goes with it; because meaning is the word
  `OVERDUE`/`due today`, dropping the slot loses only reinforcement — but at that width the deadline is simply
  not shown (acceptable for the pathological case). A full-ISO other-year string (`OVERDUE 2025-12-01`, ~19
  cols) is the widest content; the title (`1fr`) yields first, and the slot drops before it can force a wrap.
- **10,000 items + DUE sort:** ordering is one `ORDER BY` in `db.py` (§9); no per-row work, navigation stays
  responsive (`main-screen.md` perf note).
- **Single item:** the one row shows/sets its due normally; DUE sort is a visual no-op but `s` still flips the
  `· by due` border-title cue and the toast.
- **`D` while a modal / the bar is already open:** `D` is a `TodoList` binding, so it fires only while the list
  holds focus; when the bar is open the list is blurred and a stray `D` types the literal character into the
  field (the structural state-guard, `feature-7.md` §10). No stacked bars.
- **Row deleted out from under the bar (`D` → Enter on a gone id):** the controller raises `TodoNotFoundError`;
  the screen catches it, toasts `Error: …`, closes the bar, refreshes — no crash (`feature-7.md` §7c).
- **Overdue-then-midnight:** overdue is evaluated at render against `date.today()`, which rolls at local
  midnight (`feature-7.md` §2b); a `due today` row becomes `OVERDUE` on the next render after midnight with no
  stored change. No timezone handling.

## Accessibility & degradation

- **Keyboard-only path:** `j`/`k` to the row → `D` → type a date (or blank to clear) → `Enter` (or `Esc`). No
  mouse required; `Esc` always backs out to the list (`main-screen.md` §Accessibility). `Tab` in the `"due"`
  bar is **inert** (single field — the canonical `Tab` convention, `main-screen.md` §Accessibility).
- **Colour-blind safety:** every *escalated* state pairs colour with a word — `OVERDUE` (`$error`),
  `due today` (`$warning`), `──` (done, `$text-disabled`). Future dates carry no colour meaning (plain muted
  data), so there is nothing colour-only to miss. Fully usable with colour disabled.
- **Monochrome / 16-colour:** all glyphs are ASCII/print-safe (`OVERDUE`, `due today`, digits, `-`, `──`);
  tokens collapse to near ANSI colours with no information loss because the words carry meaning
  (`main-screen.md` §Degradation).
- **Screen reader:** per-state words fold into the row label after the text — `overdue` / `due today` /
  `due <full-ISO>`; none and done contribute nothing. Label order **completion, priority, text, due**. The
  sort mode is announced via the border-title update, not per row. On set/clear the row re-renders → the list's
  `Highlighted` re-announce conveys the new due state without a visual glyph (`priority.md` §`p`).
- **Contrast:** lean on theme tokens (`main-screen.md` targets ≥4.5:1 for `$text` on `$surface`/`$accent`). The
  one pairing to keep in mind is `$error`/`$warning` `#meta` text on the focused-row `$accent` fill — the word
  guarantees legibility regardless, so that contrast is reinforcement, not load-bearing.

## Resolved decisions (researcher, 2026-07-04)

1. **Q3 grammar → confirm small set** — ISO `YYYY-MM-DD`, `today`, `tomorrow`, `+N` (whole days); NL/weekday
   forms deliberately deferred (purity/testability + right-weight, grounded in todo.sh/dstask). Any token
   resolves to a `date` in `parse_due_date`, so broadening later is a zero-UX-cost change.
2. **Q3 copy** — border title `Due date`; placeholder `YYYY-MM-DD, today, tomorrow, +3`; footer Set/Clear swap
   (`⏎ Set due` / `⏎ Clear due` · `Esc Cancel`) to make blank-to-clear discoverable; invalid-parse hint
   `Can't read that date — try YYYY-MM-DD, today, +3` on the reused `-invalid` pulse. **Touches
   `feature-7.md` §7b** (single `Set due` label → two-state swap — a copy/affordance refinement in researcher
   scope, wired via the existing `check_action`/`refresh_bindings` mechanism).
3. **Q4 display strings** — `OVERDUE MM-DD` / `due today` / `MM-DD` / `──`; **future stays absolute**, not
   relative (coherence with `main-screen.md`'s reservation). **Resolves `main-screen.md` Open Question #4.**
4. **Year rule** — show `MM-DD` in the current year, full `YYYY-MM-DD` otherwise (overdue *and* future); needs
   `today` passed to `_due_display`/`_due_word` (a small signature refinement of `feature-7.md` §8, no new
   clock read).
5. **Accessible label** — future uses full ISO (`due 2026-06-30`), not `MM-DD`, for unambiguous read-aloud (a
   refinement of `feature-7.md` §8's `due 06-30`); none/done omit the word; order completion, priority, text, due.
6. **CSS** — confirm `.-overdue`/`.-due-today`/`.-done > #meta` unchanged; note the completion gate structurally
   avoids the priority-style source-order tie.
7. **`D` key & sort/filter split** — inherited as resolved from `feature-7.md` (`D` = due; `by due` *sort* in
   #7, real *filter* deferred to #11); not relitigated here.

## Open questions

- **Footer crowding (cross-feature, for #8).** Nine list-focused hints is at the practical limit; Feature #8's
  category key will force a footer rethink (grouping / demoting hints to `?`-help). Surfaced for #8's design —
  no #7 change.
- **`──` vs empty on a done row that had a due date.** Spec keeps `feature-7.md`'s behaviour (`──` = had a
  deadline, now moot; empty = never had one). If the subtle two-symbol distinction on done rows proves
  confusing in practice, collapsing both to empty is a one-line change — flagged, not blocking.

## Reconciliation notes (for whoever syncs the shipped docs)

- **`main-screen.md` Open Question #4** (due-format assumption) is now **resolved** by this spec (Q4 + year
  rule). Its §States wireframe already shows `OVERDUE 06-20` / `due today` / `06-30` / `──`, which match — only
  the other-year full-ISO rule is new and does not contradict the wireframe (all its examples are current-year).
- **`main-screen.md` Color Scheme table** already lists Overdue = `$error` bold and Due today = `$warning`; this
  spec confirms them unchanged — no table edit needed (unlike `priority.md`'s low-colour change).
