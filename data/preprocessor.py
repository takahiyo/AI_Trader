"""
AI_Trader データ前処理モジュール

1分足データから各タイムフレームへのリサンプリング、
ボラティリティ情報を保持するスケーリング、欠損値処理を行う。

設計原則:
- スケーリング時にボラティリティ（標準偏差）情報を欠落させない
- FXにおいて変動幅はエッジの源泉であるため、σ情報の保持は必須
"""

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# pandas リサンプリングルール対応表
_RESAMPLE_RULES = {
    "1min": "1min",
    "5min": "5min",
    "15min": "15min",
    "30min": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}


class VolatilityAwareScaler:
    """
    ボラティリティ情報を保持するカスタムスケーラー。

    StandardScalerはσ情報を1に正規化してしまい、
    ボラティリティ情報が失われる。
    本スケーラーは、価格系列の相対変動（リターン）ベースでスケーリングし、
    σの大小関係を保持する。

    手法:
    1. 価格をリターン（対数変化率）に変換
    2. リターンをRobustScaler（中央値・IQR基準）でスケーリング
    3. 元のσ情報を補助特徴量として保持
    """

    def __init__(self):
        self._median: Optional[pd.Series] = None
        self._iqr: Optional[pd.Series] = None
        self._fitted = False

    def fit(self, df: pd.DataFrame) -> "VolatilityAwareScaler":
        """
        スケーリングパラメータを学習する。

        Args:
            df: OHLCV DataFrame

        Returns:
            self（メソッドチェーン用）
        """
        price_cols = [c for c in ["open", "high", "low", "close"] if c in df.columns]
        returns = df[price_cols].pct_change().dropna()

        self._median = returns.median()
        q75 = returns.quantile(0.75)
        q25 = returns.quantile(0.25)
        self._iqr = q75 - q25

        # IQRが0の場合の対策（変動がない場合）
        self._iqr = self._iqr.replace(0, 1e-10)

        self._fitted = True
        logger.debug(
            f"スケーラーfit完了: median={self._median.to_dict()}, "
            f"IQR={self._iqr.to_dict()}"
        )
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        データをスケーリングする。

        ボラティリティ情報を保持するため:
        1. 価格 → リターンに変換（相対変動に正規化）
        2. RobustScaling（中央値とIQR基準）を適用
        3. ローリングσを補助特徴量として追加

        Args:
            df: OHLCV DataFrame

        Returns:
            スケーリング済みDataFrame（σ補助特徴量付き）
        """
        if not self._fitted:
            raise RuntimeError("先にfit()を呼び出してください")

        result = df.copy()
        price_cols = [c for c in ["open", "high", "low", "close"] if c in df.columns]

        # リターン変換 + RobustScaling
        returns = result[price_cols].pct_change()
        for col in price_cols:
            result[f"{col}_scaled"] = (
                (returns[col] - self._median[col]) / self._iqr[col]
            )

        # ローリングσ（ボラティリティ指標）を保持
        for window in [5, 20]:
            result[f"volatility_{window}"] = (
                returns["close"].rolling(window=window).std()
            )

        # 最初の行（pct_changeによるNaN）を除去
        result = result.dropna()

        logger.debug(f"スケーリング完了: {len(result)}行, 列={list(result.columns)}")
        return result

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """fit()とtransform()を連続実行する。"""
        return self.fit(df).transform(df)

    def get_params(self) -> Dict:
        """学習済みパラメータを返す（モデル保存時に使用）。"""
        if not self._fitted:
            return {}
        return {
            "median": self._median.to_dict(),
            "iqr": self._iqr.to_dict(),
        }


class DataPreprocessor:
    """
    データ前処理クラス。

    リサンプリング、スケーリング、欠損値処理を統合管理する。
    """

    def __init__(self, config):
        """
        Args:
            config: ConfigAccessorインスタンス
        """
        self.config = config
        self.scaler = VolatilityAwareScaler()
        self._scaler_fitted = False

    def resample(
        self,
        df: pd.DataFrame,
        target_timeframe: str,
    ) -> pd.DataFrame:
        """
        1分足データを指定タイムフレームにリサンプリングする。

        OHLCVデータを正確に集約:
        - Open: 期間の最初の値
        - High: 期間の最大値
        - Low: 期間の最小値
        - Close: 期間の最後の値
        - Volume: 期間の合計

        Args:
            df: 1分足OHLCV DataFrame（UTC、time列がインデックス）
            target_timeframe: 目標タイムフレーム

        Returns:
            リサンプリング済みDataFrame
        """
        rule = _RESAMPLE_RULES.get(target_timeframe)
        if rule is None:
            raise ValueError(f"未対応のタイムフレーム: {target_timeframe}")

        # 既に目標のタイムフレームと同等ならそのまま返す
        if target_timeframe == "1min":
            return df.copy()

        ohlcv_agg = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
        }

        # volume列がある場合は合計
        if "volume" in df.columns:
            ohlcv_agg["volume"] = "sum"

        resampled = df.resample(rule).agg(ohlcv_agg).dropna()

        logger.debug(
            f"リサンプリング完了: {target_timeframe} "
            f"({len(df)}行 → {len(resampled)}行)"
        )
        return resampled

    def handle_gaps(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        市場休場時間によるギャップを処理する。

        FX市場は週末（金曜NYクローズ～日曜シドニーオープン）に休場する。
        ギャップ区間は前方埋め（ffill）で処理し、
        過度に長いギャップ（24時間以上）はNaNのままにする。

        Args:
            df: OHLCV DataFrame

        Returns:
            ギャップ処理済みDataFrame
        """
        if df.empty:
            return df

        result = df.copy()

        # 24時間以上のギャップを検出
        time_diff = result.index.to_series().diff()
        large_gaps = time_diff[time_diff > pd.Timedelta(hours=24)]

        if len(large_gaps) > 0:
            logger.info(
                f"大きなギャップを{len(large_gaps)}箇所検出 "
                f"（最大: {large_gaps.max()}）"
            )

        # 短いギャップ（24時間以内）は前方埋め
        result = result.ffill(limit=60 * 24)  # 最大24時間分

        # 残ったNaN（長いギャップ）は除去
        nan_before = result.isnull().sum().sum()
        result = result.dropna()

        if nan_before > 0:
            logger.debug(f"欠損値処理: {nan_before}個のNaN除去")

        return result

    def process(
        self,
        df: pd.DataFrame,
        timeframe: str,
        apply_scaling: bool = False,
    ) -> pd.DataFrame:
        """
        データの前処理パイプラインを実行する。

        1. ギャップ処理
        2. リサンプリング（必要な場合）
        3. スケーリング（フラグが有効な場合）

        Args:
            df: 入力OHLCV DataFrame
            timeframe: 目標タイムフレーム
            apply_scaling: スケーリングを適用するか

        Returns:
            前処理済みDataFrame
        """
        if df is None or df.empty:
            logger.warning("空のDataFrameが渡されました")
            return pd.DataFrame()

        # 1. ギャップ処理
        result = self.handle_gaps(df)

        # 2. リサンプリング
        # 入力データのタイムフレームと目標が異なる場合のみ実行
        # （MT5からは既に目標TFで取得しているため、通常はスキップ）
        # HistDataの1分足から変換する場合に使用
        # result = self.resample(result, timeframe)

        # 3. スケーリング（オプション）
        if apply_scaling:
            if not self._scaler_fitted:
                result = self.scaler.fit_transform(result)
                self._scaler_fitted = True
            else:
                result = self.scaler.transform(result)

        logger.debug(
            f"前処理完了: {timeframe} ({len(result)}行)"
        )
        return result

    def prepare_multi_timeframe(
        self,
        base_data: pd.DataFrame,
        timeframes: list,
    ) -> Dict[str, pd.DataFrame]:
        """
        1分足ベースデータから複数タイムフレームのデータを生成する。

        Args:
            base_data: 1分足OHLCV DataFrame
            timeframes: 生成するタイムフレームのリスト

        Returns:
            {タイムフレーム: DataFrame} の辞書
        """
        result = {}
        cleaned = self.handle_gaps(base_data)

        for tf in timeframes:
            resampled = self.resample(cleaned, tf)
            result[tf] = resampled
            logger.info(
                f"MTFデータ生成: {tf} → {len(resampled)}行"
            )

        return result
