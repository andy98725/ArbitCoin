"""
Fetch historical OHLCV data from exchange APIs, falling back to realistic
synthetic generation when APIs are unavailable (e.g. proxy-restricted environments).
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data_cache")
USE_REAL_DATA = os.environ.get("ARBITCOIN_REAL_DATA", "0") == "1"


def _check_cache(cache_file, max_age_hours=1):
    """Check if a cached CSV exists and is fresh enough."""
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file, parse_dates=["timestamp"])
        if (datetime.utcnow() - df["timestamp"].max()) < timedelta(hours=max_age_hours):
            return df
    return None


def _save_cache(df, cache_file):
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(cache_file, index=False)


def _try_fetch_kraken(pair_name, interval_minutes=5, since_days=15):
    """Fetch OHLCV from Kraken's public API."""
    import requests
    kraken_map = {
        "BTC/USD": "XXBTZUSD", "ETH/USD": "XETHZUSD", "LTC/USD": "XLTCZUSD",
        "LINK/USD": "LINKUSD", "BCH/USD": "BCHUSD", "ZEC/USD": "XZECZUSD",
        "XLM/USD": "XXLMZUSD", "AAVE/USD": "AAVEUSD", "ETH/BTC": "XETHXXBT",
        "LTC/BTC": "XLTCXXBT", "LINK/BTC": "LINKXBT", "XLM/BTC": "XXLMXXBT",
        "AAVE/ETH": "AAVEETH", "LINK/ETH": "LINKETH", "USDC/USD": "USDCUSD",
    }
    sym = kraken_map.get(pair_name)
    if not sym:
        return None
    try:
        cache_file = os.path.join(DATA_DIR, f"kraken_{pair_name.replace('/', '_')}_{interval_minutes}m.csv")
        cached = _check_cache(cache_file)
        if cached is not None:
            return cached

        since = int((datetime.utcnow() - timedelta(days=since_days)).timestamp())
        url = f"https://api.kraken.com/0/public/OHLC?pair={sym}&interval={interval_minutes}&since={since}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error") and len(data["error"]) > 0:
            return None
        result_key = [k for k in data["result"].keys() if k != "last"][0]
        rows = data["result"][result_key]
        df = pd.DataFrame(rows, columns=[
            "timestamp", "open", "high", "low", "close", "vwap", "volume", "count"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        for col in ["open", "high", "low", "close", "vwap", "volume"]:
            df[col] = df[col].astype(float)
        df["count"] = df["count"].astype(int)
        df["pair"] = pair_name
        _save_cache(df, cache_file)
        return df
    except Exception:
        return None


def _try_fetch_coinbase(pair_name, interval_minutes=5, since_days=15):
    """Fetch OHLCV from Coinbase's public API."""
    import requests
    coinbase_map = {
        "BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "LTC/USD": "LTC-USD",
        "LINK/USD": "LINK-USD", "BCH/USD": "BCH-USD", "ZEC/USD": "ZEC-USD",
        "XLM/USD": "XLM-USD", "AAVE/USD": "AAVE-USD", "ETH/BTC": "ETH-BTC",
        "LTC/BTC": "LTC-BTC", "LINK/BTC": "LINK-BTC", "XLM/BTC": "XLM-BTC",
        "AAVE/ETH": "AAVE-ETH", "LINK/ETH": "LINK-ETH", "USDC/USD": "USDC-USD",
    }
    sym = coinbase_map.get(pair_name)
    if not sym:
        return None

    granularity_map = {1: 60, 5: 300, 15: 900, 60: 3600, 360: 21600, 1440: 86400}
    granularity = granularity_map.get(interval_minutes, 300)

    try:
        cache_file = os.path.join(DATA_DIR, f"coinbase_{pair_name.replace('/', '_')}_{interval_minutes}m.csv")
        cached = _check_cache(cache_file)
        if cached is not None:
            return cached

        all_rows = []
        end = datetime.utcnow()
        start = end - timedelta(days=since_days)
        chunk_size = timedelta(hours=4) if interval_minutes <= 5 else timedelta(days=1)
        current = start

        while current < end:
            chunk_end = min(current + chunk_size, end)
            url = (f"https://api.exchange.coinbase.com/products/{sym}/candles"
                   f"?start={current.isoformat()}Z&end={chunk_end.isoformat()}Z"
                   f"&granularity={granularity}")
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                rows = resp.json()
                all_rows.extend(rows)
            current = chunk_end
            import time as _t
            _t.sleep(0.35)

        if not all_rows:
            return None

        df = pd.DataFrame(all_rows, columns=["timestamp", "low", "high", "open", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["vwap"] = (df["high"] + df["low"] + df["close"]) / 3
        df["count"] = 0
        df["pair"] = pair_name
        df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
        _save_cache(df, cache_file)
        return df
    except Exception:
        return None


def _try_fetch_gemini(pair_name, interval_minutes=5, since_days=15):
    """Fetch OHLCV from Gemini's public API."""
    import requests
    gemini_map = {
        "BTC/USD": "btcusd", "ETH/USD": "ethusd", "LTC/USD": "ltcusd",
        "LINK/USD": "linkusd", "BCH/USD": "bchusd", "ZEC/USD": "zecusd",
        "XLM/USD": "xlmusd", "AAVE/USD": "aaveusd", "ETH/BTC": "ethbtc",
        "LTC/BTC": "ltcbtc", "LINK/BTC": "linkbtc", "USDC/USD": "usdcusd",
    }
    sym = gemini_map.get(pair_name)
    if not sym:
        return None

    tf_map = {1: "1m", 5: "5m", 15: "15m", 30: "30m", 60: "1hr", 360: "6hr", 1440: "1day"}
    tf = tf_map.get(interval_minutes, "5m")

    try:
        cache_file = os.path.join(DATA_DIR, f"gemini_{pair_name.replace('/', '_')}_{interval_minutes}m.csv")
        cached = _check_cache(cache_file)
        if cached is not None:
            return cached

        url = f"https://api.gemini.com/v2/candles/{sym}/{tf}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        rows = resp.json()

        if not rows or not isinstance(rows, list):
            return None

        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["vwap"] = (df["high"] + df["low"] + df["close"]) / 3
        df["count"] = 0
        df["pair"] = pair_name
        df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
        cutoff = datetime.utcnow() - timedelta(days=since_days)
        df = df[df["timestamp"] >= cutoff].reset_index(drop=True)
        _save_cache(df, cache_file)
        return df
    except Exception:
        return None


EXCHANGE_FETCHERS = {
    "kraken": _try_fetch_kraken,
    "coinbase": _try_fetch_coinbase,
    "gemini": _try_fetch_gemini,
}


def _try_fetch_real_ohlcv(pair_name, interval_minutes=5, since_days=15):
    """Try all exchange APIs in order, return the first successful result."""
    for name, fetcher in EXCHANGE_FETCHERS.items():
        df = fetcher(pair_name, interval_minutes, since_days)
        if df is not None and not df.empty:
            return df
    return None

COIN_PARAMS = {
    "BTC": {"base_price": 64000, "daily_vol": 0.035, "drift": 0.0002},
    "ETH": {"base_price": 3400,  "daily_vol": 0.045, "drift": 0.0001},
    "LTC": {"base_price": 85,    "daily_vol": 0.050, "drift": -0.0001},
    "LINK": {"base_price": 14,   "daily_vol": 0.055, "drift": 0.0003},
    "BCH": {"base_price": 450,   "daily_vol": 0.048, "drift": -0.0002},
    "ZEC": {"base_price": 28,    "daily_vol": 0.052, "drift": -0.0001},
    "XLM": {"base_price": 0.11,  "daily_vol": 0.055, "drift": 0.0001},
    "AAVE": {"base_price": 95,   "daily_vol": 0.060, "drift": 0.0002},
    "USDC": {"base_price": 1.0,  "daily_vol": 0.0005, "drift": 0.0},
}

PAIRS = {
    "BTC/USD": ("BTC", "USD"),
    "ETH/USD": ("ETH", "USD"),
    "LTC/USD": ("LTC", "USD"),
    "LINK/USD": ("LINK", "USD"),
    "BCH/USD": ("BCH", "USD"),
    "ZEC/USD": ("ZEC", "USD"),
    "XLM/USD": ("XLM", "USD"),
    "AAVE/USD": ("AAVE", "USD"),
    "ETH/BTC": ("ETH", "BTC"),
    "LTC/BTC": ("LTC", "BTC"),
    "LINK/BTC": ("LINK", "BTC"),
    "XLM/BTC": ("XLM", "BTC"),
    "AAVE/ETH": ("AAVE", "ETH"),
    "LINK/ETH": ("LINK", "ETH"),
    "USDC/USD": ("USDC", "USD"),
}

EXCHANGE_SPREADS = {
    "kraken":   {"base_spread": 0.0002, "fee": 0.0026},
    "coinbase": {"base_spread": 0.0003, "fee": 0.005},
    "gemini":   {"base_spread": 0.00025, "fee": 0.0035},
}

EXCHANGE_PRICE_PARAMS = {
    "kraken":   {"ou_mean": 0.0,     "ou_sigma": 0.0007,  "ou_theta": 0.05},
    "coinbase": {"ou_mean": 0.0006,  "ou_sigma": 0.00085, "ou_theta": 0.04},
    "gemini":   {"ou_mean": -0.0003, "ou_sigma": 0.00055, "ou_theta": 0.06},
}

CORRELATION_MATRIX = {
    "BTC": {"BTC": 1.0, "ETH": 0.85, "LTC": 0.75, "LINK": 0.65, "BCH": 0.80, "ZEC": 0.60, "XLM": 0.55, "AAVE": 0.60, "USDC": -0.05},
    "ETH": {"BTC": 0.85, "ETH": 1.0, "LTC": 0.70, "LINK": 0.75, "BCH": 0.65, "ZEC": 0.55, "XLM": 0.60, "AAVE": 0.75, "USDC": -0.05},
}

_generated_cache = {}


def _stable_hash(s):
    h = 5381
    for c in s:
        h = ((h << 5) + h + ord(c)) & 0xFFFFFFFF
    return h


def _generate_correlated_returns(n_steps, coins, seed=42):
    rng = np.random.RandomState(seed)
    n_coins = len(coins)

    corr = np.eye(n_coins)
    for i, c1 in enumerate(coins):
        for j, c2 in enumerate(coins):
            if i != j:
                if c1 in CORRELATION_MATRIX and c2 in CORRELATION_MATRIX[c1]:
                    corr[i, j] = CORRELATION_MATRIX[c1][c2]
                elif c2 in CORRELATION_MATRIX and c1 in CORRELATION_MATRIX[c2]:
                    corr[i, j] = CORRELATION_MATRIX[c2][c1]
                else:
                    corr[i, j] = 0.5

    eigvals = np.linalg.eigvalsh(corr)
    if np.min(eigvals) < 0:
        corr += (-np.min(eigvals) + 0.01) * np.eye(n_coins)
        d = np.sqrt(np.diag(corr))
        corr = corr / np.outer(d, d)

    L = np.linalg.cholesky(corr)
    independent = rng.randn(n_steps, n_coins)
    correlated = independent @ L.T

    return correlated


def _generate_garch_vol(n_steps, base_vol, rng):
    omega = base_vol ** 2 * 0.05
    alpha = 0.10
    beta = 0.85
    vol = np.zeros(n_steps)
    vol[0] = base_vol
    innovations = rng.randn(n_steps)

    for t in range(1, n_steps):
        vol[t] = np.sqrt(omega + alpha * (innovations[t-1] * vol[t-1])**2 + beta * vol[t-1]**2)
        vol[t] = np.clip(vol[t], base_vol * 0.3, base_vol * 3.0)

    return vol, innovations


def generate_pair_data(pair_name, interval_minutes=5, n_days=15, seed=42):
    cache_key = f"{pair_name}_{interval_minutes}_{n_days}_{seed}"
    if cache_key in _generated_cache:
        return _generated_cache[cache_key]

    base_coin, quote_coin = PAIRS[pair_name]
    rng = np.random.RandomState(seed + _stable_hash(pair_name) % 10000)

    n_steps = int(n_days * 24 * 60 / interval_minutes)
    dt = interval_minutes / (24 * 60)

    if quote_coin == "USD":
        params = COIN_PARAMS[base_coin]
        base_price = params["base_price"]
        daily_vol = params["daily_vol"]
        drift = params["drift"]
    else:
        base_params = COIN_PARAMS[base_coin]
        quote_params = COIN_PARAMS[quote_coin]
        base_price = base_params["base_price"] / quote_params["base_price"]
        daily_vol = np.sqrt(base_params["daily_vol"]**2 + quote_params["daily_vol"]**2
                            - 2 * 0.7 * base_params["daily_vol"] * quote_params["daily_vol"])
        drift = base_params["drift"] - quote_params["drift"]

    vol_per_step = daily_vol * np.sqrt(dt)
    drift_per_step = drift * dt

    vol_series, innovations = _generate_garch_vol(n_steps, vol_per_step, rng)

    prices = np.zeros(n_steps)
    prices[0] = base_price

    mean_reversion_strength = 0.01
    log_base = np.log(base_price)

    for t in range(1, n_steps):
        mr = -mean_reversion_strength * (np.log(prices[t-1]) - log_base) * dt * 24 * 60
        log_return = drift_per_step + mr + vol_series[t] * innovations[t]
        prices[t] = prices[t-1] * np.exp(log_return)

    end_time = datetime(2026, 8, 24, 0, 0, 0)
    start_time = end_time - timedelta(days=n_days)
    timestamps = pd.date_range(start=start_time, periods=n_steps, freq=f"{interval_minutes}min")

    highs = prices * (1 + np.abs(rng.randn(n_steps)) * vol_per_step * 0.5)
    lows = prices * (1 - np.abs(rng.randn(n_steps)) * vol_per_step * 0.5)
    opens = np.roll(prices, 1)
    opens[0] = base_price

    base_volume = base_price * 100
    volume = base_volume * np.exp(rng.randn(n_steps) * 0.5) * (1 + 0.3 * np.abs(innovations))

    hour_of_day = np.array([t.hour for t in timestamps])
    volume_multiplier = 1 + 0.5 * np.sin(2 * np.pi * (hour_of_day - 14) / 24)
    volume *= volume_multiplier

    vwap = (highs + lows + prices) / 3

    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": prices,
        "vwap": vwap,
        "volume": volume,
        "count": (rng.poisson(50, n_steps) * volume_multiplier).astype(int),
        "pair": pair_name,
    })

    _generated_cache[cache_key] = df
    return df


def generate_exchange_prices(base_df, exchange_name, seed=42):
    spread = EXCHANGE_SPREADS[exchange_name]
    params = EXCHANGE_PRICE_PARAMS[exchange_name]

    rng = np.random.RandomState(seed + _stable_hash(exchange_name) % 10000)
    n = len(base_df)

    offset = np.zeros(n)
    offset[0] = params["ou_mean"]
    for t in range(1, n):
        offset[t] = (offset[t-1]
                     + params["ou_theta"] * (params["ou_mean"] - offset[t-1])
                     + params["ou_sigma"] * rng.randn())

    pair_noise = np.zeros(n)
    for t in range(1, n):
        pair_noise[t] = 0.93 * pair_noise[t-1] + rng.randn() * 0.0006

    total_offset = offset + pair_noise

    divergence_mask = rng.random(n) < 0.005
    n_div = divergence_mask.sum()
    if n_div > 0:
        total_offset[divergence_mask] += (
            rng.choice([-1, 1], size=n_div)
            * (0.003 + rng.exponential(0.002, n_div))
        )

    df = base_df.copy()
    df["exchange"] = exchange_name
    df["bid"] = df["close"] * (1 - spread["base_spread"] / 2) * (1 + total_offset)
    df["ask"] = df["close"] * (1 + spread["base_spread"] / 2) * (1 + total_offset)
    df["fee_rate"] = spread["fee"]
    df["bid_after_fee"] = df["bid"] * (1 - spread["fee"])
    df["ask_after_fee"] = df["ask"] * (1 + spread["fee"])

    return df


def _derive_cross_pair(all_data, pair_name, base_coin, quote_coin, seed=42):
    """Derive cross-pair prices from constituent USD pairs with small noise."""
    base_usd = f"{base_coin}/USD"
    quote_usd = f"{quote_coin}/USD"

    if base_usd not in all_data or quote_usd not in all_data:
        return generate_pair_data(pair_name, 5, 15, seed)

    base_df = all_data[base_usd]
    quote_df = all_data[quote_usd]

    n = min(len(base_df), len(quote_df))
    rng = np.random.RandomState(seed + _stable_hash(pair_name) % 10000)

    implied_close = base_df["close"].values[:n] / quote_df["close"].values[:n]

    noise = rng.randn(n) * 0.0003
    ar_noise = np.zeros(n)
    for t in range(1, n):
        ar_noise[t] = 0.92 * ar_noise[t-1] + rng.randn() * 0.0002
    total_noise = noise + ar_noise

    close = implied_close * (1 + total_noise)

    vol_per_step = np.std(np.diff(np.log(implied_close))) if n > 1 else 0.001
    highs = close * (1 + np.abs(rng.randn(n)) * vol_per_step * 0.5)
    lows = close * (1 - np.abs(rng.randn(n)) * vol_per_step * 0.5)
    opens = np.roll(close, 1)
    opens[0] = close[0]
    vwap_vals = (highs + lows + close) / 3

    volume = np.minimum(base_df["volume"].values[:n], quote_df["volume"].values[:n]) * 0.3
    volume *= (1 + rng.randn(n) * 0.2).clip(0.5, 2.0)

    df = pd.DataFrame({
        "timestamp": base_df["timestamp"].values[:n],
        "open": opens,
        "high": highs,
        "low": lows,
        "close": close,
        "vwap": vwap_vals,
        "volume": volume,
        "count": (rng.poisson(30, n)).astype(int),
        "pair": pair_name,
    })
    return df


CROSS_PAIRS = {
    "ETH/BTC": ("ETH", "BTC"),
    "LTC/BTC": ("LTC", "BTC"),
    "LINK/BTC": ("LINK", "BTC"),
    "XLM/BTC": ("XLM", "BTC"),
    "AAVE/ETH": ("AAVE", "ETH"),
    "LINK/ETH": ("LINK", "ETH"),
}


def fetch_all_pairs(interval=5, since_days=15, seed=42):
    import time as _time
    all_data = {}
    real_count = 0

    usd_pairs = {k: v for k, v in PAIRS.items() if v[1] == "USD"}
    cross_pairs = {k: v for k, v in PAIRS.items() if v[1] != "USD"}

    for pair_name in usd_pairs:
        df = None
        if USE_REAL_DATA:
            print(f"  Fetching {pair_name} (live)...", end=" ", flush=True)
            df = _try_fetch_real_ohlcv(pair_name, interval, since_days)
            if df is not None and not df.empty:
                real_count += 1
                print(f"{len(df)} candles (real)")
                all_data[pair_name] = df
                _time.sleep(1)
                continue
            else:
                print("unavailable, ", end="", flush=True)

        if not USE_REAL_DATA:
            print(f"  Generating {pair_name} (synthetic)...", end=" ", flush=True)
        df = generate_pair_data(pair_name, interval, since_days, seed)
        all_data[pair_name] = df
        print(f"{len(df)} candles")

    for pair_name, (base_coin, quote_coin) in cross_pairs.items():
        if USE_REAL_DATA:
            print(f"  Fetching {pair_name} (live)...", end=" ", flush=True)
            df = _try_fetch_real_ohlcv(pair_name, interval, since_days)
            if df is not None and not df.empty:
                real_count += 1
                print(f"{len(df)} candles (real)")
                all_data[pair_name] = df
                _time.sleep(1)
                continue
            else:
                print("unavailable, ", end="", flush=True)

        print(f"  Deriving {pair_name} from USD pairs...", end=" ", flush=True)
        df = _derive_cross_pair(all_data, pair_name, base_coin, quote_coin, seed)
        all_data[pair_name] = df
        print(f"{len(df)} candles")

    if USE_REAL_DATA:
        print(f"\n  Data source: {real_count}/{len(PAIRS)} pairs from live API, rest synthetic")
    else:
        print(f"\n  Data source: all synthetic (set ARBITCOIN_REAL_DATA=1 for live API)")

    return all_data


def build_exchange_books(all_pair_data, seed=42):
    exchange_books = {ex: {} for ex in EXCHANGE_SPREADS}

    for pair_name, base_df in all_pair_data.items():
        for ex_name in EXCHANGE_SPREADS:
            ex_df = generate_exchange_prices(base_df, ex_name, seed)
            exchange_books[ex_name][pair_name] = ex_df

    return exchange_books


def build_time_index(exchange_books):
    time_index = {}
    for ex_name, pairs in exchange_books.items():
        time_index[ex_name] = {}
        for pair_name, df in pairs.items():
            indexed = df.set_index("timestamp").sort_index()
            time_index[ex_name][pair_name] = indexed
    return time_index


def get_snapshot_at_time(exchange_books, target_time, time_index=None):
    snapshot = {}
    source = time_index if time_index else exchange_books

    for ex_name, pairs in source.items():
        snapshot[ex_name] = {}
        for pair_name, data in pairs.items():
            if time_index:
                idx = data.index.searchsorted(target_time, side="right") - 1
                if idx < 0:
                    continue
                row = data.iloc[idx]
            else:
                mask = data["timestamp"] <= target_time
                if not mask.any():
                    continue
                row = data[mask].iloc[-1]

            snapshot[ex_name][pair_name] = {
                "bid": row["bid"],
                "ask": row["ask"],
                "bid_after_fee": row["bid_after_fee"],
                "ask_after_fee": row["ask_after_fee"],
                "close": row["close"],
                "volume": row["volume"],
                "vwap": row["vwap"],
                "fee_rate": row["fee_rate"],
            }
    return snapshot


if __name__ == "__main__":
    print("Generating synthetic market data...")
    data = fetch_all_pairs(interval=5, since_days=15)
    print(f"\nGenerated {len(data)} pairs")
    for pair, df in data.items():
        print(f"  {pair}: {len(df)} candles, {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"    Price range: {df['close'].min():.4f} - {df['close'].max():.4f}")
