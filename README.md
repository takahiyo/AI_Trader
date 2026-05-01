# AI_Trader - AI高頻度FXトレードシステム

ディープラーニング（CNN/LSTM）とマルチタイムフレーム分析を統合した、
薄利多売型の24時間自動売買システム。

## アーキテクチャ

```
Python（分析の脳）→ ONNX推論 → MT5 API（執行の手足）
```

- **データ取得**: HistData.com + MT5 リアルタイムフィード
- **特徴量**: 13テクニカル指標 × 25日 = 325次元マトリクス
- **AIモデル**: CNN（形状認識）+ LSTM（時系列依存） → ONNX変換
- **検証**: CPCV（パージング・エンバーゴ付き）、モンテカルロ1万回
- **リスク**: バルサラ破産確率0%、ATR動的SL/TP
- **監視**: 24時間死活監視、自動復旧、メール/LINE通知

## セットアップ

### 1. Python環境

```bash
# Python 3.10+ をインストール
# https://www.python.org/downloads/

# 依存パッケージのインストール
pip install -r requirements.txt
```

### 2. MT5

- MetaTrader 5 をインストール（ブローカーから提供）
- デモ口座を開設

### 3. 環境変数

```bash
# .env.example を .env にコピー
copy .env.example .env

# .env を編集して以下を設定:
# - MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
# - FRED_API_KEY（https://fred.stlouisfed.org/docs/api/api_key.html）
```

### 4. 実行

```bash
# メインシステム起動
python main.py
```

## ビルド（EXE化）

改修したコードをWindows実行ファイル（EXE）として書き出す場合は、以下のコマンドを実行してください。

```bash
# ビルドスクリプトの実行
build.bat
```

ビルドが完了すると、`dist/AI_Trader.exe` が生成されます。実行時は、EXEと同じディレクトリに `config/` フォルダや `.env` ファイルを配置してください。

## ディレクトリ構造

```
AI_Trader/
├── config/          # 設定管理（SSOT）
├── data/            # データ取得・前処理
├── features/        # テクニカル指標・特徴量
├── models/          # CNN/LSTM・学習・ONNX
├── backtest/        # バックテスト・CPCV・指標
├── strategy/        # シグナル生成・MTFフィルター
├── risk/            # ポジションサイジング・ATR・モンテカルロ
├── execution/       # MT5注文執行
├── monitoring/      # 監視・通知・自動復旧
└── main.py          # エントリポイント
```

## ライセンス

Private - All rights reserved.