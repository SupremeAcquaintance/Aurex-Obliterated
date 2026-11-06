import re
from pathlib import Path

from aurex.backtest_engine.service import (
    JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE,
    JAM_REVERSAL_V1_PARAMETER_TEMPLATE,
    SLOW_BREAKOUT_SPOT_V1_PARAMETER_TEMPLATE,
    VOLATILITY_BREAKOUT_V1_PARAMETER_TEMPLATE,
    backtest_strategy_setup,
    strategy_parameter_fingerprint,
)
from aurex.strategy_engine.registry import REGISTERED_STRATEGIES

PINE_PATHS = [
    Path("pine/strategies/trend_pullback_v1.pine"),
    Path("pine/strategies/volatility_breakout_v1.pine"),
    Path("pine/strategies/range_mean_reversion_v1.pine"),
    Path("pine/strategies/atk_def_swing_sr_atr_v1.pine"),
    Path("pine/strategies/jam_reversal_v1.pine"),
    Path("pine/strategies/jam_reversal_spot_v1.pine"),
    Path("pine/strategies/slow_breakout_spot_v1.pine"),
]


def test_pine_strategy_contracts() -> None:
    required_fragments = [
        "//@version=6",
        "strategy(",
        "strategy.entry",
        "strategy.exit",
        "alert(",
        "barstate.isconfirmed",
        "calc_on_every_tick = false",
        "process_orders_on_close = true",
    ]

    for path in PINE_PATHS:
        source = path.read_text(encoding="utf-8")
        assert path.stem in source

        for fragment in required_fragments:
            assert fragment in source

    for path in PINE_PATHS[:-1]:
        assert "request.security" in path.read_text(encoding="utf-8")


def test_pine_payloads_contain_aurex_required_fields() -> None:
    required_payload_keys = [
        "source",
        "strategy",
        "symbol",
        "timeframe",
        "direction",
        "entry_price",
        "stop_loss",
        "take_profit",
        "market_regime",
        "timestamp",
    ]

    for path in PINE_PATHS:
        source = path.read_text(encoding="utf-8")
        for key in required_payload_keys:
            assert key in source


def test_pine_strategies_avoid_known_repaint_risk_pattern() -> None:
    trend_pullback = PINE_PATHS[0].read_text(encoding="utf-8")
    assert "ta.ema(close, htfEmaFastLength)[1]" in trend_pullback
    assert "ta.ema(close, htfEmaSlowLength)[1]" in trend_pullback
    assert trend_pullback.count("lookahead = barmerge.lookahead_on") == 2
    assert "ta.ema(close, htfEmaFastLength)," not in trend_pullback
    assert "ta.ema(close, htfEmaSlowLength)," not in trend_pullback

    volatility_breakout = PINE_PATHS[1].read_text(encoding="utf-8")
    assert "ta.ema(close, emaFastLength)[1]" in volatility_breakout
    assert "ta.ema(close, emaSlowLength)[1]" in volatility_breakout
    assert volatility_breakout.count("lookahead = barmerge.lookahead_on") == 2
    assert "ta.ema(close, emaFastLength)," not in volatility_breakout
    assert "ta.ema(close, emaSlowLength)," not in volatility_breakout

    for path in PINE_PATHS[2:5]:
        source = path.read_text(encoding="utf-8")
        assert "lookahead = barmerge.lookahead_off" in source
        assert "barmerge.lookahead_on" not in source

    jam_reversal_spot = PINE_PATHS[5].read_text(encoding="utf-8")
    assert "ta.ema(close, htfEmaFastLength)[1]" in jam_reversal_spot
    assert "ta.ema(close, htfEmaSlowLength)[1]" in jam_reversal_spot
    assert jam_reversal_spot.count("lookahead = barmerge.lookahead_on") == 2

    slow_breakout = PINE_PATHS[-1].read_text(encoding="utf-8")
    assert "request.security" not in slow_breakout
    assert "barmerge.lookahead_on" not in slow_breakout


def test_trend_pullback_export_order_ids_preserve_regime_evidence() -> None:
    source = Path("pine/strategies/trend_pullback_v1.pine").read_text(encoding="utf-8")

    assert "AUREX-LONG-TRENDING_UP" in source
    assert "AUREX-SHORT-TRENDING_DOWN" in source


