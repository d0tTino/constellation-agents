from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.config import Config
from agents.crypto_bot import CryptoBot


def test_load_strategy_and_connect(tmp_path):
    cfg_file = tmp_path / "cfg.toml"
    strat_file = tmp_path / "strategy.yaml"
    strat_file.write_text("exchange: binance\n")
    cfg_file.write_text(f"[crypto_bot]\nstrategy = '{strat_file}'\n")

    bot = CryptoBot(Config(cfg_file), user_id="u1")
    bot.load_strategy()
    assert bot.strategy == {"exchange": "binance"}

    with patch("ccxt.binance") as binance_cls:
        binance_cls.return_value = MagicMock()
        bot.connect_exchange()
        binance_cls.assert_called_once()


def test_init_engine_uses_freqtrade_modules(tmp_path):
    cfg_file = tmp_path / "cfg.toml"
    strat_file = tmp_path / "strategy.yaml"
    strat_file.write_text("exchange: binance\n")
    cfg_file.write_text(f"[crypto_bot]\nstrategy = '{strat_file}'\n")

    fake_worker_module = ModuleType("freqtrade.worker")
    fake_configuration_module = ModuleType("freqtrade.configuration")
    fake_worker_module.Worker = MagicMock()
    fake_configuration_module.Configuration = MagicMock(return_value=MagicMock(get_config=MagicMock(return_value={})))
    with patch.dict(sys.modules, {
        "freqtrade.worker": fake_worker_module,
        "freqtrade.configuration": fake_configuration_module,
    }):
        bot = CryptoBot(Config(cfg_file), user_id="u1")
        bot.strategy = {"exchange": "binance"}
        bot.init_engine()
        assert bot.engine is fake_worker_module.Worker.return_value


def test_run_emits_metrics(tmp_path):
    cfg_file = tmp_path / "cfg.toml"
    strat_file = tmp_path / "strategy.yaml"
    strat_file.write_text("exchange: binance\n")
    cfg_file.write_text(f"[crypto_bot]\nstrategy = '{strat_file}'\n")

    bot = CryptoBot(Config(cfg_file), user_id="u1")
    engine = MagicMock()
    engine.positions = ["pos1"]
    engine.profit = 1.23
    bot.engine = engine
    with patch.object(bot, "load_strategy"), patch.object(bot, "connect_exchange"), patch.object(bot, "init_engine"), patch(
        "agents.crypto_bot.emit_event"
    ) as emit, patch("agents.crypto_bot.check_permission", return_value=True) as cp:
        bot.run()
    engine.run.assert_called_once()
    cp.assert_called_once_with("u1", "trade", None)
    emit.assert_called_once_with(
        "TradeSummary",
        {"positions": engine.positions, "profit": engine.profit},
        user_id="u1",
    )


def test_run_exits_without_emitting_when_permission_denied(tmp_path):
    cfg_file = tmp_path / "cfg.toml"
    strat_file = tmp_path / "strategy.yaml"
    strat_file.write_text("exchange: binance\n")
    cfg_file.write_text(f"[crypto_bot]\nstrategy = '{strat_file}'\n")

    bot = CryptoBot(Config(cfg_file), user_id="u1")
    with patch.object(bot, "load_strategy") as load, patch.object(bot, "connect_exchange") as connect, patch.object(
        bot, "init_engine"
    ) as init, patch("agents.crypto_bot.emit_event") as emit, patch(
        "agents.crypto_bot.check_permission", return_value=False
    ) as cp:
        bot.run()
    cp.assert_called_once_with("u1", "trade", None)
    load.assert_not_called()
    connect.assert_not_called()
    init.assert_not_called()
    emit.assert_not_called()


