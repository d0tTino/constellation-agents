# constellation-agents

This repository manages code for constellation agents.

## Continuous Integration

GitHub Actions runs Ruff and Pytest on pushes that modify Python source files.
Tests and linting only trigger when code changes occur—documentation updates
or comment-only edits are ignored. If `pyproject.toml` is missing, Ruff runs
directly and tests are skipped.


## Configuration

Use the `Config` class in `agents.config` to load settings from a TOML file. The
configuration automatically reloads when the process receives a `SIGHUP` signal.

```python
from agents.config import Config

cfg = Config("settings.toml")
value = cfg.get("some_key")
```

Sending `SIGHUP` causes `cfg` to reload the file at runtime.
