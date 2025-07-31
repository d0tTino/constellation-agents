# constellation-agents

This repository manages code for constellation agents.

## Continuous Integration

GitHub Actions runs Ruff and Pytest on pushes that modify Python source files.
Tests and linting only trigger when code changes occur—documentation updates
or comment-only edits are ignored. If `pyproject.toml` is missing, Ruff runs
directly and tests are skipped.
