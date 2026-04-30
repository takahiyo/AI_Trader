"""
AI_Trader 注文管理モジュール

オープンポジションの管理、最大同時ポジション数の制御、
トレーリングストップ等の動的管理を行う。
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OrderRequest:
    """注文リクエスト結果。"""
    success: bool = False
    error_message: str = ""


class OrderManager:
    """ポジション管理。"""

    def __init__(self, config, mt5_executor):
        self.config = config
        self.executor = mt5_executor
        self.max_open = config.get("risk.max_open_positions", 3)

    def place_order(
        self,
        symbol: str,
        direction: int,
        lot_size: float,
        sl_distance: float,
        tp_distance: float,
        signal_strength: float = 0.0,
    ) -> OrderRequest:
        """
        新規注文を発行する。

        Args:
            symbol: 通貨ペア
            direction: 1=Buy, -1=Sell
            lot_size: ロットサイズ
            sl_distance: SL距離（pips）
            tp_distance: TP距離（pips）
            signal_strength: シグナル強度

        Returns:
            OrderRequest
        """
        # 最大ポジション数チェック
        open_positions = self.executor.get_open_positions()
        if len(open_positions) >= self.max_open:
            return OrderRequest(
                success=False,
                error_message=f"最大ポジション数({self.max_open})に到達",
            )

        # 同一シンボルの既存ポジションチェック
        for pos in open_positions:
            if pos.symbol == symbol:
                return OrderRequest(
                    success=False,
                    error_message=f"{symbol}: 既存ポジションあり",
                )

        # 現在の価格を取得してSL/TP価格を計算
        pip = 0.0001
        order_type = 0 if direction == 1 else 1

        try:
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return OrderRequest(success=False, error_message="価格取得失敗")

            price = tick.ask if direction == 1 else tick.bid

            if direction == 1:
                sl_price = price - sl_distance * pip
                tp_price = price + tp_distance * pip
            else:
                sl_price = price + sl_distance * pip
                tp_price = price - tp_distance * pip

        except ImportError:
            return OrderRequest(success=False, error_message="MT5モジュール未インストール")

        result = self.executor.send_order(
            symbol=symbol,
            order_type=order_type,
            lot=lot_size,
            sl=sl_price,
            tp=tp_price,
            comment=f"AI_s{signal_strength:.2f}",
        )

        return OrderRequest(
            success=result.success,
            error_message=result.error_message,
        )

    def manage_open_positions(self) -> None:
        """
        オープンポジションの管理（SL更新等）。
        現時点では基本管理のみ。将来的にトレーリングストップ等を追加。
        """
        positions = self.executor.get_open_positions()
        for pos in positions:
            # ログ出力
            logger.debug(
                f"ポジション: {pos.symbol} "
                f"{'BUY' if pos.type == 0 else 'SELL'} "
                f"lot={pos.volume} profit={pos.profit:.2f}"
            )
