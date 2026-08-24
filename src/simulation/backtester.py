"""
Backtesting engine: replays historical data through the arbitrage + prediction system.
"""

import json
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from data.fetcher import fetch_all_pairs, build_exchange_books, get_snapshot_at_time, build_time_index
from simulation.exchange import ExchangeManager
from simulation.portfolio import Portfolio
from prediction.signals import PredictionEngine


class BacktestConfig:

    def __init__(self):
        self.initial_usd = 10000.0
        self.max_trade_pct = 0.05
        self.max_trade_usd = 500.0
        self.min_arb_profit_pct = 0.08
        self.prediction_trade_pct = 0.03
        self.prediction_min_confidence = 0.4
        self.enable_cross_exchange_arb = True
        self.enable_triangular_arb = True
        self.enable_prediction_trading = True
        self.rebalance_interval_bars = 12
        self.stop_loss_pct = 0.02
        self.take_profit_pct = 0.03
        self.arb_cooldown_bars = 3
        self.transfer_cost_pct = 0.001
        self.max_position_pct = 0.30


class BacktestEngine:

    def __init__(self, config=None):
        self.config = config or BacktestConfig()
        self.exchange_mgr = ExchangeManager()
        self.portfolio = Portfolio(self.config.initial_usd)
        self.prediction = PredictionEngine()
        self.results = []
        self.arb_opportunities_found = 0
        self.arb_trades_executed = 0
        self.prediction_trades_executed = 0
        self.cross_ex_arbs_found = 0
        self.tri_arbs_found = 0
        self._last_arb_bar = -100

    def run(self, start_date=None, end_date=None, interval_minutes=5):
        print("=" * 70)
        print("ARBITCOIN BACKTEST ENGINE")
        print("=" * 70)

        print("\n[1/4] Fetching historical market data...")
        all_pair_data = fetch_all_pairs(interval=interval_minutes, since_days=16)

        if not all_pair_data:
            print("ERROR: No data fetched. Aborting.")
            return None

        print(f"\n[2/4] Building exchange order books for {len(all_pair_data)} pairs...")
        exchange_books = build_exchange_books(all_pair_data)
        time_index = build_time_index(exchange_books)

        first_pair = list(all_pair_data.values())[0]
        data_start = first_pair["timestamp"].min()
        data_end = first_pair["timestamp"].max()

        if start_date is None:
            start_date = data_start + timedelta(days=1)
        if end_date is None:
            end_date = data_end

        print(f"  Data range: {data_start} to {data_end}")
        print(f"  Backtest range: {start_date} to {end_date}")

        timestamps = pd.date_range(start=start_date, end=end_date, freq=f"{interval_minutes}min")
        print(f"  Total bars: {len(timestamps)}")

        print(f"\n[3/4] Running simulation...")
        print(f"  Initial portfolio: ${self.config.initial_usd:,.2f}")
        print(f"  Strategy: {'Arb+Prediction' if self.config.enable_prediction_trading else 'Arb Only'}")
        print(f"  Cross-exchange arb: {self.config.enable_cross_exchange_arb}")
        print(f"  Triangular arb: {self.config.enable_triangular_arb}")
        print(f"  Prediction trading: {self.config.enable_prediction_trading}")

        bar_count = 0
        report_interval = max(1, len(timestamps) // 20)

        for ts in timestamps:
            snapshot = get_snapshot_at_time(exchange_books, ts, time_index)
            self.exchange_mgr.update_from_snapshot(snapshot)

            if self.config.enable_prediction_trading and bar_count % self.config.rebalance_interval_bars == 0:
                for pair_name, df in all_pair_data.items():
                    pair_df = df[df["timestamp"] <= ts].tail(500)
                    if len(pair_df) >= 60:
                        self.prediction.update(pair_name, pair_df)

            if self.config.enable_cross_exchange_arb and (bar_count - self._last_arb_bar) >= self.config.arb_cooldown_bars:
                if self._execute_cross_exchange_arbs(ts):
                    self._last_arb_bar = bar_count

            if self.config.enable_triangular_arb and (bar_count - self._last_arb_bar) >= self.config.arb_cooldown_bars:
                if self._execute_triangular_arbs(ts):
                    self._last_arb_bar = bar_count

            if self.config.enable_prediction_trading and bar_count % self.config.rebalance_interval_bars == 0:
                self._execute_prediction_trades(ts)

            prices = self.exchange_mgr.get_current_prices()
            value = self.portfolio.record_equity(ts, prices)

            bar_count += 1
            if bar_count % report_interval == 0:
                pct_done = bar_count / len(timestamps) * 100
                ret = self.portfolio.get_return_pct(prices)
                print(f"  [{pct_done:5.1f}%] {ts.strftime('%Y-%m-%d %H:%M')} | "
                      f"Portfolio: ${value:,.2f} | Return: {ret:+.2f}% | "
                      f"Trades: {self.portfolio.total_trades}")

        prices = self.exchange_mgr.get_current_prices()
        print(f"\n[4/4] Simulation complete.")

        return self._generate_report(prices)

    def _execute_cross_exchange_arbs(self, timestamp):
        arbs = self.exchange_mgr.find_cross_exchange_arbs()
        self.cross_ex_arbs_found += len(arbs)
        executed_any = False

        for arb in arbs[:2]:
            if arb["profit_pct"] < self.config.min_arb_profit_pct:
                continue

            self.arb_opportunities_found += 1
            quote_coin = arb["quote_coin"]
            base_coin = arb["base_coin"]
            pair = arb["pair"]

            available = self.portfolio.get_balance(quote_coin)
            trade_amount = min(
                available * self.config.max_trade_pct,
                self.config.max_trade_usd,
                available,
            )

            transfer_cost = trade_amount * self.config.transfer_cost_pct
            trade_amount -= transfer_cost

            if trade_amount < 5.0 and quote_coin == "USD":
                continue
            if trade_amount <= 0:
                continue

            buy_ex = self.exchange_mgr.exchanges[arb["buy_exchange"]]
            sell_ex = self.exchange_mgr.exchanges[arb["sell_exchange"]]

            buy_result = buy_ex.simulate_buy(pair, trade_amount)
            if not buy_result:
                continue

            sell_result = sell_ex.simulate_sell(pair, buy_result["coins"])
            if not sell_result:
                continue

            net_profit = sell_result["usd"] - trade_amount
            if net_profit <= 0:
                continue

            cycle_trades = [
                {
                    "from_coin": quote_coin,
                    "to_coin": base_coin,
                    "amount": trade_amount,
                    "rate": 1.0 / buy_result["price"],
                    "fee_rate": buy_ex.fee_rate,
                    "exchange": arb["buy_exchange"],
                },
                {
                    "from_coin": base_coin,
                    "to_coin": quote_coin,
                    "amount": buy_result["coins"],
                    "rate": sell_result["price"],
                    "fee_rate": sell_ex.fee_rate,
                    "exchange": arb["sell_exchange"],
                },
            ]

            self.portfolio.execute_cycle(cycle_trades, timestamp)
            self.arb_trades_executed += 1
            executed_any = True

        return executed_any

    def _execute_triangular_arbs(self, timestamp):
        executed_any = False
        for ex_name in ["kraken", "coinbase", "gemini"]:
            arbs = self.exchange_mgr.find_triangular_arbs(ex_name)
            self.tri_arbs_found += len(arbs)

            for arb in arbs[:1]:
                if arb["profit_pct"] < self.config.min_arb_profit_pct:
                    continue

                self.arb_opportunities_found += 1
                coins = arb["coins"]
                exchange = self.exchange_mgr.exchanges[ex_name]

                start_coin = coins[0]
                available = self.portfolio.get_balance(start_coin)
                if start_coin == "USD" or start_coin == "USDC":
                    trade_amount = min(
                        available * self.config.max_trade_pct,
                        self.config.max_trade_usd,
                        available,
                    )
                    if trade_amount < 5.0:
                        continue
                else:
                    continue

                cycle_trades = []
                current_amount = trade_amount
                valid = True

                for i in range(len(coins)):
                    from_c = coins[i]
                    to_c = coins[(i + 1) % len(coins)]
                    pair = f"{from_c}/{to_c}"
                    reverse_pair = f"{to_c}/{from_c}"

                    if pair in exchange.current_prices:
                        rate = exchange.current_prices[pair]["bid"] * (1 - exchange.fee_rate)
                    elif reverse_pair in exchange.current_prices:
                        rate = (1 / exchange.current_prices[reverse_pair]["ask"]) * (1 - exchange.fee_rate)
                    else:
                        valid = False
                        break

                    cycle_trades.append({
                        "from_coin": from_c,
                        "to_coin": to_c,
                        "amount": current_amount,
                        "rate": rate,
                        "fee_rate": exchange.fee_rate,
                        "exchange": ex_name,
                    })
                    current_amount = current_amount * rate

                if valid and current_amount > trade_amount:
                    self.portfolio.execute_cycle(cycle_trades, timestamp)
                    self.arb_trades_executed += 1
                    executed_any = True

        return executed_any

    def _execute_prediction_trades(self, timestamp):
        opportunities = self.prediction.get_top_opportunities(n=3)

        for signal in opportunities:
            if signal["confidence"] < self.config.prediction_min_confidence:
                continue

            pair = signal["pair"]
            parts = pair.split("/")
            if len(parts) != 2:
                continue
            base_coin, quote_coin = parts

            if signal["direction"] == "buy":
                available = self.portfolio.get_balance(quote_coin)
                prices = self.exchange_mgr.get_current_prices()
                total_val = self.portfolio.total_value_usd(prices)
                trade_amount = min(
                    available * self.config.prediction_trade_pct * signal["confidence"],
                    self.config.max_trade_usd,
                    total_val * self.config.max_position_pct,
                )

                if quote_coin == "USD" and trade_amount < 10.0:
                    continue
                if trade_amount <= 0:
                    continue

                best_ex = self._find_best_exchange(pair, "buy")
                if not best_ex:
                    continue

                exchange = self.exchange_mgr.exchanges[best_ex]
                ask = exchange.get_ask(pair)
                if not ask:
                    continue

                self.portfolio.execute_prediction_trade(
                    quote_coin, base_coin, trade_amount,
                    1.0 / ask, exchange.fee_rate, best_ex, timestamp
                )
                self.prediction_trades_executed += 1

            elif signal["direction"] == "sell":
                available = self.portfolio.get_balance(base_coin)
                trade_amount = available * self.config.prediction_trade_pct * signal["confidence"]

                if trade_amount <= 0:
                    continue

                best_ex = self._find_best_exchange(pair, "sell")
                if not best_ex:
                    continue

                exchange = self.exchange_mgr.exchanges[best_ex]
                bid = exchange.get_bid(pair)
                if not bid:
                    continue

                self.portfolio.execute_prediction_trade(
                    base_coin, quote_coin, trade_amount,
                    bid, exchange.fee_rate, best_ex, timestamp
                )
                self.prediction_trades_executed += 1

    def _find_best_exchange(self, pair, direction):
        best_ex = None
        best_price = None

        for ex_name, exchange in self.exchange_mgr.exchanges.items():
            if pair not in exchange.current_prices:
                continue

            if direction == "buy":
                price = exchange.current_prices[pair]["ask"] * (1 + exchange.fee_rate)
                if best_price is None or price < best_price:
                    best_price = price
                    best_ex = ex_name
            else:
                price = exchange.current_prices[pair]["bid"] * (1 - exchange.fee_rate)
                if best_price is None or price > best_price:
                    best_price = price
                    best_ex = ex_name

        return best_ex

    def _generate_report(self, prices):
        summary = self.portfolio.summary(prices)

        equity_df = pd.DataFrame(self.portfolio.equity_curve)
        if not equity_df.empty:
            equity_df["returns"] = equity_df["value"].pct_change()
            max_drawdown = self._calculate_max_drawdown(equity_df["value"])
            sharpe = self._calculate_sharpe(equity_df["returns"])
            sortino = self._calculate_sortino(equity_df["returns"])
        else:
            max_drawdown = 0
            sharpe = 0
            sortino = 0

        report = {
            "summary": summary,
            "metrics": {
                "max_drawdown_pct": max_drawdown * 100,
                "sharpe_ratio": sharpe,
                "sortino_ratio": sortino,
                "arb_opportunities_found": self.arb_opportunities_found,
                "arb_trades_executed": self.arb_trades_executed,
                "cross_exchange_arbs_found": self.cross_ex_arbs_found,
                "triangular_arbs_found": self.tri_arbs_found,
                "prediction_trades_executed": self.prediction_trades_executed,
            },
            "equity_curve": self.portfolio.equity_curve,
            "trade_log": self.portfolio.trade_log,
        }

        self._print_report(report)
        return report

    def _calculate_max_drawdown(self, equity_series):
        peak = equity_series.expanding(min_periods=1).max()
        drawdown = (equity_series - peak) / peak
        return abs(drawdown.min()) if len(drawdown) > 0 else 0

    def _calculate_sharpe(self, returns, risk_free_rate=0.0, periods_per_year=105120):
        if len(returns.dropna()) < 2:
            return 0
        excess = returns.dropna() - risk_free_rate / periods_per_year
        if excess.std() == 0:
            return 0
        return float(excess.mean() / excess.std() * np.sqrt(periods_per_year))

    def _calculate_sortino(self, returns, risk_free_rate=0.0, periods_per_year=105120):
        if len(returns.dropna()) < 2:
            return 0
        excess = returns.dropna() - risk_free_rate / periods_per_year
        downside = excess[excess < 0]
        if len(downside) == 0 or downside.std() == 0:
            return 0
        return float(excess.mean() / downside.std() * np.sqrt(periods_per_year))

    def _print_report(self, report):
        s = report["summary"]
        m = report["metrics"]

        print("\n" + "=" * 70)
        print("BACKTEST RESULTS")
        print("=" * 70)
        print(f"\n  Initial Portfolio:     ${s['initial_usd']:>12,.2f}")
        print(f"  Final Portfolio:       ${s['final_usd']:>12,.2f}")
        print(f"  Total Return:          {s['return_pct']:>+11.2f}%")
        print(f"  Max Drawdown:          {m['max_drawdown_pct']:>11.2f}%")
        print(f"  Sharpe Ratio:          {m['sharpe_ratio']:>11.4f}")
        print(f"  Sortino Ratio:         {m['sortino_ratio']:>11.4f}")
        print(f"\n  Total Trades:          {s['total_trades']:>8d}")
        print(f"  Winning Trades:        {s['winning_trades']:>8d}")
        print(f"  Losing Trades:         {s['losing_trades']:>8d}")
        print(f"  Win Rate:              {s['win_rate']:>10.1f}%")
        print(f"  Total Fees Paid:       ${s['total_fees_paid']:>12,.2f}")
        print(f"\n  Arb Opportunities:     {m['arb_opportunities_found']:>8d}")
        print(f"  Arb Trades Executed:   {m['arb_trades_executed']:>8d}")
        print(f"  Cross-Ex Arbs Found:   {m['cross_exchange_arbs_found']:>8d}")
        print(f"  Triangular Arbs Found: {m['triangular_arbs_found']:>8d}")
        print(f"  Prediction Trades:     {m['prediction_trades_executed']:>8d}")

        print(f"\n  Final Holdings:")
        for coin, amount in sorted(s["holdings"].items()):
            if abs(amount) > 0.0001:
                print(f"    {coin:>6s}: {amount:>14.6f}")

        print("=" * 70)
