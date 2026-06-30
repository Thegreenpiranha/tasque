---
name: testing
description: Use when writing, modifying, running, or reviewing tests for the project. Covers what to test, what not to test, structure, naming, fixtures, coverage targets, and the rule that tests are written against behaviour — never modified to paper over broken code.
---

# Testing Skill

The project's testing conventions. The point is signal, not coverage theatre.

## What to Test

- **Public behaviour of every module.** What it accepts, what it returns, what it does to state, what it raises.
- **Every state in a UX spec.** Empty, loading, populated, error, focused. If the spec defines a state, there's a test for it.
- **Error paths.** What happens when the input is wrong, the file is missing, the DB is locked, the network is slow.
- **Edge cases.** Empty input, single-item, very large input, boundary values (0, 1, max).
- **Regressions.** Every bug found gets a test that would have caught it.

## What Not to Test

- **Implementation details.** Private functions, internal data structures, the exact SQL string. If renaming a private helper breaks a test, the test is wrong.
- **The framework.** Don't test that `useState` updates state, or that pytest discovers tests. Test your code.
- **Generated code.** Migrations, ORM scaffolding, type stubs. Test the behaviour they enable.

## Structure

```
tests/
├── unit/           # one module at a time, no I/O
│   ├── test_<module_name>.py
├── integration/    # multiple modules together, in-memory persistence
│   ├── test_<feature>.py
└── e2e/            # full app, rare, slow
    └── test_<scenario>.py
```

Mirror the structure of `src/`. Tests for `src/widgets/list.py` live in `tests/unit/widgets/test_list.py`.

## Naming

- `test_<thing>_<behaviour>_when_<condition>` — e.g. `test_add_task_returns_task_when_input_is_valid`.
- Describe **behaviour**, not implementation. `test_add_task_calls_db_insert` is wrong — it tests how, not what.

## Test Body Shape

Arrange / Act / Assert. Visible whitespace between sections. One behavioural assertion per test where possible (multiple `assert` lines on one logical outcome is fine).

```python
def test_add_task_assigns_unique_id():
    # arrange
    repo = InMemoryTaskRepo()

    # act
    a = repo.add("buy milk")
    b = repo.add("buy bread")

    # assert
    assert a.id != b.id
```

## Fixtures and Mocking

- **Prefer real dependencies** with an in-memory backend (SQLite `:memory:`, in-memory queue, etc.) over mocks. Mocks lie.
- **Mock only at the boundary** — third-party APIs you can't call from tests, system clock, randomness.
- **No global fixtures with hidden state.** If a fixture mutates module-level state, fix it.
- **Each test sets up its own world.** Tests don't depend on order. Run any single test in isolation and it passes.

## Coverage

- Per-module floor: **80% line coverage** unless there's a documented reason in `LEARNINGS.md`.
- Coverage is a floor, not a target. 100% coverage with bad tests is worse than 80% with good ones.
- **A line being covered is not the same as a behaviour being tested.** Coverage tools count execution, not assertion quality.
- Look at coverage **per module**, not the overall number. A 95% overall coverage can hide a 30%-covered persistence layer.

## The Cardinal Rule

**Tests document behaviour. They do not exist to be green.**

When a test fails:

1. First, check whether the test or the code is wrong. If the spec says X and the code does Y, the code is wrong.
2. If the code is wrong, **fix the code**.
3. If the test is wrong (it asserts a behaviour that was never specified), **fix the test** — and add a `LEARNINGS.md` entry explaining why so it doesn't happen again.
4. **Never** change the expected value to match the (broken) actual just to make the suite green. This is the failure mode the article calls out as "tests papered over bugs rather than catching them."

## Running Tests

- The full suite runs in CI on every change.
- Locally, run the suite **after every meaningful change**, not at the end. Catching a failure early costs minutes; catching it after another feature is layered on costs hours.
- Slow tests are tagged (`@pytest.mark.slow` or equivalent) but still run in the full pass — don't let them rot.

## Reviewing Tests

When reviewing someone's (or your own past) tests, ask:

- Can this assertion ever fail? (If not, delete or rewrite.)
- Would this test catch a real regression I can imagine? (If not, it's decoration.)
- Does this test break when I refactor a private detail? (If yes, it's over-specified.)
- Is the test name describing behaviour or implementation? (Implementation = rewrite.)
