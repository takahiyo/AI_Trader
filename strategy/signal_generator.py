"""
AI_Trader シグナル生成モジュール

AIモデル（ONNX）の推論結果からトレードシグナルを生成する。
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """トレードシグナル。"""
    direction: int = 0      # 1=Buy, -1=Sell, 0=NoTrade
    strength: float = 0.0   # シグナル強度（0.0～1.0）
    probabilities: Optional[np.ndarray] = None  # [Sell, Hold, Buy]


class SignalGenerator:
    """AIモデル推論によるシグナル生成。"""

    def __init__(self, config):
        self.config = config
        self._onnx_session = None
        self._model_loaded = False
        # シグナル発火の最低確率閾値
        self.min_confidence = 0.6

    def _load_model(self) -> bool:
        """ONNXモデルをロードする。"""
        if self._model_loaded:
            return True
        try:
            import onnxruntime as ort

            model_dir = Path(self.config.get("model.onnx.output_dir", "models/saved"))
            onnx_files = list(model_dir.glob("*.onnx"))
            if not onnx_files:
                logger.warning(f"ONNXモデルが見つかりません: {model_dir}")
                return False

            # 最新のモデルを使用
            latest = max(onnx_files, key=lambda f: f.stat().st_mtime)
            self._onnx_session = ort.InferenceSession(str(latest))
            self._model_loaded = True
            logger.info(f"ONNXモデルロード: {latest.name}")
            return True
        except Exception as e:
            logger.error(f"モデルロードエラー: {e}")
            return False

    def generate(self, features: np.ndarray) -> TradeSignal:
        """
        特徴量からトレードシグナルを生成する。

        Args:
            features: 特徴量配列 (1, n_indicators, lookback_days)

        Returns:
            TradeSignal
        """
        if not self._load_model():
            return TradeSignal()

        try:
            # CNN入力形式に変換 (batch, indicators, time, 1)
            input_data = features[..., np.newaxis].astype(np.float32)

            input_name = self._onnx_session.get_inputs()[0].name
            output_name = self._onnx_session.get_outputs()[0].name

            result = self._onnx_session.run(
                [output_name], {input_name: input_data}
            )
            probs = result[0][0]  # [Sell, Hold, Buy]

            # 最大確率のクラスを判定
            max_class = np.argmax(probs)
            max_prob = probs[max_class]

            if max_prob < self.min_confidence:
                return TradeSignal(direction=0, strength=0, probabilities=probs)

            # 0=Sell, 1=Hold, 2=Buy → direction: -1, 0, 1
            direction = max_class - 1

            return TradeSignal(
                direction=direction,
                strength=float(max_prob),
                probabilities=probs,
            )
        except Exception as e:
            logger.error(f"推論エラー: {e}")
            return TradeSignal()
