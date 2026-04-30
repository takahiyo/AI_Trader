"""
AI_Trader CPCV（組合せパージング交差検証）

パージング・エンバーゴ付き交差検証で、
複数経路からシャープレシオ分布を算出する。
"""

import logging
from itertools import combinations
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CPCV:
    """組合せパージング交差検証。"""

    def __init__(self, config):
        self.n_splits = config.get("backtest.cpcv.n_splits", 10)
        self.n_test_splits = config.get("backtest.cpcv.n_test_splits", 2)
        self.embargo_days = config.get("backtest.cpcv.embargo_days", 30)
        self.purge_days = config.get("backtest.cpcv.purge_days", 5)

    def generate_splits(self, n_samples: int) -> List[Tuple[np.ndarray, np.ndarray]]:
        """CPCVの訓練-テスト分割を生成する。"""
        group_size = n_samples // self.n_splits
        groups = []
        for i in range(self.n_splits):
            start = i * group_size
            end = start + group_size if i < self.n_splits - 1 else n_samples
            groups.append(np.arange(start, end))

        test_combos = list(combinations(range(self.n_splits), self.n_test_splits))
        splits = []

        for test_gids in test_combos:
            test_idx = np.sort(np.concatenate([groups[i] for i in test_gids]))
            train_gids = [i for i in range(self.n_splits) if i not in test_gids]
            train_idx = np.sort(np.concatenate([groups[i] for i in train_gids]))

            # パージング: テスト境界付近の訓練データ除去
            test_start, test_end = test_idx.min(), test_idx.max()
            purge = set(range(max(0, test_start - self.purge_days), test_start))
            purge.update(range(test_end + 1, min(n_samples, test_end + self.purge_days + 1)))
            train_idx = np.array([i for i in train_idx if i not in purge])

            # エンバーゴ: テスト直後のデータ除去
            embargo = set(range(test_end + 1, min(n_samples, test_end + self.embargo_days + 1)))
            train_idx = np.array([i for i in train_idx if i not in embargo])

            splits.append((train_idx, test_idx))

        logger.info(f"CPCV分割生成: {len(splits)}組")
        return splits
