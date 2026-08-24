"""
Market prediction signals: momentum, mean-reversion, and ML-based price prediction.
"""

import numpy as np
import pandas as pd


def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def sma(series, window):
    return series.rolling(window=window).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def bollinger_bands(series, window=20, num_std=2):
    middle = sma(series, window)
    std = series.rolling(window=window).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return lower, middle, upper


def macd(series, fast=12, slow=26, signal=9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def vwap(df):
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum()
    return cumulative_tp_vol / cumulative_vol.replace(0, np.nan)


def atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def compute_features(df):
    close = df["close"].copy()
    features = pd.DataFrame(index=df.index)

    features["ema_5"] = ema(close, 5)
    features["ema_20"] = ema(close, 20)
    features["ema_50"] = ema(close, 50)

    features["ema_cross_5_20"] = (features["ema_5"] - features["ema_20"]) / features["ema_20"]
    features["ema_cross_20_50"] = (features["ema_20"] - features["ema_50"]) / features["ema_50"]

    features["rsi_14"] = rsi(close, 14)
    features["rsi_7"] = rsi(close, 7)

    bb_lower, bb_mid, bb_upper = bollinger_bands(close, 20, 2)
    features["bb_position"] = (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)

    macd_line, signal_line, histogram = macd(close)
    features["macd_hist"] = histogram / close

    features["momentum_5"] = close.pct_change(5)
    features["momentum_20"] = close.pct_change(20)

    features["volatility_20"] = close.pct_change().rolling(20).std()

    if "volume" in df.columns:
        features["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean().replace(0, np.nan)
        features["vwap_diff"] = (close - vwap(df)) / close

    if "high" in df.columns and "low" in df.columns:
        features["atr_14"] = atr(df, 14) / close

    features["returns_1"] = close.pct_change(1)
    features["returns_3"] = close.pct_change(3)

    log_close = np.log(close)
    roll_mean = log_close.rolling(100).mean()
    roll_std = log_close.rolling(100).std()
    features["zscore"] = (log_close - roll_mean) / roll_std.replace(0, np.nan)

    return features


class PredictionEngine:

    def __init__(self):
        self.pair_features = {}
        self.pair_signals = {}
        self._signal_history = {}

    def update(self, pair_name, df):
        if len(df) < 60:
            return

        features = compute_features(df)
        self.pair_features[pair_name] = features

        latest = features.iloc[-1]
        signal = self._generate_signal(latest, pair_name)
        self.pair_signals[pair_name] = signal
        if pair_name not in self._signal_history:
            self._signal_history[pair_name] = []
        self._signal_history[pair_name].append(signal["score"])
        if len(self._signal_history[pair_name]) > 10:
            self._signal_history[pair_name] = self._signal_history[pair_name][-10:]

    def _generate_signal(self, features, pair_name):
        score = 0.0
        reasons = []

        ema_cross = features.get("ema_cross_5_20", 0)
        if not np.isnan(ema_cross):
            if ema_cross > 0.003:
                score += 1.5
                reasons.append("EMA5>EMA20 bullish")
            elif ema_cross < -0.003:
                score -= 1.5
                reasons.append("EMA5<EMA20 bearish")
            elif ema_cross > 0.001:
                score += 0.5
            elif ema_cross < -0.001:
                score -= 0.5

        rsi_val = features.get("rsi_14", 50)
        if not np.isnan(rsi_val):
            if rsi_val < 25:
                score += 2.5
                reasons.append(f"RSI deeply oversold ({rsi_val:.0f})")
            elif rsi_val < 35:
                score += 1.5
                reasons.append(f"RSI oversold ({rsi_val:.0f})")
            elif rsi_val > 75:
                score -= 2.5
                reasons.append(f"RSI deeply overbought ({rsi_val:.0f})")
            elif rsi_val > 65:
                score -= 1.5
                reasons.append(f"RSI overbought ({rsi_val:.0f})")

        bb_pos = features.get("bb_position", 0.5)
        if not np.isnan(bb_pos):
            if bb_pos < 0.05:
                score += 2.0
                reasons.append("Below lower BB")
            elif bb_pos < 0.15:
                score += 1.0
            elif bb_pos > 0.95:
                score -= 2.0
                reasons.append("Above upper BB")
            elif bb_pos > 0.85:
                score -= 1.0

        macd_h = features.get("macd_hist", 0)
        if not np.isnan(macd_h):
            if macd_h > 0.0005:
                score += 1.0
                reasons.append("MACD bullish")
            elif macd_h < -0.0005:
                score -= 1.0
                reasons.append("MACD bearish")

        mom_5 = features.get("momentum_5", 0)
        if not np.isnan(mom_5):
            if mom_5 > 0.02:
                score += 0.75
                reasons.append("Strong 5-bar momentum")
            elif mom_5 < -0.02:
                score -= 0.75
                reasons.append("Weak 5-bar momentum")

        ret_1 = features.get("returns_1", 0)
        ret_3 = features.get("returns_3", 0)
        if not np.isnan(ret_1) and not np.isnan(ret_3):
            if ret_3 < -0.03 and ret_1 > 0:
                score += 1.0
                reasons.append("Reversal after drop")
            elif ret_3 > 0.03 and ret_1 < 0:
                score -= 1.0
                reasons.append("Reversal after rally")

        zscore = features.get("zscore", 0)
        if not np.isnan(zscore):
            if zscore < -2.0:
                score += 3.0
                reasons.append(f"Z-score deeply oversold ({zscore:.1f})")
            elif zscore < -1.2:
                score += 2.0
                reasons.append(f"Z-score oversold ({zscore:.1f})")
            elif zscore > 2.0:
                score -= 3.0
                reasons.append(f"Z-score deeply overbought ({zscore:.1f})")
            elif zscore > 1.2:
                score -= 2.0
                reasons.append(f"Z-score overbought ({zscore:.1f})")

        vol_ratio = features.get("volume_ratio", 1.0)
        if not np.isnan(vol_ratio) and vol_ratio > 1.5:
            score *= min(1 + (vol_ratio - 1) * 0.2, 1.5)
            reasons.append(f"High volume ({vol_ratio:.1f}x)")

        confidence = min(abs(score) / 5.0, 1.0)
        direction = "buy" if score > 0 else "sell" if score < 0 else "hold"

        if abs(score) < 1.0:
            direction = "hold"
            confidence *= 0.5

        return {
            "pair": pair_name,
            "direction": direction,
            "score": score,
            "confidence": confidence,
            "reasons": reasons,
        }

    def get_signal(self, pair_name):
        return self.pair_signals.get(pair_name)

    def get_all_signals(self):
        return dict(self.pair_signals)

    def get_top_opportunities(self, n=5):
        signals = list(self.pair_signals.values())
        signals.sort(key=lambda s: abs(s["score"]) * s["confidence"], reverse=True)
        return [s for s in signals[:n] if s["direction"] != "hold"]

    def get_signal_momentum(self, pair_name):
        if pair_name not in self._signal_history:
            return 0.0
        history = self._signal_history[pair_name]
        if len(history) < 2:
            return 0.0
        recent = history[-1]
        prev = history[-2]
        return recent - prev

    def get_atr_pct(self, pair_name):
        feat = self.pair_features.get(pair_name)
        if feat is None or "atr_14" not in feat.columns:
            return None
        val = feat["atr_14"].iloc[-1]
        return val if not np.isnan(val) else None

    def get_order_flow_signal(self, pair_name):
        feat = self.pair_features.get(pair_name)
        if feat is None:
            return 0.0
        vr = feat.get("volume_ratio")
        if vr is None:
            return 0.0
        latest_vr = vr.iloc[-1] if not isinstance(vr, float) else vr
        if np.isnan(latest_vr):
            return 0.0
        ret_1 = feat["returns_1"].iloc[-1] if "returns_1" in feat.columns else 0
        if np.isnan(ret_1):
            return 0.0
        if latest_vr > 1.5 and ret_1 > 0.005:
            return 1.0
        elif latest_vr > 1.5 and ret_1 < -0.005:
            return -1.0
        return 0.0
