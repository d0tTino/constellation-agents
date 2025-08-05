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


## UME Permissions

The SDK communicates with the Unified Messaging Engine (UME) for permission
checks.  Use `agents.sdk.check_permission` to verify whether a user may perform
an action.  The function posts to the endpoint defined by the
`UME_PERMISSION_ENDPOINT` environment variable, defaulting to
`http://localhost:8000/permissions/check`.

Requests are routed through the optional OPA sidecar in the same manner as
`agents.sdk.ume_query`.  When `OPA_SIDECAR_URL` is set, the original endpoint
and payload are wrapped and sent to the sidecar URL instead of directly to the
UME service.

## CalendarNLPAgent

Translates natural language requests into structured calendar events.

**Topics**

- Consumes: `calendar.nl.request`
- Produces: `calendar.event.create_request`

**Payloads**

- Incoming `calendar.nl.request`

  ```json
  {"text": "Lunch with Sam at noon", "user_id": "u1", "group_id": "g1"}
  ```

- Outgoing `calendar.event.create_request`

  ```json
  {
    "group_id": "g1",
    "event": {
      "title": "Lunch",
      "start_time": "2024-01-01T12:00:00",
      "end_time": "2024-01-01T13:00:00",
      "location": "Cafe",
      "description": "Lunch with Sam",
      "is_all_day": false,
      "recurrence": null
    }
  }
  ```

**Permission model**

```python
from agents.sdk import check_permission

if check_permission(user_id, "calendar:create", group_id):
    agent.emit(
        "calendar.event.create_request",
        {"group_id": group_id, "event": calendar_event},
        user_id=user_id,
        group_id=group_id,
    )
```

## ExplainabilityAgent

Provides human‑readable explanations for financial analyses.

**Topics**

- Consumes: `finance.explain.request`
- Produces: `finance.explain.result`

**Payloads**

- Incoming `finance.explain.request`

  ```json
  {"analysis_id": "a1", "user_id": "u1"}
  ```

- Outgoing `finance.explain.result`

  ```json
  {
    "analysis_id": "a1",
    "explanations": [
      {"action": "invest", "pros": "growth", "cons": "risk"}
    ]
  }
  ```

**Permission model**

```python
from agents.sdk import check_permission

if not check_permission(user_id, "analysis:read"):
    return
```

## PlaidSyncAgent

Synchronizes transactions from Plaid and emits updates.

**Topics**

- Consumes: `plaid.transactions.sync`
- Produces: `plaid.transaction.synced`

**Payloads**

- Incoming `plaid.transactions.sync`

  ```json
  {"user_id": "u1", "group_id": "g1"}
  ```

- Outgoing `plaid.transaction.synced`

  ```json
  {
    "id": "t1",
    "amount": 42,
    "user_id": "u1",
    "group_id": "g1"
  }
  ```

**Permission model**

```python
from agents.sdk import check_permission

if not check_permission(user_id, "read", group_id):
    return
transactions = plaid.fetch_transactions(user_id)
if check_permission(user_id, "write", group_id):
    for tx in transactions:
        agent.emit("plaid.transaction.synced", tx, user_id=user_id, group_id=group_id)
```

## Event Topics

| Topic | Produced By | Consumed By | Required identifiers |
| ----- | ----------- | ----------- | -------------------- |
| `calendar.nl.request` | client applications | CalendarNLPAgent | `user_id`, `text`, `group_id` (optional) |
| `calendar.event.create_request` | CalendarNLPAgent | calendar service | `user_id`, `group_id` (optional), event fields |
| `finance.explain.request` | analytics service | ExplainabilityAgent | `user_id`, `analysis_id` |
| `finance.explain.result` | ExplainabilityAgent | clients | `user_id`, `analysis_id` |
| `plaid.transactions.sync` | scheduler | PlaidSyncAgent | `user_id`, `group_id` (optional) |
| `plaid.transaction.synced` | PlaidSyncAgent | transaction processor | `user_id`, `group_id` (optional), transaction fields |

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
