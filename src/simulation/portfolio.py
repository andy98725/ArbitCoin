"""
Portfolio manager: tracks holdings, executes simulated trades, records P&L.
"""

import copy
from datetime import datetime


class Portfolio:

    def __init__(self, initial_usd=10000.0):
        self.holdings = {"USD": initial_usd}
        self.initial_usd = initial_usd
        self.trade_log = []
        self.equity_curve = []
        self.total_fees_paid = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self._open_positions = {}

    def get_balance(self, coin):
        return self.holdings.get(coin, 0.0)

    def set_balance(self, coin, amount):
        self.holdings[coin] = amount

    def execute_trade(self, from_coin, to_coin, amount, rate, fee_rate, exchange, timestamp, trade_type="arbitrage"):
        from_balance = self.get_balance(from_coin)
        if amount > from_balance:
            amount = from_balance

        if amount <= 0:
            return False

        fee = amount * fee_rate
        net_amount = amount - fee
        received = net_amount * rate

        self.holdings[from_coin] = from_balance - amount
        self.holdings[to_coin] = self.get_balance(to_coin) + received
        self.total_fees_paid += fee * self._get_usd_value(from_coin, rate)
        self.total_trades += 1

        self.trade_log.append({
            "timestamp": timestamp,
            "type": trade_type,
            "exchange": exchange,
            "from": from_coin,
            "to": to_coin,
            "amount": amount,
            "rate": rate,
            "fee": fee,
            "received": received,
        })

        return True

    def execute_cycle(self, cycle_trades, timestamp, prices=None):
        if prices is None:
            prices = {}
        initial_usd_equiv = self.total_value_usd(prices)
        for trade in cycle_trades:
            success = self.execute_trade(
                trade["from_coin"], trade["to_coin"],
                trade["amount"], trade["rate"],
                trade["fee_rate"], trade["exchange"],
                timestamp, trade_type="arbitrage_cycle"
            )
            if not success:
                return False
        final_usd_equiv = self.total_value_usd(prices)
        if final_usd_equiv > initial_usd_equiv:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        return True

    def execute_prediction_trade(self, from_coin, to_coin, amount, rate, fee_rate, exchange, timestamp):
        from_balance = self.get_balance(from_coin)
        if amount > from_balance:
            amount = from_balance
        if amount <= 0:
            return False

        fee = amount * fee_rate
        net_amount = amount - fee
        received = net_amount * rate

        is_buy_crypto = from_coin in ("USD", "USDC") and to_coin not in ("USD", "USDC")
        is_sell_crypto = from_coin not in ("USD", "USDC") and to_coin in ("USD", "USDC")

        if is_buy_crypto:
            if to_coin not in self._open_positions:
                self._open_positions[to_coin] = {"cost_basis": 0.0, "amount": 0.0}
            self._open_positions[to_coin]["cost_basis"] += amount
            self._open_positions[to_coin]["amount"] += received

        if is_sell_crypto and from_coin in self._open_positions:
            pos = self._open_positions[from_coin]
            if pos["amount"] > 0:
                sold_fraction = min(amount / pos["amount"], 1.0)
                cost_of_sold = pos["cost_basis"] * sold_fraction
                pnl = received - cost_of_sold
                if pnl > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
                pos["cost_basis"] *= (1 - sold_fraction)
                pos["amount"] = max(0, pos["amount"] - amount)
                if pos["amount"] < 0.00001:
                    del self._open_positions[from_coin]

        self.holdings[from_coin] = from_balance - amount
        self.holdings[to_coin] = self.get_balance(to_coin) + received
        self.total_fees_paid += fee * self._get_usd_value(from_coin, rate)
        self.total_trades += 1

        self.trade_log.append({
            "timestamp": timestamp,
            "type": "prediction",
            "exchange": exchange,
            "from": from_coin,
            "to": to_coin,
            "amount": amount,
            "rate": rate,
            "fee": fee,
            "received": received,
        })
        return True

    def _get_usd_value(self, coin, rate_hint):
        if coin == "USD" or coin == "USDC":
            return 1.0
        return rate_hint if rate_hint else 1.0

    def total_value_usd(self, prices):
        total = 0.0
        for coin, amount in self.holdings.items():
            if coin == "USD" or coin == "USDC":
                total += amount
            elif f"{coin}/USD" in prices:
                total += amount * prices[f"{coin}/USD"]
            elif coin == "BTC" and "BTC/USD" in prices:
                total += amount * prices["BTC/USD"]
            else:
                total += 0
        return total

    def record_equity(self, timestamp, prices):
        value = self.total_value_usd(prices)
        self.equity_curve.append({
            "timestamp": timestamp,
            "value": value,
            "holdings": copy.copy(self.holdings),
        })
        return value

    def get_return_pct(self, prices):
        current = self.total_value_usd(prices)
        return (current - self.initial_usd) / self.initial_usd * 100

    def summary(self, prices):
        current_value = self.total_value_usd(prices)
        return_pct = self.get_return_pct(prices)
        return {
            "initial_usd": self.initial_usd,
            "final_usd": current_value,
            "return_pct": return_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.winning_trades / max(1, self.winning_trades + self.losing_trades) * 100,
            "total_fees_paid": self.total_fees_paid,
            "holdings": dict(self.holdings),
        }