def test_run_calls_stop_on_error(tmp_path):
    cfg_file = tmp_path / "cfg.toml"
    strat_file = tmp_path / "strategy.yaml"
    strat_file.write_text("exchange: binance\n")
    cfg_file.write_text(f"[crypto_bot]\nstrategy = '{strat_file}'\n")

    bot = CryptoBot(Config(cfg_file), user_id="u1")
    engine = MagicMock()
    engine.run.side_effect = RuntimeError("boom")
    engine.stop = MagicMock()
    bot.engine = engine
    with patch.object(bot, "load_strategy"), patch.object(bot, "connect_exchange"), patch.object(
        bot, "init_engine"
    ), patch("agents.crypto_bot.emit_event") as emit, patch(
        "agents.crypto_bot.check_permission", return_value=True
    ) as cp:
        with pytest.raises(RuntimeError):
            bot.run()
    cp.assert_called_once_with("u1", "trade", None)
    engine.stop.assert_called_once()
    emit.assert_not_called()


def test_run_calls_close_on_error(tmp_path):
    cfg_file = tmp_path / "cfg.toml"
    strat_file = tmp_path / "strategy.yaml"
    strat_file.write_text("exchange: binance\n")
    cfg_file.write_text(f"[crypto_bot]\nstrategy = '{strat_file}'\n")

    engine = MagicMock(spec=["start", "close"])
    engine.start.side_effect = RuntimeError("boom")
    engine.close = MagicMock()

    bot = CryptoBot(Config(cfg_file), user_id="u1")
    bot.engine = engine
    with patch.object(bot, "load_strategy"), patch.object(bot, "connect_exchange"), patch.object(
        bot, "init_engine"
    ), patch("agents.crypto_bot.emit_event") as emit, patch(
        "agents.crypto_bot.check_permission", return_value=True
    ) as cp:
        with pytest.raises(RuntimeError):
            bot.run()
    cp.assert_called_once_with("u1", "trade", None)
    engine.close.assert_called_once()
    emit.assert_not_called()


def test_run_emits_metrics_when_start_used(tmp_path):
    cfg_file = tmp_path / "cfg.toml"
    strat_file = tmp_path / "strategy.yaml"
    strat_file.write_text("exchange: binance\n")
    cfg_file.write_text(f"[crypto_bot]\nstrategy = '{strat_file}'\n")

    engine = MagicMock(spec=["start", "positions", "profit"])
    engine.start = MagicMock()
    engine.positions = ["pos1"]
    engine.profit = 2.34

    bot = CryptoBot(Config(cfg_file), user_id="u1")
    bot.engine = engine
    with patch.object(bot, "load_strategy"), patch.object(bot, "connect_exchange"), patch.object(bot, "init_engine"), patch(
        "agents.crypto_bot.emit_event"
    ) as emit, patch("agents.crypto_bot.check_permission", return_value=True) as cp:
        bot.run()
    engine.start.assert_called_once()
    cp.assert_called_once_with("u1", "trade", None)
    emit.assert_called_once_with(
        "TradeSummary",
        {"positions": engine.positions, "profit": engine.profit},
        user_id="u1",
    )


def test_run_emits_metrics_with_group(tmp_path):
    cfg_file = tmp_path / "cfg.toml"
    strat_file = tmp_path / "strategy.yaml"
    strat_file.write_text("exchange: binance\n")
    cfg_file.write_text(f"[crypto_bot]\nstrategy = '{strat_file}'\n")

    bot = CryptoBot(Config(cfg_file), user_id="u1", group_id="g1")
    engine = MagicMock()
    engine.positions = ["pos1"]
    engine.profit = 1.23
    bot.engine = engine
    with patch.object(bot, "load_strategy"), patch.object(bot, "connect_exchange"), patch.object(
        bot, "init_engine"
    ), patch("agents.crypto_bot.emit_event") as emit, patch(
        "agents.crypto_bot.check_permission", return_value=True
    ) as cp:
        bot.run()
    engine.run.assert_called_once()
    cp.assert_called_once_with("u1", "trade", "g1")
    emit.assert_called_once_with(
        "TradeSummary",
        {"positions": engine.positions, "profit": engine.profit},
        user_id="u1",
        group_id="g1",
    )
