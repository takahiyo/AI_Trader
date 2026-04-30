"""
AI_Trader MT5注文執行モジュール

MT5 APIを通じた注文送信、ポジション照会、口座情報取得を行う。
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    """注文結果。"""
    success: bool = False
    ticket: int = 0
    error_message: str = ""
    price: float = 0.0


class MT5Executor:
    """MT5 API経由の注文執行。"""

    def __init__(self, config):
        self.config = config
        self._connected = False

    def connect(self) -> bool:
        """MT5に接続する。"""
        try:
            import MetaTrader5 as mt5

            kwargs = {}
            path = self.config.get("mt5.terminal_path", "")
            if path:
                kwargs["path"] = path
            login = self.config.get("mt5.login", "")
            if login:
                kwargs["login"] = int(login)
            password = self.config.get("mt5.password", "")
            if password:
                kwargs["password"] = password
            server = self.config.get("mt5.server", "")
            if server:
                kwargs["server"] = server

            if not mt5.initialize(**kwargs):
                logger.error(f"MT5接続失敗: {mt5.last_error()}")
                return False

            self._connected = True
            info = mt5.account_info()
            logger.info(
                f"MT5接続成功: "
                f"口座={info.login}, 残高={info.balance}, "
                f"サーバー={info.server}"
            )
            return True
        except ImportError:
            logger.error("MetaTrader5モジュールが見つかりません")
            return False

    def disconnect(self) -> None:
        """MT5接続を解放する。"""
        if self._connected:
            try:
                import MetaTrader5 as mt5
                mt5.shutdown()
                self._connected = False
                logger.info("MT5切断")
            except Exception as e:
                logger.error(f"MT5切断エラー: {e}")

    def send_order(
        self,
        symbol: str,
        order_type: int,
        lot: float,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "AI_Trader",
    ) -> OrderResult:
        """
        成行注文を送信する。

        Args:
            symbol: 通貨ペア
            order_type: 0=Buy, 1=Sell
            lot: ロットサイズ
            sl: ストップロス価格
            tp: テイクプロフィット価格
            comment: 注文コメント

        Returns:
            OrderResult
        """
        if not self._connected:
            return OrderResult(success=False, error_message="MT5未接続")

        try:
            import MetaTrader5 as mt5

            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return OrderResult(success=False, error_message=f"シンボル不明: {symbol}")

            if not symbol_info.visible:
                mt5.symbol_select(symbol, True)

            price = mt5.symbol_info_tick(symbol)
            if price is None:
                return OrderResult(success=False, error_message="価格取得失敗")

            fill_price = price.ask if order_type == 0 else price.bid
            mt5_type = mt5.ORDER_TYPE_BUY if order_type == 0 else mt5.ORDER_TYPE_SELL

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot,
                "type": mt5_type,
                "price": fill_price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 123456,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return OrderResult(
                    success=False,
                    error_message=f"注文失敗: retcode={result.retcode}, comment={result.comment}",
                )

            return OrderResult(
                success=True,
                ticket=result.order,
                price=result.price,
            )
        except Exception as e:
            return OrderResult(success=False, error_message=str(e))

    def close_position(self, ticket: int) -> OrderResult:
        """ポジションをクローズする。"""
        if not self._connected:
            return OrderResult(success=False, error_message="MT5未接続")

        try:
            import MetaTrader5 as mt5

            position = mt5.positions_get(ticket=ticket)
            if not position:
                return OrderResult(success=False, error_message=f"ポジション不明: {ticket}")

            pos = position[0]
            close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(pos.symbol)
            close_price = price.bid if pos.type == 0 else price.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": ticket,
                "price": close_price,
                "deviation": 20,
                "magic": 123456,
                "comment": "AI_Trader_Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return OrderResult(
                    success=False,
                    error_message=f"クローズ失敗: {result.comment}",
                )
            return OrderResult(success=True, ticket=result.order, price=result.price)
        except Exception as e:
            return OrderResult(success=False, error_message=str(e))

    def get_spread(self, symbol: str) -> float:
        """現在のスプレッドを取得する（pips）。"""
        if not self._connected:
            return 999.0
        try:
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                return (tick.ask - tick.bid) / 0.0001
            return 999.0
        except Exception:
            return 999.0

    def get_account_balance(self) -> float:
        """口座残高を取得する。"""
        if not self._connected:
            return 0.0
        try:
            import MetaTrader5 as mt5
            info = mt5.account_info()
            return info.balance if info else 0.0
        except Exception:
            return 0.0

    def get_open_positions(self) -> list:
        """オープンポジション一覧を取得する。"""
        if not self._connected:
            return []
        try:
            import MetaTrader5 as mt5
            positions = mt5.positions_get()
            return list(positions) if positions else []
        except Exception:
            return []
