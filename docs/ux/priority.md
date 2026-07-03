# UX Spec: Priority levels (Feature #6)

> Scope: the **visual token** shown in the reserved `#priority` slot for none/low/medium/high,
> its colour tokens and paired non-colour signals, the `p` cycle affordance, the `s` sort
> affordance (feedback + active-mode indicator), and every priority-related state/edge case.
> This spec completes the seam the architect deferred in `docs/architecture/feature-6.md` §7
> (the `(H)/(M)/(L)` letter tags there are an illustrative placeholder — this doc owns the
> final token). It defers to `main-screen.md` for the row layout, the cursor/`▸` language, the
> `-done` dim+strike, the theme-token/colour-blind rules, and the footer style; it does not
> restate them. Data model, migration, sort SQL, and control flow are the architect's (`feature-6.md`).

## References

- **taskwarrior / taskwarrior-tui** — *priority is a three-value attribute `H`/`M`/`L` (plus none), shown as a short column tag; the default theme colours it as a **brightness ramp** (`color.uda.priority.H=color255`, `M=color250`, `L=color245`) so the letter carries identity and **low is deliberately the dimmest**, while urgency still ranks `L` above none.* We borrow the **`H/M/L` letter shorthand** (learned, compact, sorts to three levels) and, crucially, taskwarrior's decision to **de-emphasise low rather than accent-colour it** — grounding our `low = muted` choice. ([priority](https://taskwarrior.org/docs/priority/), [taskwarrior-tui](https://github.com/kdheepak/taskwarrior-tui))
- **todo.txt** — *priority is an uppercase letter **in parentheses** at the head of the task — `(A)` highest, down through `(Z)` — and by convention people use only `(A)/(B)/(C)`; the parens visually bracket it as a badge distinct from the description.* We borrow the **parenthesised single-letter badge** shape `(…)`, which parallels our checkbox `[…]` language and reads as a tag, not a word in the title. ([todo.txt](https://github.com/todotxt/todo.txt))
- **k9s** — *dense one-line rows where a state is shown as a **word/symbol paired with a colour** (Running/Terminating/Error), never hue alone, and a context/breadcrumb line names the current view.* We borrow the **symbol+colour pairing** (already `main-screen.md`'s Principle 4) and the idea that the **active view mode belongs in the context line** — here, the sort mode in the panel border-title.
- **GitHub CLI (`gh`) labels** — *labels render as short coloured text chips inline in a list; the **text** is the meaning and the colour is reinforcement, so the list is legible piped to a non-colour terminal.* Confirms the pattern of a **short coloured text tag whose meaning survives without colour**.

## Design Principles (priority-specific; defers to `main-screen.md`)

1. **The glyph is the meaning; colour only reinforces.** Per `main-screen.md` Principle 4, every priority level must read in monochrome. The letter (`H`/`M`/`L`) carries the level; `$error`/`$warning`/muted merely echo it. A bare coloured swatch is out.
2. **One 4-column slot, shared shape family.** Priority lives in the reserved `#priority` slot (`width: 4`). Its shape — a parenthesised single character — is deliberately the **same family** as the checkbox `[ ]` and the future overdue echo `(!)` (Feature #7), so the slot never changes width or grammar as features land.
3. **Colour the tag, never the row.** Priority tints only `#priority`, so it composes with the `▸`+`$accent` cursor highlight, the `-done` dim, and the future `-overdue` `$error` `#meta` without any two colours fighting for the whole row (`main-screen.md` §High-priority item).
4. **None is a first-class blank.** `priority is None` renders an empty slot and no CSS class — absence, not a fourth glyph. It is distinct from low, which is a present-but-muted tag.

## The visual token — decision

**Decision: confirm the parenthesised letter tags `(H)` / `(M)` / `(L)`, right-padded in the width-4 slot; none renders four spaces.** The architect's placeholder is adopted as the real token — not for inertia, but because it is the choice most grounded in our references *and* the one already-established visual language of `main-screen.md`.

Rendered content (exact), fed to `Static(..., id="priority", markup=False)`:

| `Priority` | Slot content (4 cols) | CSS class | Colour token | Accessible word |
| --- | --- | --- | --- | --- |
| `HIGH` (3) | `(H) ` | `-priority-high` | `$error` | `high priority` |
| `MEDIUM` (2) | `(M) ` | `-priority-medium` | `$warning` | `medium priority` |
| `LOW` (1) | `(L) ` | `-priority-low` | **`$text-muted`** *(was `$primary` — see CSS §)* | `low priority` |
| `None` | `    ` (4 spaces) | *(none)* | — (default text) | *(omitted from label)* |

`markup=False` is retained on the `#priority` `Static`. Parentheses are **not** Rich markup (only `[...]` is), so they are not at risk of the bracket-stripping gotcha — but keeping `markup=False` is consistent with the checkbox/gutter and costs nothing (LEARNINGS 2026-07-01 bracket-strip note).

### Why letter tags (and not the alternatives)

- **It is already the room's language.** `main-screen.md` renders `(H)/(M)/(L)` in this exact slot across its wireframes, pairs it with the `[ ]`/`[x]` bracket checkbox, and reserves the **same slot and shape** for Feature #7's overdue echo `(!)`. Any non-parenthesised token (pips, icons) would clash with `(!)` the moment #7 lands, forcing a slot redesign. Coherence with the shipped language is the decisive factor.
- **Fully ASCII → zero fallback, monochrome- and 16-colour-legible.** `( H ) M L` are plain ASCII; there is nothing to degrade. On a 16-colour terminal the tokens collapse to near colours but the letters are untouched, so no information is lost (`main-screen.md` §Degradation).
- **Doubly grounded in convention.** taskwarrior's `H/M/L` and todo.txt's parenthesised letters are the two most recognised terminal to-do priority notations; a taskwarrior/todo.txt user reads `(H)` instantly.
- **Colour-blind safe by construction.** Three distinct letters are distinguishable with colour fully disabled; colour is pure reinforcement.

### Rejected alternatives

- **Pips `●` / `●●` / `●●●`.** Count-based, so colour-blind-safe, *but*: (1) non-ASCII (`●` U+25CF) needs a fallback (`*`/`o`), which the letter tags don't; (2) a lone `●` for low is easy to mistake for a bullet/cursor artefact; (3) it does **not** share a shape family with the checkbox or the `(!)` overdue echo, so it breaks slot grammar at Feature #7; (4) harder to voice for a screen reader (the letter maps straight to "high"). Rejected.
- **Coloured icons / arrows (`▲ ■ ▼`, `↑ = ↓`).** Direction (up=high) is a nice colour-free shape signal, but non-ASCII (fallback needed), no shared family with `(!)`, and no established terminal-to-do precedent. Rejected in favour of the referenced letter convention.
- **Colour + word (`High`/`Med`/`Low`).** A full word does not fit `width: 4` and would eat the `1fr` title column, violating `main-screen.md`'s density principle (#2). Rejected — the letter *is* the word, abbreviated.
- **Bare coloured swatch (a colour block, no glyph).** Fails Principle 4 outright — meaning by hue alone. Rejected.
- **A fourth glyph for "none".** Rejected — absence is the honest signal for "no priority set" and matches the nullable model (`feature-6.md` encoding decision). A blank slot ≠ a low tag.

## Slot width & CSS

- **Slot width: confirm `#priority { width: 4 }` — no change.** `(H) ` is 3 glyphs + 1 trailing space = 4, mirroring the checkbox slot's `[ ] ` spacing; the trailing space is the gap to the title. None is four spaces. No stylesheet width edit.
- **High / medium colours: confirm.** `TodoItem.-priority-high > #priority { color: $error; }` and `-priority-medium { color: $warning; }` already ship and are correct (severity hue ramp: alarming red → warning amber for the two "act now" levels).
- **Low colour: RECOMMENDED change `$primary → $text-muted`.** This is the one change that touches a shipped artefact, so it is surfaced, not silent (see Open Questions #1). Rationale:
  1. **Semantic.** A severity ramp reads red → amber → *calm*, not red → amber → *another saturated accent*. `$primary` is the panel's accent hue (the focused border colour); using it for "low" makes the least-urgent level compete for attention and reads like "info", an orthogonal axis. `$text-muted` recedes — exactly what "low" should do.
  2. **Referenced, not aesthetic.** taskwarrior's default priority theme is a **brightness ramp** with `L` as the *dimmest* grey (`color245`), deliberately de-emphasised. `$text-muted` reproduces that intent in theme tokens.
  3. **Contrast on the cursor row.** On the focused row the background is `$accent`; a `$primary` foreground (a near-hue) risks poor contrast, whereas `$text-muted` matches how `main-screen.md` already renders `#meta` on the focused row — a tradeoff the app has already accepted, so this is consistent, not new. Either way the letter `L` carries meaning, so contrast is reinforcement, not load-bearing.
  - Alternative if the user prefers low to keep a distinct *hue* rather than go neutral: `$secondary`. Noted in Open Questions #1.
- **ADD a done-dims-priority rule (correctness fix, not optional).** `main-screen.md` §Completed states a done row dims "priority/category/due". The shipped `.-done` rules cover `#title`/`#checkbox`/`#meta` but **not** `#priority` — a #6 gap. Add:
  ```
  TodoItem.-done > #priority { color: $text-disabled; }
  ```
  **Placement matters:** `.-done > #priority` and `.-priority-high > #priority` have equal specificity (type + one class + id), so **source order decides the tie** — this rule must appear **after** the `.-priority-*` block in `tasque.tcss` so a done high-priority tag dims rather than staying `$error`. (Flagged because it is easy to place it too early and see a bright `(H)` on a completed row.)

## States

- **None.** `    ` (blank slot), no `-priority-*` class, no colour, label omits priority. Indistinguishable from an unset field because it *is* one.
- **Low / Medium / High (active row).** `(L)`/`(M)`/`(H)` in muted / `$warning` / `$error`, tag only. Title and the rest of the row keep their normal treatment.
- **Focused cursor row + priority.** `▸ [ ] (H) Finish the quarterly report` — `▸` gutter, `$accent` row background, and the `(H)` still tinted `$error` on top of the accent fill (colour on the tag only). The letter guarantees legibility even where tag-on-accent contrast is imperfect.
- **Done + high priority.** `[x] (H) <title dimmed+strike>` with the `(H)` **dimmed to `$text-disabled`** (per the CSS add) — urgency is moot once done, and in priority-sort the row sits in the demoted done band, so a dim `(H)` at the bottom reads correctly rather than a bright red one competing with active highs.
- **Loading / error.** No priority-specific loading (local SQLite is instant — `main-screen.md` §Loading). A failed cycle (row deleted mid-action) surfaces as the standard controller `TasqueError` toast `Error: …`; the row keeps its last good tag (`feature-6.md` §6 guard).

## Interaction & affordances

### `p` — cycle priority (on the focused row)
- **Cycle:** `none → low → medium → high → none` (`main-screen.md` keybindings; `feature-6.md` `next_priority`). Each press persists and re-renders the tag.
- **Feedback — quiet by design, no animation, no toast.** The tag glyph+colour changing *in place* is the feedback; cycling to `none` blanks the slot (itself a clear "back to none" signal). This matches the app's "instant local op, no spinner/no noise" convention (`main-screen.md` §Loading; input-bar quick-capture). A toast per press would be noisy under rapid `p p p` cycling and is deliberately omitted. (An optional ~150 ms tag emphasis/pulse is *possible* for discoverability but not specified — flagged in Open Questions #3.)
- **In creation-order sort:** the row does not move; only its tag changes (cheap in-place `update_todo`, cursor preserved).
- **In priority sort:** cycling changes the row's band, so the list re-sorts and the row visibly jumps to its new position — strong, self-explanatory feedback; the cursor follows the **task** via `refresh_todos(keep_id=…)` (`feature-6.md` §6), never the vacated slot.
- **Screen reader:** the row's `accessible_label` recomputes live (e.g. `"incomplete, high priority, Finish the quarterly report"`), so re-announcing the row on change conveys the new level without a visual glyph.

### `s` — sort mode (screen-level)
- Toggles `creation order ↔ by priority` (`feature-6.md` §3/§6). Priority sort: `high → medium → low → none`, with **done demoted below active** (already decided).
- **Transient feedback:** on toggle, the standard `app.notify(..., severity="information")` toast — `Sorted by priority` / `Sorted by creation order`. (Meaning is in the words, not a colour — Principle 4; and `notify` has no "success" severity anyway, LEARNINGS 2026-07-01.)
- **Persistent active-mode indicator — RECOMMENDED (borrowing lazygit/k9s context line):** the toast vanishes, so the *current* sort must be legible on return. Append the mode to the panel **border-title** only when it is non-default:
  - creation order (default): `Inbox · 3 active · 1 done` (unchanged — the default stays invisible; no clutter).
  - priority: `Inbox · 3 active · 1 done · by priority`.
  This is a text word in the border title (colour-blind-safe, screen-reader-announced on update) and slightly extends `main-screen.md`'s border-title format (`{list} · {N} active · {M} done`) — a coherent addition, surfaced in Open Questions #2. On a narrow terminal the `· by priority` suffix truncates first (right-truncation, per `main-screen.md`), which is acceptable since it is a soft cue the toast already delivered.
- **Why done-demotion needs no extra cue:** done rows already carry `[x]` + dim + strike, so their cluster at the bottom of a priority sort is self-explanatory — no additional indicator required.

### Footer
`p Priority` and `s Sort` both `show=True`. The list-focused footer becomes:

```
a Add · ␣ Toggle · e Edit · d Delete · p Priority · s Sort · ? Help · q Quit
```

This realises the `s?` sort key `main-screen.md` reserved as its Open Question #2 — an extension of, not a contradiction to, the shipped footer (which already lists `p Priority`).

## Edge cases

- **`p` on an empty list / no cursor row:** no-op (`current_todo_id is None`), as with every other row action. No tag, no toast.
- **Rapid `p` spam:** in creation order the tag flickers through the cycle in place; in priority sort the row hops band per press (cursor follows via `keep_id`). Each press is one controller command = one future undo entry (#9). Bounded and harmless; no debounce needed for local SQLite.
- **Cycle onto `none` in priority sort:** the row sinks to the `NULLS LAST` none band and the cursor follows it down — visible confirmation that priority was cleared.
- **Single item:** the one row shows/cycles its tag normally; sort is a visual no-op (nothing to reorder) but `s` still toggles the border-title cue.
- **10,000 items + priority sort:** ordering is one `ORDER BY` in `db.py` (`feature-6.md` §3); no per-row work, navigation stays responsive (`main-screen.md` perf note).
- **Narrow terminal:** the priority tag is **retained** — `main-screen.md` drops `due → category` first; the 4-col priority tag stays with the checkbox + truncated title (it is a primary signal, not optional meta). Only at pathological width, after due and category are gone, would priority be the last optional element to drop; if it does, the colour goes with it but the letter's absence loses only reinforcement, never a colour-only meaning.
- **Toggling completion while in priority sort (integration note):** completing/uncompleting a task moves it between the active and done bands, so — like a `p` cycle in priority mode — the row should re-sort and the cursor follow via `keep_id`. `feature-6.md` §6 wires `keep_id` for the cycle and sort handlers but the **toggle** handler (a Feature #5 flow) should mirror this in priority mode. Surfaced in Open Questions #4.

## Accessibility & degradation

- **Keyboard-only path:** `j`/`k` to the row → `p` to set/cycle priority; `s` to sort. No mouse required (`main-screen.md` §Accessibility).
- **Colour-blind safety:** every level is a distinct **letter** (`H`/`M`/`L`) or **absence** (none); colour (`$error`/`$warning`/`$text-muted`) is reinforcement only. Fully usable with colour disabled.
- **Monochrome / 16-colour:** all glyphs are ASCII — nothing to fall back. Tokens collapse to near ANSI colours with no information loss because the letters carry meaning.
- **Screen reader:** per-level words — `high priority` / `medium priority` / `low priority`; **none contributes nothing** to the label (absence, not "no priority"). Confirming the architect's `_PRIORITY_WORDS` map and label order (`completion, priority, text` → `"incomplete, high priority, Finish the quarterly report"`). The sort mode is announced via the border-title update, not per row.
- **Contrast:** lean on theme tokens (`main-screen.md` targets ≥4.5:1 for `$text` on `$surface`/`$accent`). The one pairing to keep in mind is a coloured tag on the focused-row `$accent` fill — the letter guarantees legibility regardless, so tag contrast is reinforcement, not load-bearing.

## Resolved decisions (user, 2026-07-03)

All open questions are resolved; the body above reflects the settled choices.

1. **Low-priority colour → `$text-muted`.** Confirmed (over keeping `$primary` / using `$secondary`) —
   semantic de-emphasis, taskwarrior-grounded. Reconciled in both `tasque.tcss` (`.-priority-low`)
   and `main-screen.md`'s Color Scheme table, and captured in `feature-6.md` §7.
2. **Sort mode in the border-title → `· by priority`.** Confirmed; wording `by priority`, default
   (creation order) shows **no** suffix. Wired via `_update_counts` in `feature-6.md` §6 and noted in
   `main-screen.md`'s border-title format.
3. **Cycle feedback → silent in-place tag change.** Confirmed (no toast, no ~150 ms pulse); matches
   the no-noise-for-instant-ops convention.
4. **Toggle-completion re-sort in priority mode → re-sort, cursor STAYS on position.** Resolved with
   a deliberate distinction from the cycle handler: the toggle handler re-sorts in priority mode but
   the cursor **holds its index** (the completed task slides to the done band and the next active task
   takes its place — "move on to the next thing"), **not** `keep_id`. Only the `p` cycle and `s` sort
   follow the task by id. Fully specified in `feature-6.md` §6.
5. **Accessible-label wording → `high/medium/low priority`** (architect's `_PRIORITY_WORDS`); none is
   silent. Confirmed, no change.