def test_trend_pullback_enforces_recorded_backtest_cost_and_date_controls() -> None:
    source = Path("pine/strategies/trend_pullback_v1.pine").read_text(encoding="utf-8")

    assert "Aurex strategy version: 1.3.0" in source
    assert "commission_value = 0.05" in source
    assert "slippage = 2" in source
    assert 'input.time(timestamp("1 Jan 2024 00:00 +0000"), "Backtest start")' in source
    assert 'input.time(timestamp("31 Dec 2026 23:59 +0000"), "Backtest end")' in source
    assert "inBacktestWindow" in source
    assert 'input.float(0.5, "Risk per trade (%)"' in source
    assert 'input.float(95.0, "Max position value (%)"' in source
    assert "riskCapital / (longRisk * contractPointValue)" in source
    assert "riskCapital / (shortRisk * contractPointValue)" in source
    assert "syminfo.mincontract" in source
    assert "syminfo.pointvalue" in source
    assert "math.floor(longQuantityRaw / minimumContract)" in source
    assert "backtestExitBar" in source
    assert "qty = longQuantity" in source
    assert "qty = shortQuantity" in source


def test_trend_pullback_has_diagnostics_without_loosening_entry_gates() -> None:
    source = Path("pine/strategies/trend_pullback_v1.pine").read_text(encoding="utf-8")

    assert 'input.bool(true, "Show diagnostic table", group = "Diagnostics")' in source
    assert "table.new(position.top_right, 3, 15" in source
    assert "Aurex diagnostics" in source
    assert "Latest blocker" in source
    assert "Open trades" in source
    assert "Closed trades" in source
    assert "Orders submitted" in source
    assert "Filled entries" in source
    assert "strategy.opentrades" in source
    assert "strategy.closedtrades" in source
    assert "longBlocker =" in source
    assert "shortBlocker =" in source
    assert "diagnosticBars" in source
    assert "longSetupCount" in source
    assert "shortSetupCount" in source


def test_registered_trend_pullback_version_matches_pine_source() -> None:
    source = Path("pine/strategies/trend_pullback_v1.pine").read_text(encoding="utf-8")
    match = re.search(r'strategyVersion = "([^"]+)"', source)

    assert match is not None
    assert REGISTERED_STRATEGIES["trend_pullback_v1"].version == match.group(1)


def test_registered_volatility_breakout_version_matches_pine_source() -> None:
    source = Path("pine/strategies/volatility_breakout_v1.pine").read_text(
        encoding="utf-8"
    )
    match = re.search(r'strategyVersion = "([^"]+)"', source)

    assert match is not None
    assert REGISTERED_STRATEGIES["volatility_breakout_v1"].version == match.group(1)


def test_registered_slow_breakout_spot_version_matches_pine_source() -> None:
    source = Path("pine/strategies/slow_breakout_spot_v1.pine").read_text(
        encoding="utf-8"
    )
    match = re.search(r'strategyVersion = "([^"]+)"', source)

    assert match is not None
    assert REGISTERED_STRATEGIES["slow_breakout_spot_v1"].version == match.group(1)


def test_registered_jam_reversal_version_matches_pine_source() -> None:
    source = Path("pine/strategies/jam_reversal_v1.pine").read_text(encoding="utf-8")
    match = re.search(r'strategyVersion = "([^"]+)"', source)

    assert match is not None
    assert REGISTERED_STRATEGIES["jam_reversal_v1"].version == match.group(1)


def test_registered_jam_reversal_spot_version_matches_pine_source() -> None:
    source = Path("pine/strategies/jam_reversal_spot_v1.pine").read_text(
        encoding="utf-8"
    )
    match = re.search(r'strategyVersion = "([^"]+)"', source)

    assert match is not None
    assert REGISTERED_STRATEGIES["jam_reversal_spot_v1"].version == match.group(1)


