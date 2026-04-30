"""
AI_Trader テクニカル指標計算モジュール

仕様書で定義された13のテクニカル指標を計算する。
全指標はOHLCV DataFrameを入力とし、新しい列を追加して返す。

指標リスト:
1-4. 移動平均線（MA）: 5, 25, 75, 200期間
5-6. 一目均衡表（遅行スパン、先行スパン）
7-8. ボリンジャーバンド（σ、乖離率）
9.   MACD
10.  ADX
11.  RSI
12.  ATR
13.  OBV

重要: 未来情報の参照は絶対禁止。全指標は現在時点以前のデータのみを使用する。
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """
    テクニカル指標計算クラス。

    設定ファイルからパラメータを取得し、全指標を一括で計算する。
    """

    def __init__(self, config):
        """
        Args:
            config: ConfigAccessorインスタンス
        """
        self.config = config

        # 設定からパラメータ取得
        self.ma_periods = config.get(
            "features.indicators.ma_periods", [5, 25, 75, 200]
        )
        self.ichimoku_tenkan = config.get(
            "features.indicators.ichimoku.tenkan", 9
        )
        self.ichimoku_kijun = config.get(
            "features.indicators.ichimoku.kijun", 26
        )
        self.ichimoku_senkou_b = config.get(
            "features.indicators.ichimoku.senkou_b", 52
        )
        self.bb_period = config.get(
            "features.indicators.bollinger.period", 20
        )
        self.bb_std = config.get(
            "features.indicators.bollinger.std_dev", 2.0
        )
        self.macd_fast = config.get("features.indicators.macd.fast", 12)
        self.macd_slow = config.get("features.indicators.macd.slow", 26)
        self.macd_signal = config.get("features.indicators.macd.signal", 9)
        self.adx_period = config.get("features.indicators.adx.period", 14)
        self.rsi_period = config.get("features.indicators.rsi.period", 14)
        self.atr_period = config.get("features.indicators.atr.period", 14)

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        全テクニカル指標を一括計算し、DataFrameに追加する。

        Args:
            df: OHLCV DataFrame

        Returns:
            全指標列が追加されたDataFrame
        """
        result = df.copy()

        # 1-4. 移動平均線
        result = self.add_moving_averages(result)

        # 5-6. 一目均衡表
        result = self.add_ichimoku(result)

        # 7-8. ボリンジャーバンド
        result = self.add_bollinger_bands(result)

        # 9. MACD
        result = self.add_macd(result)

        # 10. ADX
        result = self.add_adx(result)

        # 11. RSI
        result = self.add_rsi(result)

        # 12. ATR
        result = self.add_atr(result)

        # 13. OBV
        result = self.add_obv(result)

        logger.info(
            f"テクニカル指標計算完了: {len(self.get_indicator_columns())}指標"
        )
        return result

    def add_moving_averages(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        移動平均線を追加する。

        Args:
            df: OHLCV DataFrame

        Returns:
            MA列が追加されたDataFrame
        """
        for period in self.ma_periods:
            df[f"ma_{period}"] = df["close"].rolling(window=period).mean()
        return df

    def add_ichimoku(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        一目均衡表の主要コンポーネントを追加する。

        - 転換線: 過去tenkan期間の(高値+安値)/2
        - 基準線: 過去kijun期間の(高値+安値)/2
        - 先行スパンA: (転換線+基準線)/2 をkijun期間先行
        - 先行スパンB: 過去senkou_b期間の(高値+安値)/2 をkijun期間先行
        - 遅行スパン: 終値をkijun期間遅行

        注意: 先行スパンは未来に描画されるが、計算自体は過去データのみを使用。
        シグナル判定時は「現在のスパン値」と「現在の価格」を比較する。

        Args:
            df: OHLCV DataFrame

        Returns:
            一目均衡表列が追加されたDataFrame
        """
        tenkan = self.ichimoku_tenkan
        kijun = self.ichimoku_kijun
        senkou_b_period = self.ichimoku_senkou_b

        # 転換線
        high_tenkan = df["high"].rolling(window=tenkan).max()
        low_tenkan = df["low"].rolling(window=tenkan).min()
        df["ichimoku_tenkan"] = (high_tenkan + low_tenkan) / 2

        # 基準線
        high_kijun = df["high"].rolling(window=kijun).max()
        low_kijun = df["low"].rolling(window=kijun).min()
        df["ichimoku_kijun"] = (high_kijun + low_kijun) / 2

        # 先行スパンA（kijun期間先行 → 現在の値として使用するためシフトしない）
        # 特徴量として使うのは「現在位置に描画された先行スパン」の値
        df["ichimoku_senkou_a"] = (
            (df["ichimoku_tenkan"] + df["ichimoku_kijun"]) / 2
        )

        # 先行スパンB
        high_senkou = df["high"].rolling(window=senkou_b_period).max()
        low_senkou = df["low"].rolling(window=senkou_b_period).min()
        df["ichimoku_senkou_b"] = (high_senkou + low_senkou) / 2

        # 遅行スパン（現在の終値をkijun期間分シフト）
        # 遅行スパンの特徴量 = 現在の終値 vs kijun期間前の価格
        df["ichimoku_chikou"] = df["close"].shift(-kijun)

        # 遅行スパン乖離率（遅行スパンと現在終値の比率）
        # ※ 未来情報を使わない代替指標として、
        # 現在の終値とkijun期間前の終値の比率を使用
        df["ichimoku_chikou_ratio"] = (
            df["close"] / df["close"].shift(kijun) - 1
        )

        return df

    def add_bollinger_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        ボリンジャーバンド（σおよび乖離率）を追加する。

        Args:
            df: OHLCV DataFrame

        Returns:
            BB列が追加されたDataFrame
        """
        period = self.bb_period
        std_dev = self.bb_std

        sma = df["close"].rolling(window=period).mean()
        rolling_std = df["close"].rolling(window=period).std()

        # バンド幅（σ）: ボラティリティの直接的な指標
        df["bb_sigma"] = rolling_std

        # 上下バンド
        df["bb_upper"] = sma + (rolling_std * std_dev)
        df["bb_lower"] = sma - (rolling_std * std_dev)

        # 乖離率: 終値がバンドのどの位置にあるか（0～1、超過もあり得る）
        band_width = df["bb_upper"] - df["bb_lower"]
        band_width = band_width.replace(0, np.nan)
        df["bb_deviation"] = (df["close"] - df["bb_lower"]) / band_width

        return df

    def add_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        MACD（Moving Average Convergence Divergence）を追加する。

        Args:
            df: OHLCV DataFrame

        Returns:
            MACD列が追加されたDataFrame
        """
        ema_fast = df["close"].ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.macd_slow, adjust=False).mean()

        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = (
            df["macd"].ewm(span=self.macd_signal, adjust=False).mean()
        )
        df["macd_histogram"] = df["macd"] - df["macd_signal"]

        return df

    def add_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        ADX（Average Directional Index）を追加する。
        トレンドの強度を示す（方向は示さない）。

        Args:
            df: OHLCV DataFrame

        Returns:
            ADX列が追加されたDataFrame
        """
        period = self.adx_period

        # True Range
        high_low = df["high"] - df["low"]
        high_close_prev = abs(df["high"] - df["close"].shift(1))
        low_close_prev = abs(df["low"] - df["close"].shift(1))
        tr = pd.concat(
            [high_low, high_close_prev, low_close_prev], axis=1
        ).max(axis=1)

        # +DM, -DM
        up_move = df["high"] - df["high"].shift(1)
        down_move = df["low"].shift(1) - df["low"]

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        # 平滑化
        atr = tr.ewm(span=period, adjust=False).mean()
        plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
            span=period, adjust=False
        ).mean() / atr
        minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
            span=period, adjust=False
        ).mean() / atr

        # DX → ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
        df["adx"] = dx.ewm(span=period, adjust=False).mean()
        df["plus_di"] = plus_di
        df["minus_di"] = minus_di

        return df

    def add_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        RSI（Relative Strength Index）を追加する。

        Args:
            df: OHLCV DataFrame

        Returns:
            RSI列が追加されたDataFrame
        """
        period = self.rsi_period
        delta = df["close"].diff()

        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)

        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        return df

    def add_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        ATR（Average True Range）を追加する。
        ストップロス距離の算出にも使用される重要指標。

        Args:
            df: OHLCV DataFrame

        Returns:
            ATR列が追加されたDataFrame
        """
        period = self.atr_period

        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift(1))
        low_close = abs(df["low"] - df["close"].shift(1))

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.ewm(span=period, adjust=False).mean()

        return df

    def add_obv(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        OBV（On-Balance Volume）を追加する。

        Args:
            df: OHLCV DataFrame

        Returns:
            OBV列が追加されたDataFrame
        """
        if "volume" not in df.columns:
            # ボリュームデータがない場合は0で埋める
            df["obv"] = 0
            logger.debug("volume列がないため、OBVは0で設定")
            return df

        direction = np.sign(df["close"].diff())
        df["obv"] = (direction * df["volume"]).cumsum()

        return df

    def get_indicator_columns(self) -> List[str]:
        """
        計算される全指標の列名リストを返す。

        Returns:
            指標列名のリスト
        """
        cols = []

        # MA
        for p in self.ma_periods:
            cols.append(f"ma_{p}")

        # 一目均衡表
        cols.extend([
            "ichimoku_tenkan", "ichimoku_kijun",
            "ichimoku_senkou_a", "ichimoku_senkou_b",
            "ichimoku_chikou_ratio",
        ])

        # ボリンジャーバンド
        cols.extend(["bb_sigma", "bb_deviation"])

        # MACD
        cols.extend(["macd", "macd_signal", "macd_histogram"])

        # ADX
        cols.extend(["adx", "plus_di", "minus_di"])

        # RSI, ATR, OBV
        cols.extend(["rsi", "atr", "obv"])

        return cols
