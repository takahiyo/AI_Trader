"""
AI_Trader データ取得モジュール

HistData.com（ヒストリカル）およびMT5 API（リアルタイム）から
市場データを取得し、統一されたUTCタイムゾーンのDataFrameとして返す。

重要: HistData.comは「EST（米国東部標準時）かつサマータイム調整なし」
という特殊なタイムゾーンを採用している。取得時にUTCへ正規化する。
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# HistData.comのタイムゾーンオフセット: EST固定（UTC-5）、DST適用なし
_HISTDATA_EST_OFFSET = timedelta(hours=-5)

# MT5タイムフレームのマッピング（文字列 → MT5定数）
# MT5モジュールが利用可能な場合にのみ解決する
_MT5_TIMEFRAME_MAP = {
    "1min": "TIMEFRAME_M1",
    "5min": "TIMEFRAME_M5",
    "15min": "TIMEFRAME_M15",
    "30min": "TIMEFRAME_M30",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1",
}


def _resolve_mt5_timeframe(tf_str: str):
    """
    文字列のタイムフレームをMT5の定数に変換する。

    Args:
        tf_str: タイムフレーム文字列（例: "5min", "1h"）

    Returns:
        MT5のタイムフレーム定数
    """
    import MetaTrader5 as mt5

    attr_name = _MT5_TIMEFRAME_MAP.get(tf_str)
    if attr_name is None:
        raise ValueError(f"未対応のタイムフレーム: {tf_str}")
    return getattr(mt5, attr_name)


def convert_histdata_to_utc(df: pd.DataFrame) -> pd.DataFrame:
    """
    HistData.comのEST（DST非対応）タイムスタンプをUTCに変換する。

    HistData.comは年間を通じてEST（UTC-5）固定。
    夏時間の切り替えは適用されないため、単純に5時間加算でUTCに変換できる。

    Args:
        df: HistDataから取得したDataFrame（'time'列がEST_NO_DST）

    Returns:
        'time'列がUTCに変換されたDataFrame
    """
    if "time" not in df.columns:
        logger.warning("'time'列が見つかりません。変換をスキップします。")
        return df

    df = df.copy()
    # EST固定（UTC-5）→ UTC: 5時間加算
    df["time"] = pd.to_datetime(df["time"]) - _HISTDATA_EST_OFFSET
    df["time"] = df["time"].dt.tz_localize("UTC")
    logger.info(
        f"タイムゾーン変換完了: EST_NO_DST → UTC "
        f"({len(df)}行, {df['time'].min()} ~ {df['time'].max()})"
    )
    return df


class DataFetcher:
    """
    市場データ取得クラス。

    ヒストリカルデータ（HistData.com）とリアルタイムデータ（MT5）を
    統一されたフォーマット（UTC、OHLCV DataFrame）で提供する。
    """

    def __init__(self, config):
        """
        Args:
            config: ConfigAccessorインスタンス
        """
        self.config = config
        self.cache_dir = Path(
            config.get("data.histdata.cache_dir", "data/cache")
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._mt5_initialized = False

    # ---------------------------------------------------------------
    # MT5リアルタイムデータ
    # ---------------------------------------------------------------

    def _ensure_mt5_connection(self) -> bool:
        """
        MT5接続が確立されていなければ初期化する。

        Returns:
            接続成功ならTrue
        """
        if self._mt5_initialized:
            return True

        try:
            import MetaTrader5 as mt5

            terminal_path = self.config.get("mt5.terminal_path", "")
            login = self.config.get("mt5.login", "")
            password = self.config.get("mt5.password", "")
            server = self.config.get("mt5.server", "")

            init_kwargs = {}
            if terminal_path:
                init_kwargs["path"] = terminal_path
            if login:
                init_kwargs["login"] = int(login)
            if password:
                init_kwargs["password"] = password
            if server:
                init_kwargs["server"] = server

            if not mt5.initialize(**init_kwargs):
                error = mt5.last_error()
                logger.error(f"MT5初期化失敗: {error}")
                return False

            self._mt5_initialized = True
            logger.info("MT5接続確立")
            return True

        except ImportError:
            logger.error(
                "MetaTrader5モジュールが見つかりません。"
                "pip install MetaTrader5 を実行してください。"
            )
            return False

    def get_realtime_data(
        self,
        symbol: str,
        timeframe: str,
        count: int = 500,
    ) -> Optional[pd.DataFrame]:
        """
        MT5からリアルタイム市場データを取得する。

        Args:
            symbol: 通貨ペア（例: "EURUSD"）
            timeframe: タイムフレーム文字列（例: "5min"）
            count: 取得するバーの数

        Returns:
            OHLCV DataFrame（UTC）。失敗時はNone。
        """
        if not self._ensure_mt5_connection():
            return None

        try:
            import MetaTrader5 as mt5

            mt5_tf = _resolve_mt5_timeframe(timeframe)

            # 現在時刻から過去方向にcount本のバーを取得
            rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)

            if rates is None or len(rates) == 0:
                error = mt5.last_error()
                logger.warning(
                    f"{symbol}/{timeframe}: データ取得失敗 - {error}"
                )
                return None

            df = pd.DataFrame(rates)
            # MT5の'time'列はUNIXタイムスタンプ（UTC）
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df = df.rename(columns={
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "tick_volume": "volume",
            })

            # 標準列のみ保持
            standard_cols = ["time", "open", "high", "low", "close", "volume"]
            available_cols = [c for c in standard_cols if c in df.columns]
            df = df[available_cols].copy()
            df = df.set_index("time").sort_index()

            logger.debug(
                f"{symbol}/{timeframe}: {len(df)}本取得 "
                f"({df.index.min()} ~ {df.index.max()})"
            )
            return df

        except Exception as e:
            logger.error(
                f"{symbol}/{timeframe}: データ取得例外 - {e}",
                exc_info=True,
            )
            return None

    # ---------------------------------------------------------------
    # HistData ヒストリカルデータ
    # ---------------------------------------------------------------

    def load_historical_csv(
        self,
        filepath: str,
        source: str = "histdata",
    ) -> Optional[pd.DataFrame]:
        """
        CSVファイルからヒストリカルデータを読み込む。

        Args:
            filepath: CSVファイルのパス
            source: データソース ("histdata" or "dukascopy")

        Returns:
            OHLCV DataFrame（UTC）。失敗時はNone。
        """
        try:
            filepath = Path(filepath)
            if not filepath.exists():
                logger.error(f"ファイルが見つかりません: {filepath}")
                return None

            # HistData.comのCSV形式に対応
            # 一般的な形式: DateTime, Open, High, Low, Close, Volume
            df = pd.read_csv(
                filepath,
                sep=";",
                header=None,
                names=["time", "open", "high", "low", "close", "volume"],
                parse_dates=["time"],
            )

            # HistDataの場合はタイムゾーン変換
            if source == "histdata":
                df = convert_histdata_to_utc(df)
            else:
                # Dukascopy等：既にUTCと仮定
                df["time"] = pd.to_datetime(df["time"]).dt.tz_localize("UTC")

            df = df.set_index("time").sort_index()

            # 欠損値チェック
            nan_count = df.isnull().sum().sum()
            if nan_count > 0:
                logger.warning(
                    f"{filepath.name}: {nan_count}個の欠損値を検出"
                )
                df = df.dropna()

            logger.info(
                f"ヒストリカルデータ読込: {filepath.name} "
                f"({len(df)}行, {df.index.min()} ~ {df.index.max()})"
            )
            return df

        except Exception as e:
            logger.error(f"CSV読み込みエラー: {e}", exc_info=True)
            return None

    def download_histdata(
        self,
        pair: str = "eurusd",
        year: Optional[int] = None,
    ) -> Optional[Path]:
        """
        histdatacomモジュールを使用してHistData.comからデータをダウンロードする。

        Args:
            pair: 通貨ペア（小文字、例: "eurusd"）
            year: 取得年（Noneの場合は全期間）

        Returns:
            ダウンロードされたファイルのパス。失敗時はNone。
        """
        try:
            from histdatacom import HistDataCom

            output_dir = self.cache_dir / pair
            output_dir.mkdir(parents=True, exist_ok=True)

            hdc = HistDataCom(
                pair=pair,
                start_year=str(year) if year else None,
                output_directory=str(output_dir),
            )
            hdc.download()

            logger.info(f"HistData ダウンロード完了: {pair} → {output_dir}")
            return output_dir

        except ImportError:
            logger.error(
                "histdatacom モジュールが見つかりません。"
                "pip install histdatacom を実行してください。"
            )
            return None
        except Exception as e:
            logger.error(f"HistData ダウンロードエラー: {e}", exc_info=True)
            return None

    def shutdown(self) -> None:
        """MT5接続を解放する。"""
        if self._mt5_initialized:
            try:
                import MetaTrader5 as mt5
                mt5.shutdown()
                self._mt5_initialized = False
                logger.info("MT5接続を解放しました")
            except Exception as e:
                logger.error(f"MT5シャットダウンエラー: {e}")
