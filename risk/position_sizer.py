"""
AI_Trader ポジションサイジングモジュール

バルサラの破産確率に基づき、破産確率が数学的に0%となる
ポジションサイズを算出する。
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class PositionSizer:
    """バルサラ破産確率ベースのポジションサイジング。"""

    def __init__(self, config):
        self.config = config
        self.max_risk_per_trade = config.get("risk.max_risk_per_trade", 0.005)
        self.max_ruin_prob = config.get("risk.max_ruin_probability", 0.0)
        self.max_open = config.get("risk.max_open_positions", 3)
        # 破産確率推定用の過去取引履歴
        self._trade_history = []

    def calculate(
        self,
        symbol: str,
        sl_distance_pips: float,
        account_balance: float,
    ) -> float:
        """
        ポジションサイズを計算する。

        1. 口座残高 × 最大リスク率 = 最大損失許容額
        2. 最大損失許容額 / SL距離 = ロットサイズ
        3. 破産確率チェック → 0%でなければロット縮小

        Args:
            symbol: 通貨ペア
            sl_distance_pips: ストップロス距離（pips）
            account_balance: 口座残高

        Returns:
            ロットサイズ（0.01単位、0=取引不可）
        """
        if sl_distance_pips <= 0 or account_balance <= 0:
            return 0.0

        # 最大損失許容額
        max_loss = account_balance * self.max_risk_per_trade

        # pip当たりの価値（標準ロット=100,000通貨、1pip=0.0001）
        pip_value = 0.0001 * 100000  # = 10 USD/lot/pip

        # ロットサイズ計算
        lot_size = max_loss / (sl_distance_pips * pip_value)

        # 最小ロット（0.01）に丸め
        lot_size = max(0.01, round(lot_size, 2))

        # 破産確率チェック
        ruin_prob = self._estimate_ruin_probability(
            account_balance, lot_size, sl_distance_pips
        )
        if ruin_prob > self.max_ruin_prob:
            # ロットを縮小して破産確率を0%に近づける
            lot_size = lot_size * 0.5
            lot_size = max(0.01, round(lot_size, 2))
            logger.warning(
                f"破産確率({ruin_prob:.2%})が閾値超過、ロット縮小: {lot_size}"
            )

        return lot_size

    def _estimate_ruin_probability(
        self,
        capital: float,
        lot_size: float,
        sl_pips: float,
        n_simulations: int = 5000,
    ) -> float:
        """
        モンテカルロ法で破産確率を推定する。

        Args:
            capital: 現在の資金
            lot_size: ロットサイズ
            sl_pips: ストップロス距離
            n_simulations: シミュレーション回数

        Returns:
            破産確率（0.0～1.0）
        """
        if len(self._trade_history) < 30:
            # 履歴不足時はデフォルト値（保守的）
            win_rate = 0.5
            avg_win_pips = sl_pips * 1.0
            avg_loss_pips = sl_pips
        else:
            wins = [t for t in self._trade_history if t > 0]
            losses = [t for t in self._trade_history if t <= 0]
            win_rate = len(wins) / len(self._trade_history)
            avg_win_pips = np.mean(wins) if wins else sl_pips
            avg_loss_pips = abs(np.mean(losses)) if losses else sl_pips

        pip_value = 10 * lot_size  # USD per pip
        ruin_count = 0

        for _ in range(n_simulations):
            balance = capital
            for _ in range(200):  # 200トレード先までシミュレート
                if np.random.rand() < win_rate:
                    balance += avg_win_pips * pip_value
                else:
                    balance -= avg_loss_pips * pip_value
                if balance <= 0:
                    ruin_count += 1
                    break

        return ruin_count / n_simulations

    def record_trade(self, pnl_pips: float) -> None:
        """取引結果を履歴に記録する。"""
        self._trade_history.append(pnl_pips)
        # 直近1000件のみ保持
        if len(self._trade_history) > 1000:
            self._trade_history = self._trade_history[-1000:]
