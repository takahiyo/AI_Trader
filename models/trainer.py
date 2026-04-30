"""
AI_Trader モデル学習パイプライン

CNN-LSTMモデルの学習、チェックポイント保存、
Early Stoppingによるオーバーフィッティング防止を管理する。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class ModelTrainer:
    """
    モデル学習を管理するクラス。

    Early Stopping、学習率スケジューラ、チェックポイント保存を統合。
    """

    def __init__(self, config):
        """
        Args:
            config: ConfigAccessorインスタンス
        """
        self.config = config
        self.model_dir = Path(
            config.get("model.onnx.output_dir", "models/saved")
        )
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # 学習ハイパーパラメータ
        self.epochs = config.get("model.training.epochs", 200)
        self.batch_size = config.get("model.training.batch_size", 64)
        self.validation_split = config.get(
            "model.training.validation_split", 0.2
        )
        self.early_stopping_patience = config.get(
            "model.training.early_stopping_patience", 20
        )

    def train(
        self,
        model,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> Dict:
        """
        モデルを学習する。

        Args:
            model: Kerasモデル
            X_train: 学習データ (n_samples, n_indicators, lookback_days, 1)
            y_train: 学習ラベル (n_samples,)
            X_val: 検証データ（省略時はvalidation_splitで自動分割）
            y_val: 検証ラベル

        Returns:
            学習履歴の辞書 {"loss": [...], "accuracy": [...], ...}
        """
        import tensorflow as tf

        logger.info(
            f"学習開始: データ={X_train.shape}, "
            f"エポック={self.epochs}, バッチ={self.batch_size}"
        )

        # コールバック設定
        callbacks = self._build_callbacks()

        # 検証データ
        validation_data = None
        if X_val is not None and y_val is not None:
            validation_data = (X_val, y_val)
            val_split = 0.0
        else:
            val_split = self.validation_split

        # 学習実行
        history = model.fit(
            X_train,
            y_train,
            epochs=self.epochs,
            batch_size=self.batch_size,
            validation_split=val_split,
            validation_data=validation_data,
            callbacks=callbacks,
            verbose=1,
        )

        # 結果ログ
        final_loss = history.history["loss"][-1]
        final_acc = history.history["accuracy"][-1]
        val_loss = history.history.get("val_loss", [None])[-1]
        val_acc = history.history.get("val_accuracy", [None])[-1]

        logger.info(
            f"学習完了: "
            f"loss={final_loss:.4f}, acc={final_acc:.4f}, "
            f"val_loss={val_loss}, val_acc={val_acc}, "
            f"エポック数={len(history.history['loss'])}"
        )

        # モデル保存
        self._save_model(model)

        return history.history

    def _build_callbacks(self) -> list:
        """学習用コールバックを構築する。"""
        import tensorflow as tf

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        callbacks = []

        # Early Stopping
        callbacks.append(
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss",
                patience=self.early_stopping_patience,
                restore_best_weights=True,
                verbose=1,
            )
        )

        # 学習率スケジューラ（Plateau時に減衰）
        callbacks.append(
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss",
                factor=0.5,
                patience=10,
                min_lr=1e-6,
                verbose=1,
            )
        )

        # チェックポイント保存
        checkpoint_path = self.model_dir / f"checkpoint_{timestamp}.keras"
        callbacks.append(
            tf.keras.callbacks.ModelCheckpoint(
                filepath=str(checkpoint_path),
                monitor="val_loss",
                save_best_only=True,
                verbose=1,
            )
        )

        return callbacks

    def _save_model(self, model) -> Path:
        """学習済みモデルを保存する。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = self.model_dir / f"cnn_lstm_{timestamp}.keras"
        model.save(str(model_path))
        logger.info(f"モデル保存: {model_path}")
        return model_path

    def load_model(self, model_path: str):
        """保存済みモデルを読み込む。"""
        import tensorflow as tf

        model = tf.keras.models.load_model(model_path)
        logger.info(f"モデル読み込み: {model_path}")
        return model
