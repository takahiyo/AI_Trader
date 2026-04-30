"""
AI_Trader ONNX変換モジュール

学習済みKeras（TensorFlow）モデルをONNXフォーマットに変換し、
MT5のMQL5環境で高速推論を可能にする。

変換手順:
1. Kerasモデルの入力シグネチャを定義
2. tf2onnxで変換
3. ONNX Runtimeでの動作検証
4. 出力パスに保存
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class ONNXConverter:
    """
    Keras → ONNX 変換クラス。
    """

    def __init__(self, config):
        """
        Args:
            config: ConfigAccessorインスタンス
        """
        self.config = config
        self.output_dir = Path(
            config.get("model.onnx.output_dir", "models/saved")
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.opset_version = config.get("model.onnx.opset_version", 13)

    def convert(
        self,
        model,
        input_shape: Tuple[int, ...],
        output_name: str = "cnn_lstm_model",
    ) -> Optional[Path]:
        """
        KerasモデルをONNXフォーマットに変換する。

        Args:
            model: 学習済みKerasモデル
            input_shape: 入力テンソルの形状（バッチ次元除く）
                         例: (n_indicators, lookback_days, 1)
            output_name: 出力ファイル名（拡張子なし）

        Returns:
            保存されたONNXファイルのパス。失敗時はNone。
        """
        try:
            import tensorflow as tf
            import tf2onnx

            output_path = self.output_dir / f"{output_name}.onnx"

            # 入力シグネチャの定義（バッチ次元はNone=可変）
            input_signature = [
                tf.TensorSpec(
                    shape=[None] + list(input_shape),
                    dtype=tf.float32,
                    name="input",
                )
            ]

            # ONNX変換
            logger.info(
                f"ONNX変換開始: opset={self.opset_version}, "
                f"入力形状={input_shape}"
            )
            onnx_model, _ = tf2onnx.convert.from_keras(
                model,
                input_signature=input_signature,
                opset=self.opset_version,
            )

            # 保存
            with open(output_path, "wb") as f:
                f.write(onnx_model.SerializeToString())

            logger.info(f"ONNX変換完了: {output_path}")

            # 動作検証
            if self.verify(output_path, input_shape):
                logger.info("ONNX検証成功: 推論結果が正常です")
            else:
                logger.warning("ONNX検証: 推論結果に問題がある可能性があります")

            return output_path

        except ImportError as e:
            logger.error(
                f"必要なモジュールが見つかりません: {e}\n"
                "pip install tf2onnx onnx onnxruntime を実行してください"
            )
            return None
        except Exception as e:
            logger.error(f"ONNX変換エラー: {e}", exc_info=True)
            return None

    def verify(
        self,
        onnx_path: Path,
        input_shape: Tuple[int, ...],
    ) -> bool:
        """
        変換されたONNXモデルの動作を検証する。

        ランダム入力で推論を実行し、出力形状が期待通りかを確認する。

        Args:
            onnx_path: ONNXファイルのパス
            input_shape: 入力テンソルの形状（バッチ次元除く）

        Returns:
            検証成功ならTrue
        """
        try:
            import onnxruntime as ort

            # ONNX Runtimeセッション作成
            session = ort.InferenceSession(str(onnx_path))

            # 入力・出力情報の確認
            input_info = session.get_inputs()[0]
            output_info = session.get_outputs()[0]

            logger.info(
                f"ONNX入力: name={input_info.name}, "
                f"shape={input_info.shape}, type={input_info.type}"
            )
            logger.info(
                f"ONNX出力: name={output_info.name}, "
                f"shape={output_info.shape}, type={output_info.type}"
            )

            # ランダム入力でテスト推論
            test_input = np.random.randn(1, *input_shape).astype(np.float32)
            result = session.run(
                [output_info.name],
                {input_info.name: test_input},
            )

            output = result[0]
            logger.info(
                f"テスト推論結果: shape={output.shape}, "
                f"値={output[0]}"
            )

            # 出力が3クラスの確率分布になっているか確認
            if output.shape[-1] == 3:
                prob_sum = np.sum(output[0])
                if abs(prob_sum - 1.0) < 0.01:
                    return True
                else:
                    logger.warning(f"確率合計が1.0ではありません: {prob_sum}")
                    return False
            else:
                logger.warning(f"出力クラス数が3ではありません: {output.shape}")
                return False

        except Exception as e:
            logger.error(f"ONNX検証エラー: {e}", exc_info=True)
            return False
