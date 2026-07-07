# Tasque

A keyboard-driven terminal to-do app.

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