def test_trend_pullback_payload_carries_backtest_provenance() -> None:
    source = Path("pine/strategies/trend_pullback_v1.pine").read_text(encoding="utf-8")

    assert 'strategyVersion = "1.3.0"' in source
    assert "settingsFingerprint() =>" in source
    assert "strategy_version" in source
    assert "settings_fingerprint" in source
    assert "|pullback_ema_fast=" in source
    assert "|risk_per_trade_percent=" in source
    assert "|enable_short=" in source

    assert (
        "longSetup = enableLong and flatPosition and entryWindow and "
        "barstate.isconfirmed and longTrend and nearPullbackZone and longRsiReset "
        "and bullishConfirmation and longRiskOk and longQuantityOk"
    ) in source
    assert (
        "shortSetup = enableShort and flatPosition and entryWindow and "
        "barstate.isconfirmed and shortTrend and nearPullbackZone and shortRsiReset "
        "and bearishConfirmation and shortRiskOk and shortQuantityOk"
    ) in source


def test_jam_reversal_payload_carries_import_provenance() -> None:
    source = Path("pine/strategies/jam_reversal_v1.pine").read_text(encoding="utf-8")

    assert 'strategyVersion = "1.14.0"' in source
    assert "settingsFingerprint() =>" in source
    assert "strategy_version" in source
    assert "settings_fingerprint" in source
    assert '\\"strategy\\":\\"jam_reversal_v1\\"' in source
    assert '\\"market_regime\\":\\"BREAKOUT_EXPANSION\\"' in source
    assert '|higher_timeframe_valid=" + formatBoolSetting(higherTimeframeValid)' in source
    assert '|allowed_symbol_mode=" + allowedSymbolMode' in source
    assert '|allowed_timeframe_mode=" + allowedTimeframeMode' in source
    assert 'stopMode = input.string("Tighter"' in source
    assert 'targetMode = input.string("ATR capped R"' in source
    assert 'rewardRiskRatio = input.float(2.20' in source
    assert 'useTimeframeAdaptiveConfirmation = input.bool(true' in source
    assert 'maxTargetAtr = input.float(2.50' in source
    assert 'minNetRewardRisk = input.float(0.80' in source
    assert 'allowedSymbolMode = input.string("BTCUSDT only"' in source
    assert 'allowedTimeframeMode = input.string("15m/30m only"' in source


def test_volatility_breakout_contract_is_frozen_before_outcome_evaluation() -> None:
    source = Path("pine/strategies/volatility_breakout_v1.pine").read_text(
        encoding="utf-8"
    )

    assert 'strategyVersion = "1.1.0"' in source
    assert "commission_value = 0.05" in source
    assert "slippage = 2" in source
    assert 'input.time(timestamp("1 Feb 2023 00:00 +0000"), "Backtest start")' in source
    assert 'input.time(timestamp("1 Jul 2026 00:00 +0000"), "Backtest end")' in source
    assert 'input.float(0.3, "Risk per trade (%)"' in source
    assert 'input.float(95.0, "Max position value (%)"' in source
    assert "riskCapital / (longRisk * contractPointValue)" in source
    assert "riskCapital / (shortRisk * contractPointValue)" in source
    assert "qty = longQuantity" in source
    assert "qty = shortQuantity" in source
    assert "backtestExitBar" in source
    assert "settingsFingerprint() =>" in source
    assert "strategy_version" in source
    assert "settings_fingerprint" in source
    assert "|breakout_lookback=" in source
    assert "|volume_expansion=" in source
    assert "|risk_per_trade_percent=" in source


def test_volatility_breakout_strategy_setup_is_preregistration_ready() -> None:
    setup = backtest_strategy_setup(
        strategy="volatility_breakout_v1",
        symbol="btcusdt",
        timeframe="15m",
    )
    expected_fingerprint = strategy_parameter_fingerprint(
        "volatility_breakout_v1",
        VOLATILITY_BREAKOUT_V1_PARAMETER_TEMPLATE,
    )

    assert setup["strategy_version"] == "1.1.0"
    assert setup["parameters"] == VOLATILITY_BREAKOUT_V1_PARAMETER_TEMPLATE
    assert setup["settings_fingerprint"] == expected_fingerprint
    assert setup["required_parameters"] == list(
        VOLATILITY_BREAKOUT_V1_PARAMETER_TEMPLATE
    )
    assert setup["cost_model"] == {"commission_percent": "0.05"}
    assert setup["slippage_model"] == {"type": "fixed_ticks", "ticks": "2"}
    assert setup["risk_snapshot"] == {"risk_per_trade": "0.003"}
    assert setup["strategy_source_evidence"]["ready"] is True
    assert setup["strategy_source_evidence"]["pine_version"] == "1.1.0"


