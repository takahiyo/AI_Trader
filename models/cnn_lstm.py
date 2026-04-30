"""
AI_Trader CNN-LSTMハイブリッドモデル定義

CNNでチャート波形の「形状」を2次元パターンとして認識し、
LSTMで時系列の長期的依存関係を学習する統合モデル。

入力: (batch, n_indicators, lookback_days, 1)
出力: (batch, 3) → [Sell確率, Hold確率, Buy確率]
"""

import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def build_cnn_lstm_model(
    input_shape: Tuple[int, int],
    config,
) -> "tf.keras.Model":
    """
    CNN-LSTMハイブリッドモデルを構築する。

    アーキテクチャ:
    1. CNN部: Conv2D層で指標マトリクスの空間的パターンを抽出
    2. Reshape: CNN出力を時系列形式に変換
    3. LSTM部: 時系列の依存関係を学習
    4. Dense: 最終分類（Sell/Hold/Buy）

    Args:
        input_shape: (n_indicators, lookback_days) のタプル
        config: ConfigAccessorインスタンス

    Returns:
        コンパイル済みKerasモデル
    """
    import tensorflow as tf
    from tensorflow.keras import layers, regularizers

    n_indicators, lookback_days = input_shape

    # 設定からハイパーパラメータ取得
    cnn_filters = config.get("model.cnn.filters", [32, 64, 128])
    kernel_size = config.get("model.cnn.kernel_size", 3)
    pool_size = config.get("model.cnn.pool_size", 2)
    cnn_dropout = config.get("model.cnn.dropout", 0.3)

    lstm_units = config.get("model.lstm.units", [128, 64])
    lstm_dropout = config.get("model.lstm.dropout", 0.3)
    recurrent_dropout = config.get("model.lstm.recurrent_dropout", 0.2)

    l2_reg = config.get("model.training.l2_regularization", 0.001)
    learning_rate = config.get("model.training.learning_rate", 0.001)

    # --- モデル構築 ---
    inputs = layers.Input(
        shape=(n_indicators, lookback_days, 1),
        name="indicator_matrix",
    )

    # === CNN部: 空間的パターン認識 ===
    x = inputs

    for i, n_filters in enumerate(cnn_filters):
        x = layers.Conv2D(
            filters=n_filters,
            kernel_size=(min(kernel_size, x.shape[1]), kernel_size),
            padding="same",
            activation="relu",
            kernel_regularizer=regularizers.l2(l2_reg),
            name=f"conv2d_{i}",
        )(x)
        x = layers.BatchNormalization(name=f"bn_conv_{i}")(x)

        # プーリングは空間サイズが十分ある場合のみ適用
        if x.shape[1] > pool_size and x.shape[2] > pool_size:
            x = layers.MaxPooling2D(
                pool_size=(1, pool_size),  # 時間方向のみプーリング
                name=f"pool_{i}",
            )(x)

        x = layers.Dropout(cnn_dropout, name=f"drop_conv_{i}")(x)

    # === CNN → LSTM 変換 ===
    # CNN出力: (batch, reduced_indicators, reduced_time, channels)
    # → LSTM入力: (batch, time_steps, features)
    cnn_shape = x.shape
    x = layers.Reshape(
        (cnn_shape[2], cnn_shape[1] * cnn_shape[3]),
        name="reshape_to_lstm",
    )(x)

    # === LSTM部: 時系列依存関係学習 ===
    for i, units in enumerate(lstm_units):
        return_sequences = i < len(lstm_units) - 1  # 最後以外はシーケンス返却
        x = layers.LSTM(
            units=units,
            return_sequences=return_sequences,
            dropout=lstm_dropout,
            recurrent_dropout=recurrent_dropout,
            kernel_regularizer=regularizers.l2(l2_reg),
            name=f"lstm_{i}",
        )(x)
        x = layers.BatchNormalization(name=f"bn_lstm_{i}")(x)

    # === 出力層 ===
    x = layers.Dense(
        32,
        activation="relu",
        kernel_regularizer=regularizers.l2(l2_reg),
        name="dense_pre_output",
    )(x)
    x = layers.Dropout(0.3, name="drop_output")(x)

    # 3クラス分類: Sell(0), Hold(1), Buy(2)
    outputs = layers.Dense(
        3,
        activation="softmax",
        name="output",
    )(x)

    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="CNN_LSTM_Trader")

    # コンパイル
    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    model.compile(
        optimizer=optimizer,
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    model.summary(print_fn=logger.info)
    logger.info(
        f"CNN-LSTMモデル構築完了: "
        f"入力=({n_indicators}, {lookback_days}, 1), "
        f"パラメータ数={model.count_params():,}"
    )

    return model
