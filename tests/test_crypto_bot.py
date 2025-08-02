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

    bot = CryptoBot(Config(cfg_file))
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
        bot = CryptoBot(Config(cfg_file))
        bot.strategy = {"exchange": "binance"}
        bot.init_engine()
        assert bot.engine is fake_worker_module.Worker.return_value


def test_run_emits_metrics(tmp_path):
    cfg_file = tmp_path / "cfg.toml"
    strat_file = tmp_path / "strategy.yaml"
    strat_file.write_text("exchange: binance\n")
    cfg_file.write_text(f"[crypto_bot]\nstrategy = '{strat_file}'\n")

    bot = CryptoBot(Config(cfg_file))
    engine = MagicMock()
    engine.positions = ["pos1"]
    engine.profit = 1.23
    bot.engine = engine
    with patch.object(bot, "load_strategy"), patch.object(bot, "connect_exchange"), patch.object(bot, "init_engine"), patch(
        "agents.crypto_bot.emit_event"
    ) as emit:
        bot.run()
        engine.run.assert_called_once()
        emit.assert_called_once_with(
            "TradeSummary",
            {"positions": engine.positions, "profit": engine.profit},
            user_id="crypto_bot",
        )


def test_run_calls_stop_on_error(tmp_path):
    cfg_file = tmp_path / "cfg.toml"
    strat_file = tmp_path / "strategy.yaml"
    strat_file.write_text("exchange: binance\n")
    cfg_file.write_text(f"[crypto_bot]\nstrategy = '{strat_file}'\n")

    bot = CryptoBot(Config(cfg_file))
    engine = MagicMock()
    engine.run.side_effect = RuntimeError("boom")
    engine.stop = MagicMock()
    bot.engine = engine
    with patch.object(bot, "load_strategy"), patch.object(bot, "connect_exchange"), patch.object(
        bot, "init_engine"
    ), patch("agents.crypto_bot.emit_event") as emit:
        with pytest.raises(RuntimeError):
            bot.run()
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

    bot = CryptoBot(Config(cfg_file))
    bot.engine = engine
    with patch.object(bot, "load_strategy"), patch.object(bot, "connect_exchange"), patch.object(
        bot, "init_engine"
    ), patch("agents.crypto_bot.emit_event") as emit:
        with pytest.raises(RuntimeError):
            bot.run()
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

    bot = CryptoBot(Config(cfg_file))
    bot.engine = engine
    with patch.object(bot, "load_strategy"), patch.object(bot, "connect_exchange"), patch.object(bot, "init_engine"), patch(
        "agents.crypto_bot.emit_event"
    ) as emit:
        bot.run()
        engine.start.assert_called_once()
        emit.assert_called_once_with(
            "TradeSummary",
            {"positions": engine.positions, "profit": engine.profit},
            user_id="crypto_bot",
        )
