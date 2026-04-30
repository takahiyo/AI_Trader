"""
AI_Trader 設定ローダー

settings.yaml を読み込み、環境変数を展開して
アプリケーション全体で使用できる設定オブジェクトを提供する。
SSOT原則に基づき、設定の取得は必ずこのモジュールを経由する。
"""

import os
import re
import yaml
import logging
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# プロジェクトルートディレクトリ
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"


def _expand_env_vars(value: Any) -> Any:
    """
    YAML値内の ${ENV_VAR} 形式の環境変数プレースホルダーを展開する。

    Args:
        value: 展開対象の値（文字列、リスト、辞書、その他）

    Returns:
        環境変数が展開された値
    """
    if isinstance(value, str):
        # ${VAR_NAME} パターンを検出して環境変数で置換
        pattern = re.compile(r'\$\{([^}]+)\}')
        matches = pattern.findall(value)
        for var_name in matches:
            env_val = os.environ.get(var_name, "")
            if not env_val:
                logger.warning(f"環境変数 '{var_name}' が未設定です")
            value = value.replace(f"${{{var_name}}}", env_val)
        return value
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


class ConfigAccessor:
    """
    ドット記法とブラケット記法の両方で設定値にアクセスできるラッパー。

    使用例:
        config = ConfigAccessor(data)
        config.mt5.login
        config["mt5"]["login"]
        config.get("mt5.login", default="")
    """

    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            return super().__getattribute__(key)
        try:
            value = self._data[key]
            if isinstance(value, dict):
                return ConfigAccessor(value)
            return value
        except KeyError:
            raise AttributeError(
                f"設定キー '{key}' が見つかりません"
            )

    def __getitem__(self, key: str) -> Any:
        value = self._data[key]
        if isinstance(value, dict):
            return ConfigAccessor(value)
        return value

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """
        ドット区切りのキーで設定値を取得する。

        Args:
            dotted_key: ドット区切りのキー（例: "mt5.login"）
            default: キーが存在しない場合のデフォルト値

        Returns:
            設定値またはデフォルト値
        """
        keys = dotted_key.split(".")
        current = self._data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current

    def to_dict(self) -> dict:
        """設定を辞書として返す。"""
        return self._data.copy()

    def __repr__(self) -> str:
        return f"ConfigAccessor({list(self._data.keys())})"


def load_config(config_path: Optional[Path] = None) -> ConfigAccessor:
    """
    設定ファイルを読み込み、環境変数を展開した ConfigAccessor を返す。

    .env ファイルが存在する場合は自動的に読み込む。

    Args:
        config_path: 設定ファイルのパス。Noneの場合はデフォルトパスを使用。

    Returns:
        ConfigAccessor: 設定アクセスオブジェクト

    Raises:
        FileNotFoundError: 設定ファイルが存在しない場合
        yaml.YAMLError: YAMLのパースに失敗した場合
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"設定ファイルが見つかりません: {config_path}"
        )

    # .envファイルがあれば読み込む
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            logger.info(f".envファイルを読み込みました: {env_path}")
        except ImportError:
            logger.warning(
                "python-dotenv がインストールされていません。"
                ".envファイルの自動読み込みをスキップします。"
            )

    # YAML読み込み
    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    if raw_config is None:
        raise ValueError(f"設定ファイルが空です: {config_path}")

    # 環境変数の展開
    expanded_config = _expand_env_vars(raw_config)

    logger.info(f"設定ファイルを読み込みました: {config_path}")
    return ConfigAccessor(expanded_config)


# --- シングルトンインスタンス ---
# アプリケーション全体で共有する設定インスタンス
_config_instance: Optional[ConfigAccessor] = None


def get_config(config_path: Optional[Path] = None) -> ConfigAccessor:
    """
    設定のシングルトンインスタンスを取得する。
    初回呼び出し時に設定を読み込み、以降はキャッシュされたインスタンスを返す。

    Args:
        config_path: 初回読み込み時の設定ファイルパス

    Returns:
        ConfigAccessor: 設定アクセスオブジェクト
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = load_config(config_path)
    return _config_instance


def reload_config(config_path: Optional[Path] = None) -> ConfigAccessor:
    """
    設定を再読み込みする。実行中のパラメータ変更に対応。

    Args:
        config_path: 設定ファイルのパス

    Returns:
        ConfigAccessor: 再読み込みされた設定アクセスオブジェクト
    """
    global _config_instance
    _config_instance = load_config(config_path)
    logger.info("設定を再読み込みしました")
    return _config_instance
