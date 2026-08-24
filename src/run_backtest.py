#!/usr/bin/env python3
"""
ArbitCoin Backtest Runner
Runs a retroactive simulation over 2 weeks of market data.
Compares baseline (arb only) vs enhanced (arb + prediction + regime + risk mgmt).
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

from simulation.backtester import BacktestEngine, BacktestConfig
from simulation.backtester_v2 import BacktestEngineV2, BacktestConfigV2


def run_baseline():
    print("\n" + "#" * 70)
    print("# BASELINE STRATEGY: Arbitrage Only (No Prediction)")
    print("#" * 70)

    config = BacktestConfig()
    config.initial_usd = 10000.0
    config.enable_cross_exchange_arb = True
    config.enable_triangular_arb = True
    config.enable_prediction_trading = False
    config.min_arb_profit_pct = 0.08
    config.max_trade_pct = 0.05
    config.max_trade_usd = 500.0
    config.arb_cooldown_bars = 3

    engine = BacktestEngine(config)
    return engine.run()


def run_enhanced():
    print("\n" + "#" * 70)
    print("# ENHANCED STRATEGY V2: Arb + Prediction + Regime + Risk Mgmt")
    print("#" * 70)

    config = BacktestConfigV2()
    config.initial_usd = 10000.0
    config.enable_cross_exchange_arb = True
    config.enable_triangular_arb = True
    config.enable_prediction_trading = True
    config.min_arb_profit_pct = 0.06
    config.max_trade_pct = 0.05
    config.max_trade_usd = 500.0
    config.prediction_trade_pct = 0.08
    config.prediction_min_confidence = 0.40
    config.prediction_score_threshold = 1.5
    config.rebalance_interval_bars = 24
    config.arb_cooldown_bars = 3
    config.max_position_pct = 0.25
    config.enable_regime_detection = True
    config.enable_kelly_sizing = True
    config.enable_stop_loss = True
    config.stop_loss_pct = 0.03
    config.enable_rebalancing = True
    config.target_cash_pct = 0.60

    engine = BacktestEngineV2(config)
    return engine.run()


def compare_results(baseline, enhanced):
    print("\n" + "=" * 70)
    print("STRATEGY COMPARISON: Baseline (V1) vs Enhanced (V2)")
    print("=" * 70)

    b = baseline["summary"]
    e = enhanced["summary"]
    bm = baseline["metrics"]
    em = enhanced["metrics"]

    rows = [
        ("Initial Portfolio", f"${b['initial_usd']:,.2f}", f"${e['initial_usd']:,.2f}"),
        ("Final Portfolio", f"${b['final_usd']:,.2f}", f"${e['final_usd']:,.2f}"),
        ("Total Return", f"{b['return_pct']:+.2f}%", f"{e['return_pct']:+.2f}%"),
        ("Max Drawdown", f"{bm['max_drawdown_pct']:.2f}%", f"{em['max_drawdown_pct']:.2f}%"),
        ("Sharpe Ratio", f"{bm['sharpe_ratio']:.4f}", f"{em['sharpe_ratio']:.4f}"),
        ("Sortino Ratio", f"{bm['sortino_ratio']:.4f}", f"{em['sortino_ratio']:.4f}"),
        ("Calmar Ratio", "N/A", f"{em.get('calmar_ratio', 0):.4f}"),
        ("Total Trades", str(b['total_trades']), str(e['total_trades'])),
        ("Win Rate", f"{b['win_rate']:.1f}%", f"{e['win_rate']:.1f}%"),
        ("Total Fees", f"${b['total_fees_paid']:,.2f}", f"${e['total_fees_paid']:,.2f}"),
        ("Arb Trades", str(bm['arb_trades_executed']), str(em['arb_trades_executed'])),
        ("Prediction Trades", str(bm['prediction_trades_executed']), str(em['prediction_trades_executed'])),
        ("Stop Losses", "N/A", str(em.get('stop_losses_triggered', 0))),
        ("Take Profits", "N/A", str(em.get('take_profits_triggered', 0))),
        ("Rebalances", "N/A", str(em.get('rebalances_executed', 0))),
    ]

    print(f"\n  {'Metric':<22s} {'Baseline V1':>16s} {'Enhanced V2':>16s} {'Delta':>12s}")
    print(f"  {'-'*22} {'-'*16} {'-'*16} {'-'*12}")

    for label, bval, eval_ in rows:
        try:
            bn = float(bval.replace("$", "").replace(",", "").replace("%", "").replace("+", ""))
            en = float(eval_.replace("$", "").replace(",", "").replace("%", "").replace("+", ""))
            delta = en - bn
            if "%" in bval:
                delta_str = f"{delta:+.2f}%"
            elif "$" in bval:
                delta_str = f"${delta:+,.2f}"
            else:
                delta_str = f"{delta:+.4f}" if "." in bval else f"{delta:+.0f}"
        except (ValueError, TypeError):
            delta_str = "N/A"

        print(f"  {label:<22s} {bval:>16s} {eval_:>16s} {delta_str:>12s}")

    print("=" * 70)


def save_results(baseline, enhanced, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    for name, report in [("baseline", baseline), ("enhanced_v2", enhanced)]:
        summary_file = os.path.join(output_dir, f"{name}_summary.json")
        summary = {
            "summary": report["summary"],
            "metrics": report["metrics"],
        }
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        trades_file = os.path.join(output_dir, f"{name}_trades.json")
        with open(trades_file, "w") as f:
            json.dump(report["trade_log"], f, indent=2, default=str)

        equity_file = os.path.join(output_dir, f"{name}_equity.json")
        equity_data = [{"timestamp": str(e["timestamp"]), "value": e["value"]} for e in report["equity_curve"]]
        with open(equity_file, "w") as f:
            json.dump(equity_data, f, default=str)

    print(f"\nResults saved to {output_dir}/")


if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")

    baseline = run_baseline()
    enhanced = run_enhanced()

    if baseline and enhanced:
        compare_results(baseline, enhanced)
        save_results(baseline, enhanced, output_dir)
    else:
        print("ERROR: One or both simulations failed.")
