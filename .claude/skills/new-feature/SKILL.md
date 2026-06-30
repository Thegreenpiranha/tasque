---
name: new-feature
description: Use when implementing a new feature from PLAN.md. This skill defines the standard sequence — read context, architect, research (if UI), implement with tests, verify, update PLAN.md and LEARNINGS.md. Follow this whenever moving a feature from Backlog to Done so the project keeps its consistency across sessions.
---

# New Feature Skill

The procedure for taking a feature from Backlog to Done. Follow it in order. Skipping steps is how the project drifts.

## Step 1 — Read the Context

Before anything else, read:

1. `CLAUDE.md` — conventions, tech stack, architectural rules, Definition of Done.
2. `PLAN.md` — the feature, its acceptance criteria, its dependencies.
3. `LEARNINGS.md` — for gotchas and decisions already logged.
4. If the feature involves UI: every file in `docs/ux/`.

If any of those are missing or contradict the feature being asked for, surface it before continuing.

## Step 2 — Move the Feature to In Progress

Edit `PLAN.md`: move the feature from **Backlog** to **In Progress**. This is the marker that work has started. Do it now, not later.

## Step 3 — Architect (if the feature has structural decisions)

Use the **architect** sub-agent if the feature:
- Introduces a new module or significantly changes one.
- Changes the data model or requires a migration.
- Adds a new public API or changes an existing signature.
- Touches multiple existing modules.

The architect produces a written design. Read it before you write code.

For trivial features (e.g. "rename a button label"), you can skip the architect — but document why in your final summary so the reviewer knows it was a deliberate choice, not an omission.

## Step 4 — Research (if the feature has UI)

Use the **researcher** sub-agent for any feature that has a user interface or interaction. The researcher produces a spec at `docs/ux/<feature>.md`.

Read every existing spec in `docs/ux/` so the new one is coherent with what's there.

## Step 5 — Implement

Use the **implementer** sub-agent (or do it in the main session — your call based on context budget).

The implementer:
1. Writes the test first.
2. Watches it fail.
3. Writes the minimum code to pass it.
4. Refactors with the test still passing.
5. Repeats for each behaviour in the spec.

Follow the conventions in CLAUDE.md exactly. Build to the architect's signatures and the researcher's spec exactly. If either is wrong, stop and surface it — do not silently "improve" the spec.

## Step 6 — Test

Use the **tester** sub-agent to:
- Run the full suite.
- Verify per-module coverage.
- Fill any gaps with real tests.

If any test fails, hand back to the implementer. Don't make tests match broken code.

## Step 7 — Review

Use the **reviewer** sub-agent against the checklist:
- Conventions, architectural rules, UX compliance, test quality, cross-feature consistency, Definition of Done.

Fix any 🔴 Critical or 🟡 Warning findings before moving on. 🟢 Suggestions can become backlog items.

## Step 8 — Update PLAN.md and LEARNINGS.md

1. Move the feature in `PLAN.md` from **In Progress** to **Done**, with the date.
2. If anything non-obvious was discovered during the build, add a dated entry to `LEARNINGS.md` with the appropriate tag.

## Step 9 — Report

Summarise what shipped:

```
## Shipped: <feature name>

**Architect output:** <summary or "skipped — trivial change">
**UX spec:** docs/ux/<feature>.md (or "no UI changes")
**Files changed:** <list>
**Tests added:** <count>
**Coverage:** <delta>
**Review verdict:** PASS / PASS WITH WARNINGS
**LEARNINGS.md entries added:** <slugs or "none">
**PLAN.md:** moved to Done on <date>

**Manual verification:** <what the human should try, or "none — fully covered by tests">
```

## When to Break the Sequence

The sequence exists so consistency is the default. You can deviate when there's a real reason — but document it:

- "Skipped architect step — the change was a one-line copy edit."
- "Skipped researcher step — feature is back-end only, no UI surface."
- "Ran tester before reviewer because the suite was already red from a prior session and needed clearing before review could be meaningful."

Never skip silently. The reviewer needs to know what was skipped to do their job.
