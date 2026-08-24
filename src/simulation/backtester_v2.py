"""
Enhanced backtesting engine v2: adds regime detection, Kelly sizing,
dynamic risk management, and improved prediction integration.
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
from prediction.regime import RegimeDetector


class BacktestConfigV2:

    def __init__(self):
        self.initial_usd = 10000.0
        self.max_trade_pct = 0.05
        self.max_trade_usd = 500.0
        self.min_arb_profit_pct = 0.08
        self.prediction_trade_pct = 0.05
        self.prediction_min_confidence = 0.35
        self.enable_cross_exchange_arb = True
        self.enable_triangular_arb = True
        self.enable_prediction_trading = True
        self.rebalance_interval_bars = 12
        self.arb_cooldown_bars = 3
        self.transfer_cost_pct = 0.001
        self.max_position_pct = 0.30
        self.enable_regime_detection = True
        self.enable_kelly_sizing = True
        self.enable_stop_loss = True
        self.stop_loss_pct = 0.03
        self.take_profit_pct = 0.018
        self.trailing_stop_pct = 0.025
        self.trailing_stop_activation = 0.01
        self.enable_pairs_trading = True
        self.pairs_zscore_entry = 2.0
        self.pairs_zscore_exit = 0.5
        self.pairs_trade_pct = 0.04
        self.pairs_max_hold_bars = 200
        self.enable_rebalancing = True
        self.target_cash_pct = 0.60
        self.rebalance_threshold = 0.10
        self.prediction_score_threshold = 2.0
        self.enable_multi_timeframe = True
        self.mtf_confirmation_weight = 0.3
        self.enable_adaptive_stops = True
        self.atr_stop_multiplier = 1.5
        self.enable_order_flow = True
        self.order_flow_weight = 0.3
        self.enable_dynamic_arb_threshold = True
        self.arb_success_lookback = 50


class BacktestEngineV2:

    def __init__(self, config=None):
        self.config = config or BacktestConfigV2()
        self.exchange_mgr = ExchangeManager()
        self.portfolio = Portfolio(self.config.initial_usd)
        self.prediction = PredictionEngine()
        self.regime = RegimeDetector()
        self.arb_opportunities_found = 0
        self.arb_trades_executed = 0
        self.prediction_trades_executed = 0
        self.cross_ex_arbs_found = 0
        self.tri_arbs_found = 0
        self.stop_losses_triggered = 0
        self.take_profits_triggered = 0
        self.rebalances_executed = 0
        self._last_arb_bar = -100
        self._entry_prices = {}
        self._high_water = {}
        self._pairs_positions = {}
        self._pairs_positions_age = {}
        self._pairs_trades_executed = 0
        self._regime_log = []
        self._mtf_cache = {}
        self._arb_results = []
        self._dynamic_stop_levels = {}

    def run(self, start_date=None, end_date=None, interval_minutes=5):
        print("=" * 70)
        print("ARBITCOIN BACKTEST ENGINE V2 (Enhanced)")
        print("=" * 70)

        print("\n[1/4] Fetching historical market data...")
        all_pair_data = fetch_all_pairs(interval=interval_minutes, since_days=16)

        if not all_pair_data:
            print("ERROR: No data fetched.")
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

        features = []
        if self.config.enable_cross_exchange_arb:
            features.append("CrossExArb")
        if self.config.enable_triangular_arb:
            features.append("TriArb")
        if self.config.enable_prediction_trading:
            features.append("Prediction")
        if self.config.enable_regime_detection:
            features.append("Regime")
        if self.config.enable_kelly_sizing:
            features.append("Kelly")
        if self.config.enable_stop_loss:
            features.append("StopLoss")
        if self.config.enable_rebalancing:
            features.append("Rebalance")
        if self.config.enable_pairs_trading:
            features.append("PairsTrading")

        print(f"\n[3/4] Running simulation...")
        print(f"  Initial portfolio: ${self.config.initial_usd:,.2f}")
        print(f"  Features: {', '.join(features)}")

        bar_count = 0
        report_interval = max(1, len(timestamps) // 20)

        for ts in timestamps:
            snapshot = get_snapshot_at_time(exchange_books, ts, time_index)
            self.exchange_mgr.update_from_snapshot(snapshot)

            do_prediction_update = (
                self.config.enable_prediction_trading
                and bar_count % self.config.rebalance_interval_bars == 0
            )

            if do_prediction_update:
                for pair_name, df in all_pair_data.items():
                    pair_df = df[df["timestamp"] <= ts].tail(500)
                    if len(pair_df) >= 60:
                        self.prediction.update(pair_name, pair_df)
                        if self.config.enable_regime_detection:
                            self.regime.detect(pair_name, pair_df)
                        if self.config.enable_multi_timeframe:
                            self._mtf_cache[pair_name] = self._compute_mtf_score(pair_name, df, ts)

            if self.config.enable_stop_loss:
                self._check_stop_losses(ts)

            if self.config.enable_cross_exchange_arb and (bar_count - self._last_arb_bar) >= self.config.arb_cooldown_bars:
                if self._execute_cross_exchange_arbs(ts):
                    self._last_arb_bar = bar_count

            if self.config.enable_triangular_arb and (bar_count - self._last_arb_bar) >= self.config.arb_cooldown_bars:
                if self._execute_triangular_arbs(ts):
                    self._last_arb_bar = bar_count

            if do_prediction_update and self.config.enable_prediction_trading:
                self._execute_prediction_trades(ts)

            if self.config.enable_pairs_trading and bar_count % self.config.rebalance_interval_bars == 0:
                self._execute_pairs_trades(ts, all_pair_data, bar_count, len(timestamps))

            if self.config.enable_rebalancing and bar_count % (self.config.rebalance_interval_bars * 4) == 0:
                self._rebalance_portfolio(ts)

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

    def _kelly_fraction(self, win_prob, win_loss_ratio):
        if win_loss_ratio <= 0 or win_prob <= 0:
            return 0
        kelly = win_prob - (1 - win_prob) / win_loss_ratio
        return max(0, min(kelly * 0.5, 0.25))

    def _check_stop_losses(self, timestamp):
        prices = self.exchange_mgr.get_current_prices()
        coins_to_sell = []

        for coin, entry_price in list(self._entry_prices.items()):
            pair = f"{coin}/USD"
            current_price = prices.get(pair)
            if current_price is None:
                continue

            if coin not in self._high_water or current_price > self._high_water[coin]:
                self._high_water[coin] = current_price

            pnl_pct = (current_price - entry_price) / entry_price
            trail_pct = (current_price - self._high_water[coin]) / self._high_water[coin]

            stop_pct = self.config.stop_loss_pct
            tp_pct = self.config.take_profit_pct
            if self.config.enable_adaptive_stops:
                atr_pct = self.prediction.get_atr_pct(pair)
                if atr_pct is not None and atr_pct > 0:
                    stop_pct = max(atr_pct * self.config.atr_stop_multiplier, self.config.stop_loss_pct * 0.5)
                    stop_pct = min(stop_pct, self.config.stop_loss_pct * 2.0)
                    tp_pct = max(atr_pct * 2.0, self.config.take_profit_pct * 0.8)
                    tp_pct = min(tp_pct, self.config.take_profit_pct * 2.5)

            if pnl_pct < -stop_pct:
                coins_to_sell.append((coin, pair, current_price, "stop_loss"))
            elif pnl_pct > self.config.trailing_stop_activation and trail_pct < -self.config.trailing_stop_pct:
                coins_to_sell.append((coin, pair, current_price, "trailing_stop"))
            elif pnl_pct > tp_pct:
                coins_to_sell.append((coin, pair, current_price, "take_profit"))

        for coin, pair, price, reason in coins_to_sell:
            amount = self.portfolio.get_balance(coin)
            if amount <= 0:
                continue

            best_ex = self._find_best_exchange(pair, "sell")
            if not best_ex:
                continue

            exchange = self.exchange_mgr.exchanges[best_ex]
            self.portfolio.execute_prediction_trade(
                coin, "USD", amount, price,
                exchange.fee_rate, best_ex, timestamp
            )
            if reason == "stop_loss":
                self.stop_losses_triggered += 1
            else:
                self.take_profits_triggered += 1
            del self._entry_prices[coin]
            self._high_water.pop(coin, None)

    def _get_dynamic_arb_threshold(self):
        if not self.config.enable_dynamic_arb_threshold or len(self._arb_results) < 10:
            return self.config.min_arb_profit_pct
        recent = self._arb_results[-self.config.arb_success_lookback:]
        win_rate = sum(1 for r in recent if r > 0) / len(recent)
        if win_rate > 0.9:
            return self.config.min_arb_profit_pct * 0.8
        elif win_rate < 0.7:
            return self.config.min_arb_profit_pct * 1.3
        return self.config.min_arb_profit_pct

    def _execute_cross_exchange_arbs(self, timestamp):
        arbs = self.exchange_mgr.find_cross_exchange_arbs()
        self.cross_ex_arbs_found += len(arbs)
        executed_any = False

        base_min_profit = self._get_dynamic_arb_threshold()

        for arb in arbs[:2]:
            min_profit = base_min_profit
            if self.config.enable_regime_detection:
                regime_info = self.regime.get_regime(arb["pair"])
                min_profit *= regime_info["params"]["arb_threshold_mult"]

            if arb["profit_pct"] < min_profit:
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

            if self.config.enable_kelly_sizing:
                kelly_f = self._kelly_fraction(0.85, arb["profit_pct"] / 0.1)
                trade_amount = min(trade_amount, available * kelly_f)

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
            self._arb_results.append(net_profit)

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
                min_profit = self.config.min_arb_profit_pct
                if arb["profit_pct"] < min_profit:
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
                    if self.config.enable_kelly_sizing:
                        kelly_f = self._kelly_fraction(0.80, arb["profit_pct"] / 0.15)
                        trade_amount = min(trade_amount, available * kelly_f)
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

    def _compute_mtf_score(self, pair_name, df, timestamp):
        if len(df) < 120:
            return 0.0

        mask = df["timestamp"] <= timestamp
        pair_df = df[mask].tail(500)
        if len(pair_df) < 120:
            return 0.0

        close = pair_df["close"].values
        returns_20 = (close[-1] - close[-20]) / close[-20] if len(close) >= 20 else 0
        returns_60 = (close[-1] - close[-60]) / close[-60] if len(close) >= 60 else 0
        returns_120 = (close[-1] - close[-120]) / close[-120] if len(close) >= 120 else 0

        score = 0.0
        if returns_20 > 0.01:
            score += 1.0
        elif returns_20 < -0.01:
            score -= 1.0

        if returns_60 > 0.02:
            score += 0.5
        elif returns_60 < -0.02:
            score -= 0.5

        if returns_120 > 0.03:
            score += 0.5
        elif returns_120 < -0.03:
            score -= 0.5

        log_close = np.log(close[-100:])
        roll_mean = np.mean(log_close)
        roll_std = np.std(log_close)
        if roll_std > 1e-8:
            zscore = (log_close[-1] - roll_mean) / roll_std
            if zscore < -1.5:
                score += 1.5
            elif zscore > 1.5:
                score -= 1.5

        return score

    def _execute_prediction_trades(self, timestamp):
        opportunities = self.prediction.get_top_opportunities(n=3)

        for signal in opportunities:
            if signal["confidence"] < self.config.prediction_min_confidence:
                continue
            if abs(signal["score"]) < self.config.prediction_score_threshold:
                continue

            pair = signal["pair"]
            parts = pair.split("/")
            if len(parts) != 2:
                continue
            base_coin, quote_coin = parts

            if quote_coin not in ("USD", "USDC"):
                continue

            regime_weight = 1.0
            if self.config.enable_regime_detection:
                regime_weight = self.regime.get_prediction_weight(pair)

            effective_confidence = signal["confidence"] * regime_weight

            if self.config.enable_multi_timeframe and pair in self._mtf_cache:
                mtf_score = self._mtf_cache[pair]
                if signal["direction"] == "buy" and mtf_score < -1.0:
                    effective_confidence *= 0.5
                elif signal["direction"] == "sell" and mtf_score > 1.0:
                    effective_confidence *= 0.5
                elif signal["direction"] == "buy" and mtf_score > 1.0:
                    effective_confidence *= 1.0 + self.config.mtf_confirmation_weight
                elif signal["direction"] == "sell" and mtf_score < -1.0:
                    effective_confidence *= 1.0 + self.config.mtf_confirmation_weight

            sig_momentum = self.prediction.get_signal_momentum(pair)
            if signal["direction"] == "buy" and sig_momentum > 0.5:
                effective_confidence *= 1.15
            elif signal["direction"] == "sell" and sig_momentum < -0.5:
                effective_confidence *= 1.15
            elif signal["direction"] == "buy" and sig_momentum < -1.0:
                effective_confidence *= 0.7
            elif signal["direction"] == "sell" and sig_momentum > 1.0:
                effective_confidence *= 0.7

            if self.config.enable_order_flow:
                of_signal = self.prediction.get_order_flow_signal(pair)
                if signal["direction"] == "buy" and of_signal > 0:
                    effective_confidence *= 1.0 + self.config.order_flow_weight
                elif signal["direction"] == "sell" and of_signal < 0:
                    effective_confidence *= 1.0 + self.config.order_flow_weight
                elif signal["direction"] == "buy" and of_signal < 0:
                    effective_confidence *= 0.8
                elif signal["direction"] == "sell" and of_signal > 0:
                    effective_confidence *= 0.8

            vol_scale = 1.0
            if self.config.enable_regime_detection:
                regime_info = self.regime.get_regime(pair)
                current_vol = regime_info.get("vol_20d", 0.5)
                if current_vol > 0.8:
                    vol_scale = 0.6
                elif current_vol < 0.3:
                    vol_scale = 1.3

            if signal["direction"] == "buy":
                available = self.portfolio.get_balance(quote_coin)
                prices = self.exchange_mgr.get_current_prices()
                total_val = self.portfolio.total_value_usd(prices)

                size_pct = self.config.prediction_trade_pct * effective_confidence * vol_scale
                if self.config.enable_kelly_sizing:
                    est_win_prob = 0.5 + signal["confidence"] * 0.2
                    est_win_loss = 1.0 + signal["confidence"]
                    kelly_f = self._kelly_fraction(est_win_prob, est_win_loss)
                    size_pct = min(size_pct, kelly_f * vol_scale)

                trade_amount = min(
                    available * size_pct,
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
                self._entry_prices[base_coin] = ask
                self.prediction_trades_executed += 1

            elif signal["direction"] == "sell":
                available = self.portfolio.get_balance(base_coin)
                size_pct = self.config.prediction_trade_pct * effective_confidence * vol_scale

                trade_amount = min(available * size_pct, available)
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
                if base_coin in self._entry_prices and available - trade_amount < 0.0001:
                    del self._entry_prices[base_coin]
                self.prediction_trades_executed += 1

    def _close_pairs_position(self, pair_key, timestamp, prices):
        if pair_key not in self._pairs_positions:
            return
        pos = self._pairs_positions[pair_key]
        pair_a, pair_b = pair_key.split("|")
        coin_a = pair_a.split("/")[0]
        coin_b = pair_b.split("/")[0]

        if pos["direction"] == "long_a":
            amt = self.portfolio.get_balance(coin_a)
            if amt > 0:
                price = prices.get(pair_a)
                if price:
                    best_ex = self._find_best_exchange(pair_a, "sell")
                    if best_ex:
                        ex = self.exchange_mgr.exchanges[best_ex]
                        self.portfolio.execute_prediction_trade(
                            coin_a, "USD", amt, price, ex.fee_rate, best_ex, timestamp
                        )
        else:
            amt = self.portfolio.get_balance(coin_b)
            if amt > 0:
                price = prices.get(pair_b)
                if price:
                    best_ex = self._find_best_exchange(pair_b, "sell")
                    if best_ex:
                        ex = self.exchange_mgr.exchanges[best_ex]
                        self.portfolio.execute_prediction_trade(
                            coin_b, "USD", amt, price, ex.fee_rate, best_ex, timestamp
                        )

        del self._pairs_positions[pair_key]
        self._pairs_positions_age.pop(pair_key, None)
        self._pairs_trades_executed += 1

    def _execute_pairs_trades(self, timestamp, all_pair_data, bar_count=0, total_bars=0):
        correlated_pairs = [
            ("BTC/USD", "ETH/USD"),
            ("BTC/USD", "LTC/USD"),
            ("ETH/USD", "LINK/USD"),
            ("BTC/USD", "BCH/USD"),
        ]

        prices = self.exchange_mgr.get_current_prices()
        total_val = self.portfolio.total_value_usd(prices)

        bars_remaining = total_bars - bar_count if total_bars > 0 else 9999
        if bars_remaining < 50:
            for pk in list(self._pairs_positions.keys()):
                self._close_pairs_position(pk, timestamp, prices)
            return

        for pair_key in list(self._pairs_positions_age.keys()):
            self._pairs_positions_age[pair_key] = self._pairs_positions_age.get(pair_key, 0) + self.config.rebalance_interval_bars
            if self._pairs_positions_age[pair_key] > self.config.pairs_max_hold_bars:
                self._close_pairs_position(pair_key, timestamp, prices)

        for pair_a, pair_b in correlated_pairs:
            if pair_a not in all_pair_data or pair_b not in all_pair_data:
                continue

            df_a = all_pair_data[pair_a]
            df_b = all_pair_data[pair_b]
            mask_a = df_a["timestamp"] <= timestamp
            mask_b = df_b["timestamp"] <= timestamp
            if mask_a.sum() < 100 or mask_b.sum() < 100:
                continue

            close_a = df_a.loc[mask_a, "close"].tail(100).values
            close_b = df_b.loc[mask_b, "close"].tail(100).values
            n = min(len(close_a), len(close_b))
            if n < 100:
                continue

            log_ratio = np.log(close_a[-n:] / close_b[-n:])
            mean_ratio = np.mean(log_ratio)
            std_ratio = np.std(log_ratio)
            if std_ratio < 1e-8:
                continue

            current_z = (log_ratio[-1] - mean_ratio) / std_ratio
            pair_key = f"{pair_a}|{pair_b}"

            if pair_key in self._pairs_positions:
                pos = self._pairs_positions[pair_key]
                if (pos["direction"] == "long_a" and current_z > -self.config.pairs_zscore_exit) or \
                   (pos["direction"] == "short_a" and current_z < self.config.pairs_zscore_exit):
                    self._close_pairs_position(pair_key, timestamp, prices)
                continue

            if abs(current_z) < self.config.pairs_zscore_entry:
                continue

            trade_amount = min(
                self.portfolio.get_balance("USD") * self.config.pairs_trade_pct,
                self.config.max_trade_usd,
                total_val * self.config.max_position_pct,
            )
            if trade_amount < 10.0:
                continue

            if current_z < -self.config.pairs_zscore_entry:
                coin_a = pair_a.split("/")[0]
                best_ex = self._find_best_exchange(pair_a, "buy")
                if best_ex:
                    ex = self.exchange_mgr.exchanges[best_ex]
                    ask = ex.get_ask(pair_a)
                    if ask:
                        self.portfolio.execute_prediction_trade(
                            "USD", coin_a, trade_amount, 1.0 / ask,
                            ex.fee_rate, best_ex, timestamp
                        )
                        self._entry_prices[coin_a] = ask
                        self._pairs_positions[pair_key] = {"direction": "long_a", "entry_z": current_z}
                        self._pairs_positions_age[pair_key] = 0
                        self._pairs_trades_executed += 1

            elif current_z > self.config.pairs_zscore_entry:
                coin_b = pair_b.split("/")[0]
                best_ex = self._find_best_exchange(pair_b, "buy")
                if best_ex:
                    ex = self.exchange_mgr.exchanges[best_ex]
                    ask = ex.get_ask(pair_b)
                    if ask:
                        self.portfolio.execute_prediction_trade(
                            "USD", coin_b, trade_amount, 1.0 / ask,
                            ex.fee_rate, best_ex, timestamp
                        )
                        self._entry_prices[coin_b] = ask
                        self._pairs_positions[pair_key] = {"direction": "short_a", "entry_z": current_z}
                        self._pairs_positions_age[pair_key] = 0
                        self._pairs_trades_executed += 1

    def _rebalance_portfolio(self, timestamp):
        prices = self.exchange_mgr.get_current_prices()
        total_val = self.portfolio.total_value_usd(prices)
        if total_val <= 0:
            return

        usd_balance = self.portfolio.get_balance("USD") + self.portfolio.get_balance("USDC")
        cash_pct = usd_balance / total_val

        if abs(cash_pct - self.config.target_cash_pct) < self.config.rebalance_threshold:
            return

        if cash_pct < self.config.target_cash_pct:
            for coin in list(self.portfolio.holdings.keys()):
                if coin in ("USD", "USDC"):
                    continue
                pair = f"{coin}/USD"
                best_ex = self._find_best_exchange(pair, "sell")
                if not best_ex:
                    continue

                exchange = self.exchange_mgr.exchanges[best_ex]
                bid = exchange.get_bid(pair)
                if not bid:
                    continue

                amount = self.portfolio.get_balance(coin)
                sell_pct = min(0.3, (self.config.target_cash_pct - cash_pct))
                sell_amount = amount * sell_pct

                if sell_amount * bid < 5.0:
                    continue

                self.portfolio.execute_trade(
                    coin, "USD", sell_amount, bid,
                    exchange.fee_rate, best_ex, timestamp, "rebalance"
                )
                self.rebalances_executed += 1

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
            calmar = abs(summary["return_pct"] / (max_drawdown * 100)) if max_drawdown > 0 else 0
        else:
            max_drawdown = sharpe = sortino = calmar = 0

        report = {
            "summary": summary,
            "metrics": {
                "max_drawdown_pct": max_drawdown * 100,
                "sharpe_ratio": sharpe,
                "sortino_ratio": sortino,
                "calmar_ratio": calmar,
                "arb_opportunities_found": self.arb_opportunities_found,
                "arb_trades_executed": self.arb_trades_executed,
                "cross_exchange_arbs_found": self.cross_ex_arbs_found,
                "triangular_arbs_found": self.tri_arbs_found,
                "prediction_trades_executed": self.prediction_trades_executed,
                "stop_losses_triggered": self.stop_losses_triggered,
                "take_profits_triggered": self.take_profits_triggered,
                "pairs_trades_executed": self._pairs_trades_executed,
                "rebalances_executed": self.rebalances_executed,
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
        print("BACKTEST RESULTS (V2 Enhanced)")
        print("=" * 70)
        print(f"\n  Initial Portfolio:     ${s['initial_usd']:>12,.2f}")
        print(f"  Final Portfolio:       ${s['final_usd']:>12,.2f}")
        print(f"  Total Return:          {s['return_pct']:>+11.2f}%")
        print(f"  Max Drawdown:          {m['max_drawdown_pct']:>11.2f}%")
        print(f"  Sharpe Ratio:          {m['sharpe_ratio']:>11.4f}")
        print(f"  Sortino Ratio:         {m['sortino_ratio']:>11.4f}")
        print(f"  Calmar Ratio:          {m['calmar_ratio']:>11.4f}")
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
        print(f"  Stop Losses Hit:       {m['stop_losses_triggered']:>8d}")
        print(f"  Take Profits Hit:      {m['take_profits_triggered']:>8d}")
        print(f"  Pairs Trades:          {m['pairs_trades_executed']:>8d}")
        print(f"  Rebalances:            {m['rebalances_executed']:>8d}")

        print(f"\n  Final Holdings:")
        for coin, amount in sorted(s["holdings"].items()):
            if abs(amount) > 0.0001:
                print(f"    {coin:>6s}: {amount:>14.6f}")

        print("=" * 70)
