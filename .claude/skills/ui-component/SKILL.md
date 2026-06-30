---
name: ui-component
description: Use when building or modifying any user interface component — a widget, screen, modal, form, or any other visual element. This skill defines the conventions for component structure, state, props/inputs, accessibility, and coherence with the project's established visual language in docs/ux/.
---

# UI Component Skill

The procedure for building UI components so they stay coherent across features. This is what stops the "three competing color systems" failure mode the article calls out.

## Step 1 — Read All UX Specs, Not Just the New One

Read **every** file in `docs/ux/`. Not the one for the feature you're building — all of them. The point is to spot:

- Color tokens already in use (so you don't introduce a fourth red).
- Layout patterns already established (sidebar vs tab bar, modal vs inline edit).
- Interaction conventions (where does focus go after a modal closes? which key cancels?).
- Empty-state and error-state patterns.

If your new component would clash with an existing pattern, stop. Either match the existing pattern, or surface the conflict and propose a unified update.

## Step 2 — Match the Visual System

Use the existing palette, type scale, spacing, and motion vocabulary. Do not introduce a new color, font size, or animation curve unless the researcher's new spec explicitly defines one and explains why it's needed.

When in doubt: copy the closest existing component and modify, rather than starting blank.

## Step 3 — Component Structure

Components follow the project's framework conventions (see CLAUDE.md), but at minimum:

- **One component per file** unless they're trivially small and tightly coupled.
- **Props/inputs at the top**, with types and defaults.
- **State is local by default**; lift to a parent only when two siblings need it.
- **Side effects in lifecycle methods/hooks**, not inline in render/template.
- **No business logic in the view.** Display logic only. If it's a calculation or a rule, it belongs in the model/controller layer.

## Step 4 — Implement Every State in the Spec

The researcher's spec lists states: empty, loading, populated, focused, error, success. **Build all of them.** Not just the populated state.

The empty state is the one most often skipped — and it's where new users live. Build it first if you want a useful exercise in clarity.

## Step 5 — Accessibility Checklist

Before you call the component done:

- [ ] Reachable by keyboard. Tab order is sensible.
- [ ] Visible focus indicator (don't rely on the browser/terminal default; it's often too subtle).
- [ ] Meaning isn't conveyed by color alone (use icons, text, or shape too).
- [ ] Interactive elements have labels (aria-label, alt text, or terminal equivalents).
- [ ] Color contrast meets WCAG AA on both dark and light backgrounds (for terminal apps: test in both light and dark terminal themes).
- [ ] Modals trap focus while open and return it sensibly on close.

## Step 6 — Test What the User Sees

For each state in the spec, write a test that:

- Renders the component in that state.
- Asserts the user-visible result (text, classes, structure).
- Where applicable, asserts the keyboard interaction works.

Don't test implementation details. Renaming a private method must not break a test.

## Step 7 — Integration With Surrounding Components

Before declaring done:

- Drop the component into the actual screen it'll live in. Check spacing and alignment against the layout in the UX spec.
- Verify it works alongside any sibling components — no z-index conflicts, no overlapping shortcuts.
- Verify keyboard navigation flows in and out of the new component without dead ends.

## Anti-Patterns to Avoid

- **Inventing a new color for "just this one thing."** It compounds. Use a token.
- **Building only the happy path.** Empty and error states are not optional.
- **Hardcoded strings.** Use the project's i18n/strings convention if there is one.
- **Inline styles that contradict the design system.** If you need an exception, document why and put it in a comment with a reference to the issue.
- **Inconsistent shortcut conventions** (e.g. `q` quits in one screen but does nothing in another). Establish the convention and stick to it.
