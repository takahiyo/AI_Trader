"""
AI_Trader バックテストエンジン

「次足始値」約定前提のリアリスティックバックテスト。
スプレッド・スリッページを厳格にモデル化し、
バックテストと実運用の乖離を最小化する。
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """1トレードの記録。"""
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp] = None
    symbol: str = ""
    direction: int = 0       # 1=Buy, -1=Sell
    entry_price: float = 0.0
    exit_price: float = 0.0
    lot_size: float = 0.0
    sl_price: float = 0.0
    tp_price: float = 0.0
    pnl: float = 0.0
    pnl_pips: float = 0.0
    spread_cost: float = 0.0
    slippage_cost: float = 0.0
    exit_reason: str = ""    # "tp", "sl", "signal", "end"


@dataclass
class BacktestResult:
    """バックテスト結果の統計。"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade_duration: float = 0.0  # 分
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)


class BacktestEngine:
    """
    バックテストエンジン。

    シグナル配列とOHLCVデータを受け取り、
    リアリスティックなバックテストを実行する。
    """

    def __init__(self, config):
        """
        Args:
            config: ConfigAccessorインスタンス
        """
        self.config = config
        self.spread_pips = config.get("backtest.spread_pips", 1.5)
        self.slippage_pips = config.get("backtest.slippage_pips", 0.5)
        # pip値（EURUSD等のメジャーペアは0.0001）
        self.pip_value = 0.0001

    def run(
        self,
        df: pd.DataFrame,
        signals: np.ndarray,
        sl_distances: np.ndarray,
        tp_distances: np.ndarray,
        lot_sizes: np.ndarray,
        initial_balance: float = 10000.0,
    ) -> BacktestResult:
        """
        バックテストを実行する。

        「次足始値」約定前提:
        - シグナルが発生した足の次の足のOpen価格でエントリー
        - スプレッドとスリッページを約定価格に加算

        Args:
            df: OHLCV DataFrame
            signals: シグナル配列（1=Buy, -1=Sell, 0=NoTrade）
            sl_distances: ストップロス距離（pips）
            tp_distances: テイクプロフィット距離（pips）
            lot_sizes: ロットサイズ配列
            initial_balance: 初期資金

        Returns:
            BacktestResult
        """
        balance = initial_balance
        equity_curve = [balance]
        trades: List[Trade] = []
        open_trade: Optional[Trade] = None

        for i in range(len(signals) - 1):
            current_time = df.index[i]
            next_bar = df.iloc[i + 1]

            # --- オープンポジションの管理 ---
            if open_trade is not None:
                # SL/TPチェック（次足のHigh/Lowで判定）
                closed = self._check_exit(open_trade, next_bar)
                if closed:
                    open_trade.exit_time = df.index[i + 1]
                    balance += open_trade.pnl
                    equity_curve.append(balance)
                    trades.append(open_trade)
                    open_trade = None
                    continue

            # --- 新規エントリー ---
            if signals[i] != 0 and open_trade is None:
                # 次足の始値でエントリー
                entry_price = next_bar["open"]
                direction = int(signals[i])
                sl_dist = sl_distances[i] * self.pip_value
                tp_dist = tp_distances[i] * self.pip_value

                # スプレッド・スリッページコスト
                spread_cost = self.spread_pips * self.pip_value
                slippage_cost = self.slippage_pips * self.pip_value
                total_cost = spread_cost + slippage_cost

                # コストを約定価格に反映
                if direction == 1:  # Buy
                    adjusted_entry = entry_price + total_cost / 2
                    sl_price = adjusted_entry - sl_dist
                    tp_price = adjusted_entry + tp_dist
                else:  # Sell
                    adjusted_entry = entry_price - total_cost / 2
                    sl_price = adjusted_entry + sl_dist
                    tp_price = adjusted_entry - tp_dist

                open_trade = Trade(
                    entry_time=df.index[i + 1],
                    symbol="",
                    direction=direction,
                    entry_price=adjusted_entry,
                    lot_size=lot_sizes[i],
                    sl_price=sl_price,
                    tp_price=tp_price,
                    spread_cost=spread_cost * lot_sizes[i] * 100000,
                    slippage_cost=slippage_cost * lot_sizes[i] * 100000,
                )

        # 残存ポジションのクローズ
        if open_trade is not None:
            last_bar = df.iloc[-1]
            open_trade.exit_price = last_bar["close"]
            open_trade.exit_time = df.index[-1]
            open_trade.pnl = self._calculate_pnl(open_trade)
            open_trade.exit_reason = "end"
            balance += open_trade.pnl
            equity_curve.append(balance)
            trades.append(open_trade)

        return self._compute_statistics(trades, equity_curve, initial_balance)

    def _check_exit(self, trade: Trade, bar: pd.Series) -> bool:
        """
        SL/TPによるエグジットをチェックする。

        Args:
            trade: オープン中のトレード
            bar: 現在のバー（OHLCV）

        Returns:
            エグジットが発生したらTrue
        """
        if trade.direction == 1:  # Buy
            # SLチェック（安値がSL以下）
            if bar["low"] <= trade.sl_price:
                trade.exit_price = trade.sl_price
                trade.exit_reason = "sl"
                trade.pnl = self._calculate_pnl(trade)
                return True
            # TPチェック（高値がTP以上）
            if bar["high"] >= trade.tp_price:
                trade.exit_price = trade.tp_price
                trade.exit_reason = "tp"
                trade.pnl = self._calculate_pnl(trade)
                return True
        else:  # Sell
            # SLチェック（高値がSL以上）
            if bar["high"] >= trade.sl_price:
                trade.exit_price = trade.sl_price
                trade.exit_reason = "sl"
                trade.pnl = self._calculate_pnl(trade)
                return True
            # TPチェック（安値がTP以下）
            if bar["low"] <= trade.tp_price:
                trade.exit_price = trade.tp_price
                trade.exit_reason = "tp"
                trade.pnl = self._calculate_pnl(trade)
                return True

        return False

    def _calculate_pnl(self, trade: Trade) -> float:
        """トレードのPnLを計算する（ロット考慮）。"""
        if trade.direction == 1:
            pips = (trade.exit_price - trade.entry_price) / self.pip_value
        else:
            pips = (trade.entry_price - trade.exit_price) / self.pip_value

        trade.pnl_pips = pips
        # 標準ロット（100,000通貨単位）× pip値
        pnl = pips * self.pip_value * trade.lot_size * 100000
        return pnl

    def _compute_statistics(
        self,
        trades: List[Trade],
        equity_curve: List[float],
        initial_balance: float,
    ) -> BacktestResult:
        """バックテスト統計を計算する。"""
        result = BacktestResult()
        result.trades = trades
        result.equity_curve = equity_curve
        result.total_trades = len(trades)

        if not trades:
            return result

        pnls = [t.pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.win_rate = len(wins) / len(trades) if trades else 0
        result.total_pnl = sum(pnls)
        result.avg_win = np.mean(wins) if wins else 0
        result.avg_loss = np.mean(losses) if losses else 0

        # プロフィットファクター
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1e-10
        result.profit_factor = gross_profit / gross_loss

        # 最大ドローダウン
        equity = np.array(equity_curve)
        peak = np.maximum.accumulate(equity)
        drawdown = peak - equity
        result.max_drawdown = np.max(drawdown)
        result.max_drawdown_pct = (
            result.max_drawdown / initial_balance if initial_balance > 0 else 0
        )

        # シャープレシオ（年率換算）
        if len(pnls) > 1:
            returns = np.array(pnls) / initial_balance
            result.sharpe_ratio = (
                np.mean(returns) / np.std(returns) * np.sqrt(252)
                if np.std(returns) > 0 else 0
            )

        logger.info(
            f"バックテスト完了: "
            f"取引数={result.total_trades}, "
            f"勝率={result.win_rate:.1%}, "
            f"PF={result.profit_factor:.2f}, "
            f"PnL={result.total_pnl:.2f}, "
            f"最大DD={result.max_drawdown_pct:.1%}, "
            f"シャープ={result.sharpe_ratio:.2f}"
        )
        return result
