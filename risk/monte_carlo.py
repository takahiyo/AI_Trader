"""
AI_Trader モンテカルロシミュレーション

最大ドローダウンの確率分布を可視化し、
リスク評価の定量的根拠を提供する。
"""

import logging
from pathlib import Path
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class MonteCarloSimulator:
    """モンテカルロシミュレーション。"""

    def __init__(self, config):
        self.config = config
        self.n_simulations = config.get(
            "backtest.monte_carlo.n_simulations", 10000
        )
        self.confidence = config.get(
            "backtest.monte_carlo.confidence_level", 0.99
        )

    def simulate(
        self,
        trade_results: List[float],
        initial_balance: float = 10000.0,
        n_trades: int = 500,
    ) -> Dict:
        """
        過去の取引結果をシャッフルして複数の資産曲線を生成する。

        Args:
            trade_results: 過去の各取引のPnL（ドル）
            initial_balance: 初期資金
            n_trades: シミュレーションするトレード数

        Returns:
            {"max_drawdowns": [...], "final_balances": [...], ...}
        """
        if not trade_results:
            logger.warning("取引結果が空のため、シミュレーション不可")
            return {}

        results = np.array(trade_results)
        max_drawdowns = []
        final_balances = []
        ruin_count = 0

        for _ in range(self.n_simulations):
            # 取引結果をランダムに並べ替え
            shuffled = np.random.choice(results, size=n_trades, replace=True)
            equity = np.cumsum(shuffled) + initial_balance
            equity = np.insert(equity, 0, initial_balance)

            # 最大ドローダウン
            peak = np.maximum.accumulate(equity)
            dd = (peak - equity) / peak
            max_dd = np.max(dd)
            max_drawdowns.append(max_dd)

            # 最終残高
            final_balances.append(equity[-1])

            # 破産チェック
            if np.min(equity) <= 0:
                ruin_count += 1

        # 統計
        dd_array = np.array(max_drawdowns)
        bal_array = np.array(final_balances)
        confidence_dd = np.percentile(dd_array, self.confidence * 100)

        result = {
            "max_drawdowns": max_drawdowns,
            "final_balances": final_balances,
            "mean_max_dd": float(np.mean(dd_array)),
            "worst_dd": float(np.max(dd_array)),
            "confidence_dd": float(confidence_dd),
            "ruin_probability": ruin_count / self.n_simulations,
            "mean_final_balance": float(np.mean(bal_array)),
            "median_final_balance": float(np.median(bal_array)),
        }

        logger.info(
            f"モンテカルロ完了({self.n_simulations}回): "
            f"平均最大DD={result['mean_max_dd']:.1%}, "
            f"{self.confidence:.0%}信頼区間DD={result['confidence_dd']:.1%}, "
            f"破産確率={result['ruin_probability']:.2%}"
        )
        return result

    def plot_results(self, results: Dict, output_path: str = "logs/monte_carlo.png") -> None:
        """結果をプロットして保存する。"""
        try:
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(1, 2, figsize=(14, 5))

            # 最大ドローダウン分布
            axes[0].hist(results["max_drawdowns"], bins=50, alpha=0.7, color="steelblue")
            axes[0].axvline(results["confidence_dd"], color="red", linestyle="--",
                           label=f'{self.confidence:.0%} 信頼区間')
            axes[0].set_title("最大ドローダウン分布")
            axes[0].set_xlabel("最大DD (%)")
            axes[0].legend()

            # 最終残高分布
            axes[1].hist(results["final_balances"], bins=50, alpha=0.7, color="seagreen")
            axes[1].axvline(results["mean_final_balance"], color="red", linestyle="--",
                           label=f'平均: {results["mean_final_balance"]:.0f}')
            axes[1].set_title("最終残高分布")
            axes[1].set_xlabel("残高")
            axes[1].legend()

            plt.tight_layout()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=150)
            plt.close()
            logger.info(f"モンテカルロプロット保存: {output_path}")
        except ImportError:
            logger.warning("matplotlibがインストールされていません")