def test_slow_breakout_spot_contract_is_preregistration_ready() -> None:
    source = Path("pine/strategies/slow_breakout_spot_v1.pine").read_text(
        encoding="utf-8"
    )
    setup = backtest_strategy_setup(
        strategy="slow_breakout_spot_v1",
        symbol="ethusdt",
        timeframe="4h",
    )
    expected_fingerprint = strategy_parameter_fingerprint(
        "slow_breakout_spot_v1",
        SLOW_BREAKOUT_SPOT_V1_PARAMETER_TEMPLATE,
    )

    assert 'strategyVersion = "1.0.0"' in source
    assert "commission_value = 0.05" in source
    assert "slippage = 2" in source
    assert "timeframe.in_seconds() != 4 * 60 * 60" in source
    assert "ta.highest(high, entryChannelLength)[1]" in source
    assert "ta.lowest(low, exitChannelLength)[1]" in source
    assert '"\\"take_profit\\":null,"' in source
    assert "strategy.short" not in source
    assert "limit =" not in source
    assert setup["strategy_version"] == "1.0.0"
    assert setup["parameters"] == SLOW_BREAKOUT_SPOT_V1_PARAMETER_TEMPLATE
    assert setup["settings_fingerprint"] == expected_fingerprint
    assert setup["required_parameters"] == list(
        SLOW_BREAKOUT_SPOT_V1_PARAMETER_TEMPLATE
    )
    assert setup["cost_model"] == {"commission_percent": "0.05"}
    assert setup["slippage_model"] == {"type": "fixed_ticks", "ticks": "2"}
    assert setup["risk_snapshot"] == {"risk_per_trade": "0.0025"}
    assert setup["strategy_source_evidence"]["ready"] is True
    assert setup["strategy_source_evidence"]["pine_version"] == "1.0.0"
    assert REGISTERED_STRATEGIES["slow_breakout_spot_v1"].default_enabled is False


def test_slow_breakout_spot_fingerprint_matches_pine_ordered_contract() -> None:
    fingerprint = strategy_parameter_fingerprint(
        "slow_breakout_spot_v1",
        SLOW_BREAKOUT_SPOT_V1_PARAMETER_TEMPLATE,
    )

    assert fingerprint is not None
    assert fingerprint.startswith(
        "slow_breakout_spot_v1|initial_capital=1000"
        "|backtest_start=2023-02-01T00:00:00Z"
    )
    assert "|entry_channel_length=55|exit_channel_length=20" in fingerprint
    assert "|atr_length=20|atr_stop_multiplier=3" in fingerprint
    assert "|risk_per_trade_percent=0.25" in fingerprint
    assert fingerprint.endswith("|max_position_value_percent=50|enable_long=true")


def test_volatility_breakout_fingerprint_matches_pine_ordered_contract() -> None:
    fingerprint = strategy_parameter_fingerprint(
        "volatility_breakout_v1",
        VOLATILITY_BREAKOUT_V1_PARAMETER_TEMPLATE,
    )

    assert fingerprint is not None
    assert fingerprint.startswith(
        "volatility_breakout_v1|initial_capital=1000"
        "|backtest_start=2023-02-01T00:00:00Z"
    )
    assert "|htf_ema_fast=50|htf_ema_slow=200" in fingerprint
    assert "|breakout_lookback=20|compression_lookback=40" in fingerprint
    assert "|atr_stop_multiplier=1.8|reward_risk=2" in fingerprint
    assert "|volume_expansion=1.15" in fingerprint
    assert "|risk_per_trade_percent=0.3" in fingerprint
    assert fingerprint.endswith("|enable_long=true|enable_short=true")


