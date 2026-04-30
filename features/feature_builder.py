"""
AI_Trader 特徴量マトリクス構築モジュール

テクニカル指標の計算結果から、AIモデルへの入力となる
特徴量マトリクス（13指標 × 25日 = 325次元）を構築する。

CNN入力: (batch, 13, 25, 1) の2D画像的表現
LSTM入力: (batch, 25, 13) の時系列シーケンス
"""

import logging
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from features.indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class FeatureBuilder:
    """
    特徴量マトリクス構築クラス。

    テクニカル指標を計算し、AIモデルの入力形式に変換する。
    """

    def __init__(self, config):
        """
        Args:
            config: ConfigAccessorインスタンス
        """
        self.config = config
        self.indicators = TechnicalIndicators(config)
        self.lookback_days = config.get("features.lookback_days", 25)

        # 使用する指標列名のリスト
        self._feature_columns = None

    def build(
        self,
        df: pd.DataFrame,
        for_training: bool = False,
    ) -> Optional[np.ndarray]:
        """
        OHLCV DataFrameから特徴量マトリクスを構築する。

        リアルタイム推論時: 最新のlookback_days期間分の特徴量を1サンプルとして返す
        学習時: 全期間のスライディングウィンドウで複数サンプルを生成

        Args:
            df: OHLCV DataFrame
            for_training: True=学習用（複数サンプル）、False=推論用（1サンプル）

        Returns:
            特徴量配列。shape: (n_samples, n_indicators, lookback_days)
            推論時はn_samples=1。データ不足の場合はNone。
        """
        if df is None or len(df) < self.lookback_days + 200:
            # MA(200)の計算に最低200期間必要
            logger.warning(
                f"データ不足: {len(df) if df is not None else 0}行 "
                f"(最低{self.lookback_days + 200}行必要)"
            )
            return None

        # テクニカル指標を計算
        df_with_indicators = self.indicators.calculate_all(df)

        # 使用する特徴量列を決定
        if self._feature_columns is None:
            self._feature_columns = self.indicators.get_indicator_columns()

        # NaN除去（指標計算の初期値が安定するまでのウォームアップ期間）
        feature_df = df_with_indicators[self._feature_columns].dropna()

        if len(feature_df) < self.lookback_days:
            logger.warning(
                f"指標計算後のデータ不足: {len(feature_df)}行 "
                f"(lookback={self.lookback_days}行必要)"
            )
            return None

        if for_training:
            return self._build_training_samples(feature_df)
        else:
            return self._build_inference_sample(feature_df)

    def _build_inference_sample(
        self, feature_df: pd.DataFrame
    ) -> np.ndarray:
        """
        推論用の1サンプルを構築する（最新のlookback期間）。

        Args:
            feature_df: 指標計算済みDataFrame

        Returns:
            shape: (1, n_indicators, lookback_days) の配列
        """
        # 最新のlookback_days期間を取得
        window = feature_df.iloc[-self.lookback_days:]
        matrix = window.values.T  # (n_indicators, lookback_days)

        # 特徴量の正規化（各指標を0-1にスケール）
        matrix = self._normalize_features(matrix)

        return matrix[np.newaxis, ...]  # バッチ次元追加

    def _build_training_samples(
        self, feature_df: pd.DataFrame
    ) -> np.ndarray:
        """
        学習用の複数サンプルをスライディングウィンドウで構築する。

        Args:
            feature_df: 指標計算済みDataFrame

        Returns:
            shape: (n_samples, n_indicators, lookback_days) の配列
        """
        values = feature_df.values  # (time_steps, n_indicators)
        n_indicators = values.shape[1]
        n_samples = len(values) - self.lookback_days + 1

        if n_samples <= 0:
            logger.warning("サンプル数が0です")
            return np.array([])

        # スライディングウィンドウでサンプル生成
        samples = np.zeros(
            (n_samples, n_indicators, self.lookback_days)
        )

        for i in range(n_samples):
            window = values[i : i + self.lookback_days]
            samples[i] = window.T  # (n_indicators, lookback_days)

        # 各サンプルを正規化
        for i in range(n_samples):
            samples[i] = self._normalize_features(samples[i])

        logger.info(
            f"学習サンプル生成: {n_samples}サンプル "
            f"(形状: {samples.shape})"
        )
        return samples

    def build_labels(
        self,
        df: pd.DataFrame,
        horizon: int = 1,
        threshold: float = 0.0,
    ) -> Optional[np.ndarray]:
        """
        学習用のラベル（目的変数）を生成する。

        次足のリターンの方向（Buy=1, Sell=0）をラベルとする。
        「次足始値」約定前提のため、次の足の終値で評価。

        Args:
            df: OHLCV DataFrame
            horizon: 予測する先のバー数
            threshold: ラベルのしきい値（0の場合は方向のみ）

        Returns:
            ラベル配列。shape: (n_samples,)
        """
        if df is None or len(df) < self.lookback_days + 200 + horizon:
            return None

        # テクニカル指標を計算してNaN除去
        df_with_indicators = self.indicators.calculate_all(df)
        feature_df = df_with_indicators[
            self.indicators.get_indicator_columns()
        ].dropna()

        # リターン計算（horizon足先の終値変化率）
        # feature_dfのインデックスを使って元のclose値を参照
        close_prices = df.loc[feature_df.index, "close"]
        future_returns = close_prices.shift(-horizon) / close_prices - 1

        # lookback_days分のオフセット後、NaN除去前のインデックスに合わせる
        n_samples = len(feature_df) - self.lookback_days + 1
        labels = future_returns.iloc[
            self.lookback_days - 1 : self.lookback_days - 1 + n_samples
        ].values

        # 方向ラベル: 1=Buy, 0=Sell
        if threshold > 0:
            # 閾値を超える変動のみをラベル付け
            labels = np.where(labels > threshold, 1, np.where(labels < -threshold, 0, -1))
        else:
            labels = np.where(labels >= 0, 1, 0)

        # NaN除去
        valid_mask = ~np.isnan(labels) & (labels >= 0)
        labels = labels[valid_mask].astype(int)

        logger.info(
            f"ラベル生成: {len(labels)}サンプル "
            f"(Buy: {np.sum(labels == 1)}, Sell: {np.sum(labels == 0)})"
        )
        return labels

    @staticmethod
    def _normalize_features(matrix: np.ndarray) -> np.ndarray:
        """
        特徴量マトリクスを指標ごとに0-1正規化する。

        各指標（行）を独立して正規化することで、
        スケールの異なる指標間の比較を可能にする。

        Args:
            matrix: shape (n_indicators, lookback_days)

        Returns:
            正規化されたmatrix
        """
        normalized = np.zeros_like(matrix, dtype=np.float32)
        for i in range(matrix.shape[0]):
            row = matrix[i]
            row_min = np.nanmin(row)
            row_max = np.nanmax(row)
            row_range = row_max - row_min

            if row_range == 0 or np.isnan(row_range):
                # 変動がない場合は0.5で埋める
                normalized[i] = 0.5
            else:
                normalized[i] = (row - row_min) / row_range

        return normalized

    def get_feature_shape(self) -> Tuple[int, int]:
        """
        特徴量マトリクスの形状を返す。

        Returns:
            (n_indicators, lookback_days) のタプル
        """
        if self._feature_columns is None:
            self._feature_columns = self.indicators.get_indicator_columns()
        return (len(self._feature_columns), self.lookback_days)

    def reshape_for_cnn(self, features: np.ndarray) -> np.ndarray:
        """
        CNN入力用に4D テンソルにリシェイプする。

        Args:
            features: shape (n_samples, n_indicators, lookback_days)

        Returns:
            shape (n_samples, n_indicators, lookback_days, 1)
        """
        return features[..., np.newaxis]

    def reshape_for_lstm(self, features: np.ndarray) -> np.ndarray:
        """
        LSTM入力用に転置する。

        Args:
            features: shape (n_samples, n_indicators, lookback_days)

        Returns:
            shape (n_samples, lookback_days, n_indicators)
        """
        return np.transpose(features, (0, 2, 1))
