"""
Simulated exchange: replays historical data and provides order book snapshots.
Handles realistic slippage, partial fills, and fee calculation.
"""

import numpy as np


class SimulatedExchange:

    def __init__(self, name, fee_rate, base_spread):
        self.name = name
        self.fee_rate = fee_rate
        self.base_spread = base_spread
        self.current_prices = {}

    def update_prices(self, pair, bid, ask, volume, close):
        self.current_prices[pair] = {
            "bid": bid,
            "ask": ask,
            "volume": volume,
            "close": close,
            "mid": (bid + ask) / 2,
        }

    def get_bid(self, pair):
        if pair not in self.current_prices:
            return None
        return self.current_prices[pair]["bid"]

    def get_ask(self, pair):
        if pair not in self.current_prices:
            return None
        return self.current_prices[pair]["ask"]

    def get_mid(self, pair):
        if pair not in self.current_prices:
            return None
        return self.current_prices[pair]["mid"]

    def simulate_buy(self, pair, usd_amount):
        if pair not in self.current_prices:
            return None
        ask = self.current_prices[pair]["ask"]
        volume = self.current_prices[pair]["volume"]

        slippage = self._calculate_slippage(usd_amount, ask * volume)
        effective_price = ask * (1 + slippage)

        fee = usd_amount * self.fee_rate
        net_usd = usd_amount - fee
        coins_received = net_usd / effective_price

        return {
            "price": effective_price,
            "coins": coins_received,
            "fee": fee,
            "slippage": slippage,
        }

    def simulate_sell(self, pair, coin_amount):
        if pair not in self.current_prices:
            return None
        bid = self.current_prices[pair]["bid"]
        volume = self.current_prices[pair]["volume"]

        slippage = self._calculate_slippage(coin_amount * bid, bid * volume)
        effective_price = bid * (1 - slippage)

        gross_usd = coin_amount * effective_price
        fee = gross_usd * self.fee_rate
        net_usd = gross_usd - fee

        return {
            "price": effective_price,
            "usd": net_usd,
            "fee": fee,
            "slippage": slippage,
        }

    def get_effective_rate(self, from_coin, to_coin, pair, direction="buy"):
        if pair not in self.current_prices:
            return None

        if direction == "buy":
            ask = self.current_prices[pair]["ask"]
            return (1 / ask) * (1 - self.fee_rate)
        else:
            bid = self.current_prices[pair]["bid"]
            return bid * (1 - self.fee_rate)

    def _calculate_slippage(self, trade_value, market_volume_value):
        if market_volume_value <= 0:
            return 0.01
        impact_ratio = trade_value / max(market_volume_value, 1)
        return min(impact_ratio * 0.1, 0.02)


class ExchangeManager:

    def __init__(self):
        self.exchanges = {
            "kraken": SimulatedExchange("kraken", 0.0026, 0.0002),
            "coinbase": SimulatedExchange("coinbase", 0.005, 0.0003),
            "gemini": SimulatedExchange("gemini", 0.0035, 0.00025),
        }

    def update_from_snapshot(self, snapshot):
        for ex_name, pairs in snapshot.items():
            if ex_name not in self.exchanges:
                continue
            for pair_name, data in pairs.items():
                self.exchanges[ex_name].update_prices(
                    pair_name, data["bid"], data["ask"],
                    data["volume"], data["close"]
                )

    def get_all_rates(self):
        rates = {}
        for ex_name, exchange in self.exchanges.items():
            rates[ex_name] = {}
            for pair, data in exchange.current_prices.items():
                rates[ex_name][pair] = {
                    "bid": data["bid"],
                    "ask": data["ask"],
                    "mid": data["mid"],
                    "fee": exchange.fee_rate,
                }
        return rates

    def get_current_prices(self):
        prices = {}
        for ex_name, exchange in self.exchanges.items():
            for pair, data in exchange.current_prices.items():
                if pair not in prices:
                    prices[pair] = data["mid"]
        return prices

    def find_cross_exchange_arbs(self):
        arbs = []
        pairs_by_exchange = {}

        for ex_name, exchange in self.exchanges.items():
            for pair in exchange.current_prices:
                if pair not in pairs_by_exchange:
                    pairs_by_exchange[pair] = {}
                pairs_by_exchange[pair][ex_name] = exchange

        for pair, exchanges in pairs_by_exchange.items():
            ex_list = list(exchanges.items())
            for i in range(len(ex_list)):
                for j in range(len(ex_list)):
                    if i == j:
                        continue
                    buy_ex_name, buy_ex = ex_list[i]
                    sell_ex_name, sell_ex = ex_list[j]

                    buy_ask = buy_ex.current_prices[pair]["ask"]
                    sell_bid = sell_ex.current_prices[pair]["bid"]

                    buy_fee = buy_ex.fee_rate
                    sell_fee = sell_ex.fee_rate

                    effective_buy = buy_ask * (1 + buy_fee)
                    effective_sell = sell_bid * (1 - sell_fee)

                    profit_pct = (effective_sell / effective_buy - 1) * 100

                    if profit_pct > 0.01:
                        coins = pair.split("/")
                        arbs.append({
                            "pair": pair,
                            "buy_exchange": buy_ex_name,
                            "sell_exchange": sell_ex_name,
                            "buy_price": buy_ask,
                            "sell_price": sell_bid,
                            "profit_pct": profit_pct,
                            "base_coin": coins[0],
                            "quote_coin": coins[1] if len(coins) > 1 else "USD",
                        })

        arbs.sort(key=lambda x: x["profit_pct"], reverse=True)
        return arbs

    def find_triangular_arbs(self, exchange_name="kraken"):
        exchange = self.exchanges.get(exchange_name)
        if not exchange:
            return []

        arbs = []
        pairs = list(exchange.current_prices.keys())

        coins = set()
        for p in pairs:
            parts = p.split("/")
            coins.update(parts)

        pair_rates = {}
        for pair, data in exchange.current_prices.items():
            c1, c2 = pair.split("/")
            pair_rates[(c1, c2)] = {"bid": data["bid"], "ask": data["ask"]}
            pair_rates[(c2, c1)] = {"bid": 1 / data["ask"], "ask": 1 / data["bid"]}

        coin_list = list(coins)
        fee = exchange.fee_rate

        for a in coin_list:
            for b in coin_list:
                if b == a:
                    continue
                if (a, b) not in pair_rates:
                    continue
                for c in coin_list:
                    if c == a or c == b:
                        continue
                    if (b, c) not in pair_rates and (c, b) not in pair_rates:
                        continue
                    if (c, a) not in pair_rates and (a, c) not in pair_rates:
                        continue

                    rate_ab = pair_rates.get((a, b), {}).get("bid", 0)
                    rate_bc = pair_rates.get((b, c), {}).get("bid", 0)
                    rate_ca = pair_rates.get((c, a), {}).get("bid", 0)

                    if rate_ab and rate_bc and rate_ca:
                        product = rate_ab * rate_bc * rate_ca
                        net = product * (1 - fee) ** 3
                        profit_pct = (net - 1) * 100

                        if profit_pct > 0.01:
                            arbs.append({
                                "path": f"{a}->{b}->{c}->{a}",
                                "exchange": exchange_name,
                                "product": product,
                                "net_after_fees": net,
                                "profit_pct": profit_pct,
                                "coins": [a, b, c],
                            })

        arbs.sort(key=lambda x: x["profit_pct"], reverse=True)
        seen = set()
        unique_arbs = []
        for a in arbs:
            key = tuple(sorted(a["coins"]))
            if key not in seen:
                seen.add(key)
                unique_arbs.append(a)

        return unique_arbs
