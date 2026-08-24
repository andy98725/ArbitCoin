"""
Market regime detection: identifies trending vs mean-reverting vs high-volatility regimes.
Adjusts strategy parameters dynamically.
"""

import numpy as np
import pandas as pd


class RegimeDetector:

    def __init__(self):
        self.pair_regimes = {}

    def detect(self, pair_name, df):
        if len(df) < 100:
            self.pair_regimes[pair_name] = self._default_regime()
            return self.pair_regimes[pair_name]

        close = df["close"].values
        returns = np.diff(np.log(close))

        vol_20 = np.std(returns[-20:]) * np.sqrt(288)
        vol_60 = np.std(returns[-60:]) * np.sqrt(288)
        vol_ratio = vol_20 / max(vol_60, 1e-10)

        trend_strength = self._hurst_exponent(close[-100:])

        autocorr = np.corrcoef(returns[-50:-1], returns[-49:])[0, 1] if len(returns) >= 50 else 0

        if vol_ratio > 1.5:
            regime = "high_volatility"
        elif trend_strength > 0.55:
            regime = "trending"
        elif trend_strength < 0.45:
            regime = "mean_reverting"
        else:
            regime = "neutral"

        self.pair_regimes[pair_name] = {
            "regime": regime,
            "vol_20d": vol_20,
            "vol_ratio": vol_ratio,
            "hurst": trend_strength,
            "autocorrelation": autocorr,
            "params": self._regime_params(regime, vol_20),
        }
        return self.pair_regimes[pair_name]

    def _hurst_exponent(self, prices):
        if len(prices) < 20:
            return 0.5
        log_prices = np.log(prices)
        lags = range(2, min(20, len(prices) // 4))
        tau = []
        for lag in lags:
            diffs = log_prices[lag:] - log_prices[:-lag]
            tau.append(np.std(diffs))

        if len(tau) < 2 or any(t <= 0 for t in tau):
            return 0.5

        log_lags = np.log(list(lags))
        log_tau = np.log(tau)
        poly = np.polyfit(log_lags, log_tau, 1)
        return poly[0]

    def _regime_params(self, regime, current_vol):
        if regime == "high_volatility":
            return {
                "position_scale": 0.5,
                "arb_threshold_mult": 1.3,
                "prediction_weight": 0.4,
                "stop_loss_mult": 1.8,
            }
        elif regime == "trending":
            return {
                "position_scale": 1.3,
                "arb_threshold_mult": 0.8,
                "prediction_weight": 1.5,
                "stop_loss_mult": 1.0,
            }
        elif regime == "mean_reverting":
            return {
                "position_scale": 1.1,
                "arb_threshold_mult": 0.9,
                "prediction_weight": 1.2,
                "stop_loss_mult": 0.8,
            }
        else:
            return {
                "position_scale": 1.0,
                "arb_threshold_mult": 1.0,
                "prediction_weight": 1.0,
                "stop_loss_mult": 1.0,
            }

    def _default_regime(self):
        return {
            "regime": "neutral",
            "vol_20d": 0.5,
            "vol_ratio": 1.0,
            "hurst": 0.5,
            "autocorrelation": 0.0,
            "params": self._regime_params("neutral", 0.5),
        }

    def get_regime(self, pair_name):
        return self.pair_regimes.get(pair_name, self._default_regime())

    def get_position_scale(self, pair_name):
        return self.get_regime(pair_name)["params"]["position_scale"]

    def get_prediction_weight(self, pair_name):
        return self.get_regime(pair_name)["params"]["prediction_weight"]
