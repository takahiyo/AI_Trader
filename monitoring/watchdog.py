"""
AI_Trader システム監視（ウォッチドッグ）

MT5プロセス生存確認、メモリリーク検知、
独立スレッドでの死活監視を行う。
"""

import logging
import threading
import time

import psutil

logger = logging.getLogger(__name__)


class SystemWatchdog:
    """システム監視デーモン。"""

    def __init__(self, config, notifier):
        self.config = config
        self.notifier = notifier
        self.check_interval = config.get(
            "monitoring.health_check_interval_sec", 30
        )
        self.watch_processes = config.get(
            "monitoring.watch_processes", ["terminal64.exe"]
        )
        self.memory_threshold = config.get(
            "monitoring.memory_threshold_mb", 1500
        )
        self._thread = None
        self._running = False

    def start(self) -> None:
        """監視スレッドを開始する。"""
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="SystemWatchdog",
        )
        self._thread.start()
        logger.info("システム監視スレッド開始")

    def stop(self) -> None:
        """監視スレッドを停止する。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("システム監視スレッド停止")

    def _monitor_loop(self) -> None:
        """監視メインループ。"""
        while self._running:
            try:
                self._check_processes()
                self._check_memory()
            except Exception as e:
                logger.error(f"監視エラー: {e}")
            time.sleep(self.check_interval)

    def _check_processes(self) -> None:
        """監視対象プロセスの生存確認。"""
        for proc_name in self.watch_processes:
            found = False
            for proc in psutil.process_iter(["name"]):
                if proc.info["name"] and proc_name.lower() in proc.info["name"].lower():
                    found = True
                    break
            if not found:
                msg = f"プロセス停止検出: {proc_name}"
                logger.critical(msg)
                self.notifier.send_critical(msg)

    def _check_memory(self) -> None:
        """メモリ使用量チェック。"""
        process = psutil.Process()
        mem_mb = process.memory_info().rss / 1024 / 1024
        if mem_mb > self.memory_threshold:
            msg = f"メモリ使用量警告: {mem_mb:.0f}MB (閾値: {self.memory_threshold}MB)"
            logger.warning(msg)
            self.notifier.send_error(msg)
