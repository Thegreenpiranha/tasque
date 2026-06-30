# Agentic Workflow Scaffold

The idea: persistent project files (`CLAUDE.md`, `PLAN.md`, `LEARNINGS.md`) carry state across `/clear` resets, and specialist sub-agents (architect, researcher, implementer, tester, reviewer) do focused work in their own contexts. Skills encode reusable procedures. The result is a workflow that survives context limits and doesn't drift over many features.

## Structure

```
.
├── CLAUDE.md            # project conventions, tech stack, Definition of Done
├── PLAN.md              # backlog / in progress / done ledger
├── LEARNINGS.md         # discoveries and decisions logged as we go
├── docs/
│   └── ux/              # UX specs the researcher saves here
└── .claude/
    ├── agents/
    │   ├── architect.md    # designs interfaces before code
    │   ├── researcher.md   # produces UX specs from existing solutions
    │   ├── implementer.md  # writes code to spec, tests first
    │   ├── tester.md       # runs suite, fills coverage gaps
    │   └── reviewer.md     # checks against checklist by severity
    └── skills/
        ├── new-feature/SKILL.md   # the standard feature procedure
        ├── ui-component/SKILL.md  # UI component conventions
        └── testing/SKILL.md       # testing conventions
```

## How to Use

1. **Drop this whole tree into the root of a new or existing project.**
2. **Fill in CLAUDE.md.** Replace the placeholders with your project's real tech stack, conventions, and architectural rules. This is the most important file — sub-agents read it first.
3. **Define your features in PLAN.md.** Each feature in the Backlog gets a goal, acceptance criteria, and any dependencies.
4. **Start a Claude Code session** (`claude` in the project root). It picks up `CLAUDE.md` automatically and the `.claude/` folder makes the agents and skills available.

## The Loop, Per Feature

From the article, condensed:

1. `/clear` — reset context. The project files carry state forward.
2. Tell Claude Code to follow the **new-feature** skill on the next item from `PLAN.md`.
3. The skill drives the sequence: read context → architect → research (if UI) → implement → test → review → update PLAN.md and LEARNINGS.md.
4. Each step can invoke its sub-agent (or run in the main session — your call based on context budget).

## Invoking Sub-Agents

In Claude Code:

```
Use the architect sub-agent to design feature #3 in PLAN.md.
```

```
Use the researcher sub-agent to produce a UX spec for feature #4.
Save it to docs/ux/feature-4.md.
```

```
Use the implementer sub-agent to build feature #3 following the architect's design
and the new-feature skill.
```

```
Use the tester sub-agent to run the suite and fill coverage gaps in the modules
touched by feature #3.
```

```
Use the reviewer sub-agent on the work for feature #3. Report by severity.
```

## Customising

- **Models per agent:** all five agents are set to `model: inherit` so they use whatever your main session is on. If you want the architect and reviewer on Opus and the implementer on Sonnet to save tokens, edit the `model:` line in each agent file (`opus`, `sonnet`, `haiku`, or a full model ID).
- **Tools per agent:** the `tools:` lines are deliberately narrow. The reviewer has read-only tools; the architect can't write code. Adjust if your project has more constrained needs.
- **More skills:** add `.claude/skills/<name>/SKILL.md` for procedures specific to your codebase (e.g. `migration`, `release`, `incident-response`).
- **More agents:** add `.claude/agents/<name>.md` for specialists — a security auditor, a performance profiler, a documentation writer. Keep each one tightly scoped.

## What This Costs

Sub-agent-heavy workflows use more tokens than a single-thread session because each agent maintains its own context. The trade-off is that the main session stays clean and the project doesn't drift. For small features, run in the main session; bring in sub-agents when the work is structurally significant or context is getting heavy.
