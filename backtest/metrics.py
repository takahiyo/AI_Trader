"""
AI_Trader バックテスト評価指標

PF/PFr、シャープレシオ、最大ドローダウン等の計算。
「なだらかな山の中心」パラメータ選定ロジックを含む。
"""

import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


def calculate_pfr(
    optimized_pf: float,
    n_trades: int,
    n_simulations: int = 1000,
    win_rate: float = 0.5,
) -> float:
    """
    PF/PFr（最適化PF / ランダムPF）を計算する。
    不十分な取引回数の偶然の上振れにペナルティを与える。

    Args:
        optimized_pf: 最適化結果のプロフィットファクター
        n_trades: 取引回数
        n_simulations: ランダムシミュレーション回数
        win_rate: ランダム取引の勝率（0.5=コイントス）

    Returns:
        PF/PFr 比率（>1.0 なら有意）
    """
    random_pfs = []
    for _ in range(n_simulations):
        wins = np.random.binomial(n_trades, win_rate)
        losses = n_trades - wins
        # ランダムなPF（勝ち数/負け数の比率として簡易計算）
        random_pf = (wins + 1) / (losses + 1)
        random_pfs.append(random_pf)

    avg_random_pf = np.mean(random_pfs)
    pfr = optimized_pf / avg_random_pf if avg_random_pf > 0 else 0

    logger.info(
        f"PF/PFr: 最適化PF={optimized_pf:.2f}, "
        f"ランダムPF={avg_random_pf:.2f}, PF/PFr={pfr:.2f}"
    )
    return pfr


def find_robust_parameters(
    param_grid: Dict[str, List],
    results: List[Dict],
    target_metric: str = "profit_factor",
) -> Dict:
    """
    「なだらかな山の中心」を選定する。
    パラメータ微調整時に結果が安定している領域の中心を選ぶ。

    Args:
        param_grid: パラメータグリッド
        results: 各パラメータでのバックテスト結果リスト
        target_metric: 最適化対象の指標

    Returns:
        選定されたパラメータ辞書
    """
    if not results:
        return {}

    metrics = np.array([r.get(target_metric, 0) for r in results])

    # 各結果の近傍平均を計算（周辺安定性）
    neighborhood_scores = np.zeros(len(metrics))
    for i in range(len(metrics)):
        neighbors = metrics[max(0, i-1):min(len(metrics), i+2)]
        neighborhood_scores[i] = np.mean(neighbors) - np.std(neighbors)

    # 近傍スコアが最大の位置が「なだらかな山の中心」
    best_idx = np.argmax(neighborhood_scores)

    logger.info(
        f"ロバストパラメータ選定: idx={best_idx}, "
        f"metric={metrics[best_idx]:.4f}, "
        f"neighborhood_score={neighborhood_scores[best_idx]:.4f}"
    )
    return results[best_idx]
