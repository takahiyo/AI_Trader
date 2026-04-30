"""
AI_Trader 自動復旧モジュール

Windows再起動後のMT5自動起動、スタートアップ登録、
自動ログオン設定を管理する。
"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class AutoRecovery:
    """自動復旧管理。"""

    def __init__(self, config):
        self.config = config
        self.mt5_path = config.get(
            "mt5.terminal_path",
            "C:/Program Files/MetaTrader 5/terminal64.exe"
        )

    def register_startup(self) -> bool:
        """
        Windowsスタートアップにメインスクリプトを登録する。
        再起動後に自動でAI_Traderが起動するようにする。

        Returns:
            成功ならTrue
        """
        try:
            import winreg

            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            python_exe = sys.executable
            script_path = Path(__file__).parent.parent / "main.py"

            command = f'"{python_exe}" "{script_path}"'

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, "AI_Trader", 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)

            logger.info(f"スタートアップ登録完了: {command}")
            return True
        except Exception as e:
            logger.error(f"スタートアップ登録失敗: {e}")
            return False

    def unregister_startup(self) -> bool:
        """スタートアップ登録を解除する。"""
        try:
            import winreg

            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            )
            winreg.DeleteValue(key, "AI_Trader")
            winreg.CloseKey(key)
            logger.info("スタートアップ登録解除")
            return True
        except FileNotFoundError:
            logger.info("スタートアップ登録なし（解除不要）")
            return True
        except Exception as e:
            logger.error(f"スタートアップ解除失敗: {e}")
            return False

    def launch_mt5(self) -> bool:
        """MT5ターミナルを起動する。"""
        try:
            mt5_path = Path(self.mt5_path)
            if not mt5_path.exists():
                logger.error(f"MT5が見つかりません: {mt5_path}")
                return False

            subprocess.Popen([str(mt5_path)], shell=False)
            logger.info(f"MT5起動: {mt5_path}")
            return True
        except Exception as e:
            logger.error(f"MT5起動失敗: {e}")
            return False