def test_jam_reversal_strategy_setup_is_import_ready() -> None:
    setup = backtest_strategy_setup(
        strategy="jam_reversal_v1",
        symbol="btcusdt",
        timeframe="15m",
    )
    expected_fingerprint = strategy_parameter_fingerprint(
        "jam_reversal_v1",
        JAM_REVERSAL_V1_PARAMETER_TEMPLATE,
    )

    assert setup["strategy"] == "jam_reversal_v1"
    assert setup["strategy_version"] == "1.14.0"
    assert setup["pine_path"] == "pine/strategies/jam_reversal_v1.pine"
    assert setup["docs_path"] == "docs/pine/jam_reversal_v1.md"
    assert setup["parameters"] == JAM_REVERSAL_V1_PARAMETER_TEMPLATE
    assert setup["settings_fingerprint"] == expected_fingerprint
    assert setup["required_parameters"] == list(JAM_REVERSAL_V1_PARAMETER_TEMPLATE)
    assert setup["cost_model"] == {"commission_percent": "0.05"}
    assert setup["slippage_model"] == {"type": "fixed_ticks", "ticks": "2"}
    assert setup["risk_snapshot"] == {"risk_per_trade": "0.005"}
    assert setup["source_reference"] == (
        "tradingview://strategy-tester/BINANCE:BTCUSDT/15m"
    )
    assert setup["strategy_source_evidence"]["ready"] is True
    assert setup["strategy_source_evidence"]["pine_version"] == "1.14.0"
    assert len(str(setup["strategy_source_evidence"]["pine_source_sha256"])) == 64


def test_jam_reversal_spot_contract_is_preregistration_ready() -> None:
    source = Path("pine/strategies/jam_reversal_spot_v1.pine").read_text(
        encoding="utf-8"
    )
    setup = backtest_strategy_setup(
        strategy="jam_reversal_spot_v1",
        symbol="btcusdt",
        timeframe="15m",
    )
    expected_fingerprint = strategy_parameter_fingerprint(
        "jam_reversal_spot_v1",
        JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE,
    )

    assert 'strategyVersion = "1.0.1"' in source
    assert "Lineage: jam_reversal_v1 v1.14.0" in source
    assert "initial_capital = 100" in source
    assert "commission_value = 0.10" in source
    assert 'directionMode = input.string("Long only"' in source
    assert 'allowedTimeframeMode = input.string("15m only"' in source
    assert "enableShort = false" in source
    assert '\\"strategy\\":\\"jam_reversal_spot_v1\\"' in source
    assert setup["strategy_version"] == "1.0.1"
    assert setup["parameters"] == JAM_REVERSAL_SPOT_V1_PARAMETER_TEMPLATE
    assert setup["settings_fingerprint"] == expected_fingerprint
    assert setup["cost_model"] == {"commission_percent": "0.10"}
    assert setup["slippage_model"] == {"type": "fixed_ticks", "ticks": "2"}
    assert setup["risk_snapshot"] == {"risk_per_trade": "0.005"}
    assert setup["strategy_source_evidence"]["ready"] is True
    assert REGISTERED_STRATEGIES["jam_reversal_spot_v1"].default_enabled is False


def test_jam_reversal_fingerprint_matches_pine_ordered_contract() -> None:
    fingerprint = strategy_parameter_fingerprint(
        "jam_reversal_v1",
        JAM_REVERSAL_V1_PARAMETER_TEMPLATE,
    )

    assert fingerprint is not None
    assert fingerprint.startswith(
        "jam_reversal_v1|initial_capital=1000|backtest_start=2024-01-01T00:00:00Z"
    )
    assert "|higher_timeframe_valid=true" in fingerprint
    assert "|stop_mode=Tighter" in fingerprint
    assert "|target_mode=ATR capped R" in fingerprint
    assert "|reward_risk=2.2" in fingerprint
    assert "|max_target_atr=2.5" in fingerprint
    assert "|min_net_reward_risk=0.8" in fingerprint
    assert "|allowed_symbol_mode=BTCUSDT only" in fingerprint
    assert "|allowed_timeframe_mode=15m/30m only" in fingerprint
    assert "|use_timeframe_adaptive_confirmation=true" in fingerprint
