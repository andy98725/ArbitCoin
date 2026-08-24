"""
Load configuration from config.yaml with config.local.yaml overrides.
"""

import os
import yaml

CONFIG_DIR = os.path.dirname(os.path.dirname(__file__))


def _deep_merge(base, override):
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config():
    config_path = os.path.join(CONFIG_DIR, "config.yaml")
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    local_path = os.path.join(CONFIG_DIR, "config.local.yaml")
    if os.path.exists(local_path):
        with open(local_path, "r") as f:
            local = yaml.safe_load(f)
        if local:
            cfg = _deep_merge(cfg, local)

    return cfg


def apply_to_backtest_config(cfg, backtest_config):
    p = cfg.get("portfolio", {})
    backtest_config.initial_usd = p.get("initial_usd", 10000.0)
    backtest_config.target_cash_pct = p.get("target_cash_pct", 0.60)
    backtest_config.max_position_pct = p.get("max_position_pct", 0.25)

    arb = cfg.get("arbitrage", {})
    backtest_config.enable_cross_exchange_arb = arb.get("enable_cross_exchange", True)
    backtest_config.enable_triangular_arb = arb.get("enable_triangular", True)
    backtest_config.min_arb_profit_pct = arb.get("min_profit_pct", 0.06)
    backtest_config.max_trade_pct = arb.get("max_trade_pct", 0.05)
    backtest_config.max_trade_usd = arb.get("max_trade_usd", 500.0)
    backtest_config.arb_cooldown_bars = arb.get("cooldown_bars", 2)
    backtest_config.enable_dynamic_arb_threshold = arb.get("enable_dynamic_threshold", True)
    backtest_config.arb_success_lookback = arb.get("success_lookback", 50)

    pred = cfg.get("prediction", {})
    backtest_config.enable_prediction_trading = pred.get("enabled", True)
    backtest_config.prediction_trade_pct = pred.get("trade_pct", 0.08)
    backtest_config.prediction_min_confidence = pred.get("min_confidence", 0.40)
    backtest_config.prediction_score_threshold = pred.get("score_threshold", 1.5)

    risk = cfg.get("risk_management", {})
    backtest_config.enable_stop_loss = risk.get("enable_stop_loss", True)
    backtest_config.stop_loss_pct = risk.get("stop_loss_pct", 0.03)
    backtest_config.take_profit_pct = risk.get("take_profit_pct", 0.018)
    backtest_config.trailing_stop_pct = risk.get("trailing_stop_pct", 0.025)
    backtest_config.trailing_stop_activation = risk.get("trailing_stop_activation", 0.01)
    backtest_config.enable_adaptive_stops = risk.get("enable_adaptive_stops", True)
    backtest_config.atr_stop_multiplier = risk.get("atr_stop_multiplier", 1.5)

    pairs = cfg.get("pairs_trading", {})
    backtest_config.enable_pairs_trading = pairs.get("enabled", True)
    backtest_config.pairs_trade_pct = pairs.get("trade_pct", 0.04)
    backtest_config.pairs_max_hold_bars = pairs.get("max_hold_bars", 200)

    sig = cfg.get("signals", {})
    backtest_config.enable_multi_timeframe = sig.get("enable_multi_timeframe", True)
    backtest_config.mtf_confirmation_weight = sig.get("mtf_confirmation_weight", 0.3)
    backtest_config.enable_order_flow = sig.get("enable_order_flow", True)
    backtest_config.order_flow_weight = sig.get("order_flow_weight", 0.3)
    backtest_config.enable_regime_detection = sig.get("enable_regime_detection", True)
    backtest_config.enable_kelly_sizing = sig.get("enable_kelly_sizing", True)

    adv = cfg.get("advanced", {})
    backtest_config.rebalance_interval_bars = adv.get("rebalance_interval_bars", 18)
    backtest_config.enable_rebalancing = adv.get("enable_rebalancing", True)
    backtest_config.enable_time_of_day = adv.get("enable_time_of_day", True)
    backtest_config.enable_performance_tracker = adv.get("enable_performance_tracker", True)
    backtest_config.perf_window_bars = adv.get("perf_window_bars", 288)
    backtest_config.enable_smart_routing = adv.get("enable_smart_routing", True)
    backtest_config.enable_correlation_limits = adv.get("enable_correlation_limits", True)
    backtest_config.max_correlated_exposure_pct = adv.get("max_correlated_exposure_pct", 0.40)

    return backtest_config
