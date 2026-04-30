"""
AI_Trader MTFフィルターモジュール

短期足（5分）のエントリー判断に対し、
長期足（4時間・日足）のトレンド方向をフィルターとして適用する
「順張り回帰アルゴリズム」。
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MTFFilter:
    """マルチタイムフレーム順張りフィルター。"""

    def __init__(self, config):
        self.config = config
        self.enabled = config.get("strategy.trend_filter_enabled", True)
        self.trend_timeframes = config.get(
            "strategy.trend_timeframes", ["4h", "1d"]
        )

    def is_aligned(
        self,
        signal,
        processed_data: Dict[str, pd.DataFrame],
    ) -> bool:
        """
        シグナルが長期トレンドと一致しているかチェックする。

        条件: 全ての長期足で同一方向のトレンドが確認された場合のみ許可。

        Args:
            signal: TradeSignal（direction: 1=Buy, -1=Sell）
            processed_data: {timeframe: DataFrame} の辞書

        Returns:
            トレンドと整合していればTrue
        """
        if not self.enabled or signal.direction == 0:
            return True

        for tf in self.trend_timeframes:
            if tf not in processed_data:
                logger.debug(f"MTFフィルター: {tf}データなし、スキップ")
                continue

            df = processed_data[tf]
            if len(df) < 50:
                continue

            trend = self._detect_trend(df)

            # 長期トレンドと逆方向のシグナルは却下
            if trend != 0 and trend != signal.direction:
                logger.debug(
                    f"MTFフィルター却下: {tf}トレンド={trend}, "
                    f"シグナル={signal.direction}"
                )
                return False

        return True

    def _detect_trend(self, df: pd.DataFrame) -> int:
        """
        MA(25)とMA(75)のクロスでトレンド方向を判定する。

        Returns:
            1=上昇, -1=下降, 0=不明
        """
        close = df["close"]
        ma_short = close.rolling(25).mean()
        ma_long = close.rolling(75).mean()

        if ma_short.iloc[-1] > ma_long.iloc[-1]:
            return 1
        elif ma_short.iloc[-1] < ma_long.iloc[-1]:
            return -1
        return 0
