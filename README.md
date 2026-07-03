# Tasque

A keyboard-driven terminal to-do app, built as a worked example of the structured agentic Claude Code workflow described in *Linux Magazine* Issue 308 (July 2026).

The app is real — SQLite persistence, undo/redo, multiple lists, search, export — but the point isn't the app. The point is showing that a small, non-trivial Python codebase can be built by AI without the usual drift, sprawl, and half-finished features that come from prompt-and-react development.

## What it does

- Add, edit, delete, and complete tasks
- Priority levels (high / medium / low) with colour coding and sorting
- Due dates with overdue highlighting
- Categories and filtering
- Undo / redo across every mutation
- Multiple lists with global search
- JSON export / import
- Fully keyboard-driven; vim-style navigation

## Running it

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Thegreenpiranha/tasque
cd tasque
uv sync
uv run python -m tasque
```

Your data lives at `%LOCALAPPDATA%\Tasque\tasque.db` on Windows, `~/.local/share/Tasque/tasque.db` on Linux, `~/Library/Application Support/Tasque/tasque.db` on macOS.

## Keys

| Key                | Action                                    |
| ------------------ | ----------------------------------------- |
| `a`                | Add task                                  |
| `Space` / `Enter`  | Toggle complete                           |
| `e`                | Edit task                                 |
| `d`                | Delete (with confirmation)                |
| `p`                | Cycle priority (none → low → med → high)  |
| `s`                | Toggle sort (creation order / priority)   |
| `j` / `k` / arrows | Navigate                                  |
| `g` / `G`          | Jump to top / bottom                      |
| `Ctrl+d` / `Ctrl+u`| Page down / up                            |
| `?`                | Help                                      |
| `q`                | Quit                                      |

## How it was built

Every feature in this repo was built by Claude Code following a structured agentic workflow:

- **Persistent project files** (`CLAUDE.md`, `PLAN.md`, `LEARNINGS.md`) carry state across `/clear` resets so the conversation can be reset without losing the rules or the plan.
- **Specialist sub-agents** in `.claude/agents/` (architect, researcher, implementer, tester, reviewer) each do focused work in their own context. The architect decides interfaces before code is written. The researcher produces UX specs referencing well-regarded TUIs (lazygit, k9s, taskwarrior-tui). The implementer writes to spec, tests first. The tester independently verifies coverage. The reviewer checks against a concrete checklist.
- **UX specs** at `docs/ux/` and **architecture designs** at `docs/architecture/` are the durable design record. Nothing load-bearing lives only in a chat transcript.
- **Skills** at `.claude/skills/` encode reusable procedures (new-feature workflow, UI component conventions, testing standards).
- **One feature per branch**, merged to `main` only when reviewed and shipped.

The result is a codebase where every design decision is on disk, every non-obvious discovery is logged in `LEARNINGS.md`, and future features can build on past ones without the model needing to hold the whole project in context.

## Licence

MIT.
