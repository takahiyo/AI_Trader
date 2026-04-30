"""
AI_Trader ATRベース動的エグジット計算

ATR（Average True Range）に基づき、
市場のノイズ幅に応じた数学的に一貫した
ストップロス/テイクプロフィット距離を設定する。
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ATRExitCalculator:
    """ATRベースのSL/TP距離計算。"""

    def __init__(self, config):
        self.config = config
        self.atr_period = config.get("features.indicators.atr.period", 14)
        self.sl_multiplier = config.get("risk.atr_exit.sl_multiplier", 2.0)
        self.tp_multiplier = config.get("risk.atr_exit.tp_multiplier", 1.5)
        self.pip_value = 0.0001

    def calculate_atr(self, df: pd.DataFrame) -> float:
        """
        最新のATR値を計算する（pips単位）。

        Args:
            df: OHLCV DataFrame

        Returns:
            ATR値（pips）
        """
        if len(df) < self.atr_period + 1:
            return 20.0  # デフォルト値

        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift(1))
        low_close = abs(df["low"] - df["close"].shift(1))

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.ewm(span=self.atr_period, adjust=False).mean().iloc[-1]

        return atr / self.pip_value  # pipsに変換

    def calculate_exits(self, atr_pips: float) -> tuple:
        """
        ATRベースのSL/TP距離を計算する。

        Args:
            atr_pips: ATR値（pips）

        Returns:
            (sl_distance_pips, tp_distance_pips) のタプル
        """
        sl = atr_pips * self.sl_multiplier
        tp = atr_pips * self.tp_multiplier

        # 最低SL距離（ノイズに引っかからないため）
        sl = max(sl, 5.0)

        logger.debug(f"ATRエグジット: ATR={atr_pips:.1f}, SL={sl:.1f}, TP={tp:.1f}")
        return sl, tp
