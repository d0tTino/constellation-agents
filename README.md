# constellation-agents

This repository manages code for constellation agents.

## Continuous Integration

GitHub Actions runs Ruff and Pytest on pushes that modify Python source files.
Tests and linting only trigger when code changes occur—documentation updates
or comment-only edits are ignored. If `pyproject.toml` is missing, Ruff runs
directly and tests are skipped.

## Setup

Install the Python dependencies with [Poetry](https://python-poetry.org/):

```bash
pip install poetry
poetry install
```



## Configuration

Use the `Config` class in `agents.config` to load settings from a TOML file. The
configuration automatically reloads when the process receives a `SIGHUP` signal.

```python
from agents.config import Config

cfg = Config("settings.toml")
value = cfg.get("some_key")
```

Sending `SIGHUP` causes `cfg` to reload the file at runtime.

All agents load configuration through the same mechanism. Specify the path
with the `--config` command line option or `CONFIG_PATH` environment
variable. If omitted, agents default to a `config.toml` file in the current
directory.

Set `CONFIG_PATH` or pass `--config` to point agents at a different file:

```bash
CONFIG_PATH=/srv/agents.toml python -m agents.crypto_bot
```


## FinRL Strategist

The package `agents.finrl_strategist` integrates the [FinRL](https://github.com/AI4Finance-Foundation/FinRL) framework.
It exposes a `FinRLStrategist` class that executes a 30‑day back‑test using a DRL policy. The strategists only run
on Mondays via the `run_weekly` method, which loads the latest 30 days of market data and trains a PPO model before
producing predictions.

## Docker Images

Each agent directory contains a `Dockerfile` for containerized execution. After installing dependencies, build the images from the repository root:

```bash
docker build -t finance-advisor -f agents/finance_advisor/Dockerfile .
docker build -t crypto-bot -f agents/crypto_bot/Dockerfile .
docker build -t finrl-strategist -f agents/finrl_strategist/Dockerfile .
```

Run the containers with:

```bash
docker run --rm finance-advisor
docker run --rm crypto-bot
docker run --rm finrl-strategist
```

Pass `CONFIG_PATH` to override the default configuration file inside the
container:

```bash
docker run --rm -e CONFIG_PATH=/srv/agents.toml crypto-bot
```
