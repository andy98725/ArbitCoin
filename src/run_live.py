#!/usr/bin/env python3
"""
ArbitCoin Live Trading Runner

Connects to exchange WebSocket feeds for real-time orderbook data,
detects arbitrage opportunities using Bellman-Ford, and executes
prediction-based trades using the V2 engine.

Modes:
  --paper     Paper trading (default) - logs trades, no real execution
  --live      Live trading - requires API keys in auth/ directory
  --monitor   Monitor only - detect opportunities but don't trade

Usage:
  python src/run_live.py [--paper|--live|--monitor] [--budget 10000]
"""

import sys
import os
import time
import signal
import argparse
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from graph.cycleGraph import TradingGraph
from traders import coinbase, kraken, gemini
import config


class LiveTrader:

    def __init__(self, mode="paper", budget=10000.0, max_trade_usd=500.0):
        self.mode = mode
        self.budget = budget
        self.max_trade_usd = max_trade_usd
        self.running = False

        self.portfolio = {"USD": budget}
        self.trade_log = []
        self.opportunities_found = 0
        self.trades_executed = 0
        self.total_pnl = 0.0
        self.start_time = None

        self.circuit_breaker_loss = budget * 0.05
        self.circuit_breaker_triggered = False
        self.max_trades_per_hour = 50
        self.hourly_trade_count = 0
        self.hourly_reset_time = None

        self.graph = TradingGraph(config.coins)
        self.frontends = []

    def start(self):
        self.running = True
        self.start_time = datetime.now()
        self.hourly_reset_time = self.start_time

        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        print("=" * 60)
        print(f"  ArbitCoin Live Trader")
        print(f"  Mode: {self.mode.upper()}")
        print(f"  Budget: ${self.budget:,.2f}")
        print(f"  Max Trade: ${self.max_trade_usd:,.2f}")
        print(f"  Circuit Breaker: ${self.circuit_breaker_loss:,.2f} loss")
        print(f"  Max Trades/Hour: {self.max_trades_per_hour}")
        print("=" * 60)

        self._connect_exchanges()

        print("\nExchanges connected. Monitoring for opportunities...")
        print("Press Ctrl+C to stop.\n")

        try:
            while self.running:
                self._check_opportunities()
                self._print_status()
                time.sleep(5)
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _connect_exchanges(self):
        print("\nConnecting to exchanges...")
        try:
            cb = coinbase.CoinbaseFrontend(config.coins, self.graph)
            self.frontends.append(("Coinbase", cb))
            print("  Coinbase: Connected")
        except Exception as e:
            print(f"  Coinbase: Failed - {e}")

        try:
            kr = kraken.KrakenFrontend(config.coins, self.graph)
            self.frontends.append(("Kraken", kr))
            print("  Kraken: Connected")
        except Exception as e:
            print(f"  Kraken: Failed - {e}")

        try:
            gm = gemini.GeminiFrontend(config.coins, self.graph)
            self.frontends.append(("Gemini", gm))
            print("  Gemini: Connected")
        except Exception as e:
            print(f"  Gemini: Failed - {e}")

        if not self.frontends:
            print("\nERROR: No exchanges connected. Exiting.")
            sys.exit(1)

    def _check_opportunities(self):
        if self.circuit_breaker_triggered:
            return

        now = datetime.now()
        if self.hourly_reset_time and (now - self.hourly_reset_time).total_seconds() > 3600:
            self.hourly_trade_count = 0
            self.hourly_reset_time = now

        cycle = self.graph.shortestProfitCycle()
        if cycle is None:
            return

        if cycle.profitPerc < config.thresholdPerc:
            return

        self.opportunities_found += 1

        trade_size = min(self.max_trade_usd, self.portfolio.get("USD", 0) * 0.1)
        if trade_size < 10:
            return

        if self.hourly_trade_count >= self.max_trades_per_hour:
            return

        estimated_profit = trade_size * (cycle.profitPerc / 100)

        if self.mode == "monitor":
            self._log_opportunity(cycle, estimated_profit)
            return

        if self.mode == "paper":
            self._paper_trade(cycle, trade_size, estimated_profit)
        elif self.mode == "live":
            self._live_trade(cycle, trade_size)

    def _paper_trade(self, cycle, trade_size, estimated_profit):
        self.trades_executed += 1
        self.hourly_trade_count += 1
        self.total_pnl += estimated_profit
        self.portfolio["USD"] = self.portfolio.get("USD", 0) + estimated_profit

        trade_record = {
            "timestamp": datetime.now().isoformat(),
            "type": "arbitrage_cycle",
            "cycle": str(cycle),
            "trade_size": trade_size,
            "estimated_profit": estimated_profit,
            "profit_pct": cycle.profitPerc,
            "portfolio_value": sum(self.portfolio.values()),
        }
        self.trade_log.append(trade_record)

        print(f"  [PAPER] Arb cycle: {cycle.profitPerc:.3f}% "
              f"profit ~${estimated_profit:.2f} "
              f"| Portfolio: ${self.portfolio.get('USD', 0):,.2f}")

        if self.total_pnl < -self.circuit_breaker_loss:
            self.circuit_breaker_triggered = True
            print(f"\n  CIRCUIT BREAKER: Loss exceeds ${self.circuit_breaker_loss:.2f}. "
                  f"Trading halted.")

    def _live_trade(self, cycle, trade_size):
        print(f"  [LIVE] Would execute cycle: {cycle.profitPerc:.3f}%")
        print(f"         Trade execution not yet implemented.")
        print(f"         Run with --paper for paper trading.")

    def _log_opportunity(self, cycle, estimated_profit):
        print(f"  [MONITOR] Opportunity: {cycle.profitPerc:.3f}% "
              f"est. profit ~${estimated_profit:.2f}")

    def _print_status(self):
        now = datetime.now()
        if not hasattr(self, '_last_status') or (now - self._last_status).total_seconds() > 60:
            self._last_status = now
            elapsed = (now - self.start_time).total_seconds() / 3600
            print(f"\n--- Status ({now.strftime('%H:%M:%S')}) ---")
            print(f"  Uptime: {elapsed:.1f}h | "
                  f"Opportunities: {self.opportunities_found} | "
                  f"Trades: {self.trades_executed} | "
                  f"P&L: ${self.total_pnl:+,.2f} | "
                  f"Portfolio: ${self.portfolio.get('USD', 0):,.2f}")
            if self.circuit_breaker_triggered:
                print("  STATUS: HALTED (circuit breaker)")
            print()

    def _handle_shutdown(self, signum, frame):
        print("\n\nShutdown signal received...")
        self.running = False

    def _shutdown(self):
        print("\n" + "=" * 60)
        print("  Session Summary")
        print("=" * 60)
        elapsed = (datetime.now() - self.start_time).total_seconds()
        hours = elapsed / 3600
        print(f"  Duration: {hours:.2f} hours")
        print(f"  Mode: {self.mode.upper()}")
        print(f"  Opportunities Found: {self.opportunities_found}")
        print(f"  Trades Executed: {self.trades_executed}")
        print(f"  Total P&L: ${self.total_pnl:+,.2f}")
        print(f"  Final Portfolio: ${self.portfolio.get('USD', 0):,.2f}")
        if self.circuit_breaker_triggered:
            print(f"  Circuit Breaker: TRIGGERED")
        print("=" * 60)

        if self.trade_log:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"live_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(log_file, "w") as f:
                json.dump({
                    "mode": self.mode,
                    "start_time": self.start_time.isoformat(),
                    "duration_hours": hours,
                    "initial_budget": self.budget,
                    "final_value": self.portfolio.get("USD", 0),
                    "total_pnl": self.total_pnl,
                    "trades": self.trade_log,
                }, f, indent=2)
            print(f"\n  Trade log saved to {log_file}")


def main():
    parser = argparse.ArgumentParser(description="ArbitCoin Live Trader")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--paper", action="store_true", default=True,
                           help="Paper trading mode (default)")
    mode_group.add_argument("--live", action="store_true",
                           help="Live trading mode (requires API keys)")
    mode_group.add_argument("--monitor", action="store_true",
                           help="Monitor only - detect but don't trade")
    parser.add_argument("--budget", type=float, default=10000.0,
                       help="Starting budget in USD (default: 10000)")
    parser.add_argument("--max-trade", type=float, default=500.0,
                       help="Maximum trade size in USD (default: 500)")

    args = parser.parse_args()

    if args.live:
        mode = "live"
    elif args.monitor:
        mode = "monitor"
    else:
        mode = "paper"

    trader = LiveTrader(
        mode=mode,
        budget=args.budget,
        max_trade_usd=args.max_trade,
    )
    trader.start()


if __name__ == "__main__":
    main()
