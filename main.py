"""
AI_Trader メインエントリポイント

24時間稼働する高頻度取引システムのメインループ。
「分析の脳（Python）」として、データ取得→推論→シグナル生成→リスク計算→MT5執行
のパイプラインを継続的に実行する。
"""

import sys
import time
import signal
import logging
import threading
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from config.config_loader import get_config
from data.fetcher import DataFetcher
from data.preprocessor import DataPreprocessor
from features.feature_builder import FeatureBuilder
from strategy.signal_generator import SignalGenerator
from strategy.mtf_filter import MTFFilter
from risk.position_sizer import PositionSizer
from risk.atr_exit import ATRExitCalculator
from execution.mt5_executor import MT5Executor
from execution.order_manager import OrderManager
from monitoring.watchdog import SystemWatchdog
from monitoring.notifier import Notifier


def setup_logging(config) -> None:
    """
    ログ設定を初期化する。

    Args:
        config: 設定アクセスオブジェクト
    """
    log_level = getattr(logging, config.get("logging.level", "INFO"))

    # ログディレクトリ作成
    for log_key in ["trade_log", "error_log", "system_log"]:
        log_path = Path(config.get(f"logging.{log_key}", f"logs/{log_key}.log"))
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # ルートロガー設定
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # トレードログ用ハンドラ
    trade_handler = logging.handlers.RotatingFileHandler(
        config.get("logging.trade_log", "logs/trades.log"),
        maxBytes=config.get("logging.rotation.max_bytes", 10485760),
        backupCount=config.get("logging.rotation.backup_count", 5),
        encoding="utf-8",
    )
    trade_handler.setLevel(log_level)
    trade_logger = logging.getLogger("trade")
    trade_logger.addHandler(trade_handler)

    # エラーログ用ハンドラ
    error_handler = logging.handlers.RotatingFileHandler(
        config.get("logging.error_log", "logs/errors.log"),
        maxBytes=config.get("logging.rotation.max_bytes", 10485760),
        backupCount=config.get("logging.rotation.backup_count", 5),
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    logging.getLogger().addHandler(error_handler)


class AITrader:
    """
    AI高頻度取引システムのメインコントローラー。

    データ取得→前処理→特徴量生成→AIモデル推論→MTFフィルター→
    リスク計算→注文執行のパイプラインを管理する。
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = get_config()
        self._running = False
        self._shutdown_event = threading.Event()

        # 各コンポーネントの初期化
        self.logger.info("=== AI_Trader システム初期化開始 ===")

        self.data_fetcher = DataFetcher(self.config)
        self.preprocessor = DataPreprocessor(self.config)
        self.feature_builder = FeatureBuilder(self.config)
        self.signal_generator = SignalGenerator(self.config)
        self.mtf_filter = MTFFilter(self.config)
        self.position_sizer = PositionSizer(self.config)
        self.atr_exit = ATRExitCalculator(self.config)
        self.mt5_executor = MT5Executor(self.config)
        self.order_manager = OrderManager(self.config, self.mt5_executor)
        self.notifier = Notifier(self.config)
        self.watchdog = SystemWatchdog(self.config, self.notifier)

        self.logger.info("=== AI_Trader システム初期化完了 ===")

    def start(self) -> None:
        """システムを起動し、メインループを開始する。"""
        self.logger.info("=== AI_Trader 起動 ===")
        self._running = True

        # シグナルハンドラ登録（Ctrl+C等での安全な終了）
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            # MT5接続確立
            self.mt5_executor.connect()
            self.logger.info("MT5接続確立")

            # 監視スレッド開始
            self.watchdog.start()
            self.logger.info("監視スレッド開始")

            # メインループ
            self._main_loop()

        except Exception as e:
            self.logger.critical(f"致命的エラー: {e}", exc_info=True)
            self.notifier.send_critical(f"AI_Trader 致命的エラー: {e}")
        finally:
            self.stop()

    def _main_loop(self) -> None:
        """
        メイン取引ループ。
        設定されたポーリング間隔で市場データを取得し、
        シグナル生成→リスク評価→注文執行を繰り返す。
        """
        poll_interval = self.config.get("data.realtime.poll_interval_sec", 5)
        symbols = self.config.get("mt5.symbols", ["EURUSD"])

        self.logger.info(
            f"メインループ開始: 対象={symbols}, 間隔={poll_interval}秒"
        )

        while self._running and not self._shutdown_event.is_set():
            cycle_start = time.time()

            try:
                for symbol in symbols:
                    self._process_symbol(symbol)

                # 既存ポジションの管理（ストップロス更新等）
                self.order_manager.manage_open_positions()

            except Exception as e:
                self.logger.error(f"取引サイクルエラー: {e}", exc_info=True)
                self.notifier.send_error(f"取引サイクルエラー: {e}")

            # ポーリング間隔の調整（処理時間を差し引き）
            elapsed = time.time() - cycle_start
            sleep_time = max(0, poll_interval - elapsed)
            self._shutdown_event.wait(timeout=sleep_time)

    def _process_symbol(self, symbol: str) -> None:
        """
        1シンボルに対する取引パイプラインを実行する。

        Args:
            symbol: 取引シンボル（例: "EURUSD"）
        """
        trade_logger = logging.getLogger("trade")

        # 1. データ取得（複数タイムフレーム）
        timeframes = self.config.get("data.timeframes", [])
        market_data = {}
        for tf in timeframes:
            data = self.data_fetcher.get_realtime_data(symbol, tf)
            if data is not None:
                market_data[tf] = data

        if not market_data:
            self.logger.warning(f"{symbol}: データ取得失敗、スキップ")
            return

        # 2. 前処理
        processed_data = {}
        for tf, data in market_data.items():
            processed_data[tf] = self.preprocessor.process(data, tf)

        # 3. 特徴量生成（エントリー用の短期足）
        entry_tf = self.config.get("strategy.entry_timeframe", "5min")
        if entry_tf not in processed_data:
            return

        features = self.feature_builder.build(processed_data[entry_tf])
        if features is None:
            return

        # 4. AIモデル推論・シグナル生成
        signal = self.signal_generator.generate(features)
        if signal.direction == 0:
            return  # シグナルなし

        # 5. MTFフィルター（長期足トレンドとの整合性チェック）
        if not self.mtf_filter.is_aligned(signal, processed_data):
            trade_logger.info(
                f"{symbol}: シグナル={signal.direction} "
                f"MTFフィルターにより却下"
            )
            return

        # 6. スプレッドチェック
        current_spread = self.mt5_executor.get_spread(symbol)
        max_spread = self.config.get("risk.max_spread_pips", 3.0)
        if current_spread > max_spread:
            trade_logger.info(
                f"{symbol}: スプレッド({current_spread})が閾値({max_spread})超過、見送り"
            )
            return

        # 7. リスク計算（ATRベースのSL/TP + ポジションサイジング）
        atr_value = self.atr_exit.calculate_atr(
            processed_data[entry_tf]
        )
        sl_distance, tp_distance = self.atr_exit.calculate_exits(atr_value)

        lot_size = self.position_sizer.calculate(
            symbol=symbol,
            sl_distance_pips=sl_distance,
            account_balance=self.mt5_executor.get_account_balance(),
        )

        if lot_size <= 0:
            trade_logger.info(
                f"{symbol}: 破産確率条件によりロットサイズ0、見送り"
            )
            return

        # 8. 注文執行
        order_result = self.order_manager.place_order(
            symbol=symbol,
            direction=signal.direction,
            lot_size=lot_size,
            sl_distance=sl_distance,
            tp_distance=tp_distance,
            signal_strength=signal.strength,
        )

        if order_result.success:
            trade_logger.info(
                f"{symbol}: 注文成功 "
                f"方向={'BUY' if signal.direction > 0 else 'SELL'} "
                f"ロット={lot_size} SL={sl_distance:.1f}pips "
                f"TP={tp_distance:.1f}pips "
                f"シグナル強度={signal.strength:.3f}"
            )
        else:
            trade_logger.warning(
                f"{symbol}: 注文失敗 - {order_result.error_message}"
            )

    def stop(self) -> None:
        """システムを安全に停止する。"""
        self.logger.info("=== AI_Trader 停止処理開始 ===")
        self._running = False
        self._shutdown_event.set()

        # 監視スレッド停止
        self.watchdog.stop()

        # MT5切断
        self.mt5_executor.disconnect()

        self.logger.info("=== AI_Trader 停止完了 ===")

    def _signal_handler(self, signum, frame) -> None:
        """シグナルハンドラ（安全な終了用）。"""
        self.logger.info(f"シグナル {signum} を受信、停止処理を開始します")
        self.stop()


def main():
    """エントリポイント。"""
    import logging.handlers

    config = get_config()
    setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info(f"AI_Trader v1.0 起動 - {datetime.now().isoformat()}")

    trader = AITrader()
    trader.start()


if __name__ == "__main__":
    main()
