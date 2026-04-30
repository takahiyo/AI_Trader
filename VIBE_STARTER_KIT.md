# AI Vibe Coding 汎用スターターキット・マスターガイド

## 🤖 AIへの実行指示（Setup Prompt）

あなたはこれから新しいプロジェクトの初期セットアップを行います。
本ドキュメントは、「AIによるVibe Coding」を安全かつ継続的に行うための**開発基礎・規約ソース**です。
以下の手順に厳密に従い、プロジェクトルートに基盤ファイルを展開してください。

1. **ディレクトリの作成**:
   - 本ドキュメントの【§2. ディレクトリ構造テンプレート】に従い、必要なディレクトリ（`docs/`, `scripts/`, `webapp/js/constants/`, `webapp/js/modules/`, `webapp/js/services/` など）を作成してください。
2. **ファイルの抽出と生成**:
   - 【§3】〜【§11】の内容を抽出し、指定されたパスにそれぞれ独立したファイルとして出力してください。
   - 例: 【§3】の内容は `docs/CORE_PRINCIPLES.md` として保存する。
   - 例: 【§10】の各種ボイラープレートは、`wrangler.toml`, `schema.sql`, `webapp/js/config.js`, `webapp/js/constants/timing.js` 等として保存する。
   - 出力時は元のコードブロック（```）や見出し構造を正しく再現すること。
3. **作業完了報告**:
   - 展開したファイルのパスと概要をリストにして出力してください。
   - `docs/INDEX.md` を確認し、リンク切れなどの不整合がないか確認してください。

---

## §1. 概要・目的・使い方

### AI Vibe Coding の定義
AI Vibe Codingとは、人間が意図（Vibe）の言語化と設計思想のガードレール構築に集中し、AIが実際のコード実装を担う開発スタイルである。AIが高い推論能力を発揮できるよう、プロジェクトの構造、規約、および「失敗の境界線」をドキュメント化し、AIが迷わず、かつ破壊的変更を行わないための環境を構築する。

### 3つの柱：AIとの共生ルール
1. **SSOT (Single Source of Truth) の徹底**: すべての定数、設定、識別子は「唯一の場所」で定義する。ハードコーディングを「技術的負債」ではなく「AIへの偽情報」と定義し、厳禁とする。
2. **AIに対する防衛線としてのドキュメント規約**: コード内のコメントは「何をしているか」ではなく「なぜそうしているか（意図）」と「何をしてはいけないか（制約）」を記述する。
3. **物理分割と順序維持による非破壊的リファクタリング**: リファクタリングを「論理的整理」ではなく「物理的な移動作業」と定義し、フェーズを分けることでAIによる意図せぬ破壊を最小化する。

---

## §2. ディレクトリ構造テンプレート

AIがプロジェクト全体を「把握可能な構造」として認識するための標準構成。

```text
/
├── CloudflareWorkers_worker.js  # バックエンド（Workers）メインロジック (CF依存時)
├── wrangler.toml               # Cloudflare環境設定 (CF依存時)
├── schema.sql                  # D1/汎用データベーススキーマ定義
├── scripts/                    # AIコンテキスト構築自動化スクリプト
│   ├── build_llm_context.ps1   # LLM向け全ソース統合スクリプト (PS)
│   ├── build_llm_context.mjs   # LLM向け全ソース統合スクリプト (Node)
│   └── LLM_CONTEXT_header.md   # ヘッダーテンプレート
├── docs/                       # 言語化されたガードレール（規約・設計）
│   ├── CORE_PRINCIPLES.md      # 最上位の絶対遵守事項
│   ├── COMMENT_GUIDE.md        # 意図と制約を伝えるためのコメント規約
│   ├── SSOT_GUIDE.md           # 定数管理と自己修復パラメータ
│   ├── MODULE_GUIDE.md         # モジュール化の作法
│   ├── REFACTOR_GUIDE.md       # 非破壊的改修・分割手順書
│   ├── CSS_GUIDE.md            # カスケード崩壊を防ぐCSS管理規則
│   └── INDEX.md                # 各規約へのインデックス
├── webapp/                     # フロントエンド資産 (公開ディレクトリ)
│   ├── index.html              # エントリポイント（読み込み順が重要）
│   ├── styles.css              # メインスタイル（出現順が重要）
│   └── js/
│       ├── main.js             # ブートストラップ・初期化管理
│       ├── config.js           # 環境別・同期自己修復パラメータ上書き
│       ├── constants/          # SSOTを実現する定数集約
│       │   ├── index.js        # バレルファイル（一括エクスポート必須）
│       │   ├── storage.js      # キャッシュキー・ストレージ名
│       │   └── timing.js       # 同期・自己修復定数
│       ├── services/           # 状態を持たない共通ヘルパー（QR, CSV等）
│       └── modules/            # 状態を持つ機能単位（init(config)パターン必須）
```

---

## §3. CORE_PRINCIPLES.md (絶対遵守事項)
**抽出先**: `docs/CORE_PRINCIPLES.md`

```markdown
# AIコーディング基本原則

本ドキュメントは、AIによるコーディング作業において**常に遵守すべき基本原則**を定める。
すべての開発作業の開始時に本ドキュメントを読み込み、作業中も常に意識すること。

---

## 絶対遵守事項

以下の規則は**いかなる場合も違反してはならない**。

### 1. SSOT（Single Source of Truth）の厳守

**あなたは設定値・定数・識別子をコード内に直接記述してはならない。**

- 定数は専用ファイル（`constants/` 等）に集約しなければならない
- 同じ値が2箇所以上に存在してはならない
- 既存の定数定義を確認せずに新しい値を追加してはならない

**違反時の影響**: 値の変更時に修正漏れが発生し、動作不整合やバグの原因となる

### 2. 既存構造の保護

**あなたは既存のモジュール構造・初期化順序・依存関係を破壊してはならない。**

- 新規コードは既存のパターンに従って追加しなければならない
- 依存注入（`init(config)`等）のパターンが存在する場合、それを維持しなければならない
- ファイルの読み込み順序に依存する処理を変更してはならない

**違反時の影響**: 初期化エラー、未定義参照、機能の完全な破壊

### 3. コメントによる意図の明示

**あなたはコメントなしでコードを追加・変更してはならない。**

- 新規関数には目的・引数・戻り値を記述しなければならない
- 複雑なロジックには「なぜそうするのか」を記述しなければならない
- 既存コメントと矛盾する変更を行う場合、コメントも更新しなければならない

**違反時の影響**: 後続の修正で意図が伝わらず、誤った変更が行われる

### 4. 変更前の確認義務

**あなたはコードを変更する前に、その影響範囲を確認しなければならない。**

- 変更対象が他のファイルから参照されているか確認すること
- 関数のシグネチャを変更する場合、すべての呼び出し元を確認すること
- 定数やクラス名を変更する場合、全ファイルを検索すること

**違反時の影響**: 参照切れ、未定義エラー、予期しない動作

---

## 作業開始時の必須手順

新しい作業を開始する前に、以下を必ず実行すること。

### 1. プロジェクト構造の把握

プロジェクトツリーや `LLM_CONTEXT.md` で全体構造と各ファイルの役割を理解する。

### 2. 既存パターンの確認

- 定数管理の方式（`constants/` の構成）
- モジュールの初期化パターン（`init()` の有無）
- コメントの書式（JSDoc、セクション区切り等）

### 3. 禁止事項チェックリスト

作業完了時に以下を確認し、自己検閲すること。

- [ ] マジックナンバー、URL、DOM ID等のハードコーディングをしていないか。
- [ ] 既存の定数を確認せず、同じ値を新規定義していないか。
- [ ] 関数名・変数名に「なぜ」を示すコメント（JSDoc）を付記したか。
- [ ] 既存の初期化順序や読み込み順序を破壊していないか。
- [ ] 変更箇所の影響範囲（呼び出し元など）を全ファイル検索で確認したか。

```

---

## §4. COMMENT_GUIDE.md (コメント規約)
**抽出先**: `docs/COMMENT_GUIDE.md`

```markdown
# コメント・ドキュメント規約

本ドキュメントは、コード内のコメントおよびドキュメントの記述規則を定める。
適切なコメントは、AIによる後続の修正においてコードの破壊を防ぐ最重要の防衛線である。

## 1. コメントの目的
1. **意図の伝達**: 「何をしているか」ではなく「なぜそうするか」
2. **制約の明示**: 変更してはいけない理由を伝える
3. **依存の記録**: 他のコードとの関係を明示（`[REF]` タグ）

## 2. ファイルヘッダー
すべてのソースファイルの先頭に役割と依存を記述する。

```javascript
/**
 * ファイル名.js - 一行での役割説明
 *
 * 詳細な説明（2-3行）
 * このモジュールが担当する責務を記述する。
 *
 * 依存: 外部モジュールへの依存を列挙
 * 参照元: このファイルを使用する側を列挙
 */
```

## 3. 警告・制約コメント
最適化や順序変更を禁止する場合に明示する。

```javascript
// ⚠️ WARNING: この順序を変更してはならない
// 理由: storageの初期化がcloudSyncより先である必要がある
```

## 4. 参照元情報の付記（[REF]タグ）
ファイルの物理分割を安全に行うため、HTML/JS間の依存を記述する。

**CSSの場合**:
```css
/* =====================================
[REF]
- HTML: #viewer 内の img 要素に適用
- JS: reader.js で .zoomed クラスを付与
- STATE: 画像ズーム時のみ有効
- LAYER: z-index: 100
- SPLIT: GROUP（.viewer-container と同一ファイル必須）
===================================== */
```
```

---

## §5. SSOT_GUIDE.md (定数管理)
**抽出先**: `docs/SSOT_GUIDE.md`

```markdown
# SSOT（Single Source of Truth）実践ガイド

本ドキュメントは、コード内の定数・設定値・識別子を一元管理するための実践方法を定める。

## 1. SSOT化の対象
**必須対象（ハードコーディング厳禁）**:
- URL・エンドポイント
- DOM ID・セレクタ (`#viewer`, `.modal`)
- 特殊な設定値・閾値 (APIタイムアウト等)
- 状態を表す文字列 (`"loading"`, `"error"`)
- ストレージのキー名

## 2. 実装パターン
`constants/` フォルダ配下にカテゴリ別ファイルを作成し、`index.js`（バレル）でまとめる。

1. オブジェクト形式の定数は必ず `Object.freeze()` で保護し、実行時の予期せぬ変更を防ぐ。
2. 命名規則：定数は `UPPER_SNAKE_CASE` とする。

```javascript
export const DOM_IDS = Object.freeze({
  VIEWER: "viewer",
  MODAL: "modal"
});
```

## 3. 同期自己修復パラメータ (分散システムの整合性維持)
※以下は参照例（プロジェクトにより適宜設定）
設定値は `config.js` を窓口として管理し、直接ロジックに秒数を書き込まない。

- `DEFAULT_SYNC_REV_RESCUE_WINDOW_MS`: リビジョン救済ウィンドウ（既定値）。
- `DEFAULT_SYNC_CACHE_TTL_MS`: 同期キャッシュ寿命（既定値）。
- `DEFAULT_SYNC_CONFLICT_STREAK_WARN_THRESHOLD`: 競合警告しきい値。
```

---

## §6. MODULE_GUIDE.md (モジュール設計)
**抽出先**: `docs/MODULE_GUIDE.md`

```markdown
# モジュール化・依存注入ガイド

## モジュール化の目的
単一責任の原則に従い、特定の機能だけを持つモジュールを作る。

## 依存注入パターン: `init(config)`
外部モジュールへの依存は、直接 `import` してグローバルに使用するのではなく、`init()` 関数を通じて注入（Dependency Injection）することを基本とする。これによりファイルの独立性が高まり、順序依存やテストの難しさを解消する。

```javascript
// my-module.js
let _storage = null;

export function init(config) {
    _storage = config.storage;
}

export function doWork() {
    if(!_storage) throw new Error("Not initialized");
    _storage.save("data");
}
```

## 循環依存の禁止
AがBを呼び、BがAを呼ぶような状態を避ける。
共通処理を抽出するか、コールバック関数を利用すること。
```

---

## §7. REFACTOR_GUIDE.md (物理分割プロセス)
**抽出先**: `docs/REFACTOR_GUIDE.md`

```markdown
# 分割・リファクタリング安全規則

コード分割は**設計作業ではなく、設計に基づく物理作業（コピー＆ペースト作業）**である。
AIによる「ついでに修正」や「論理の再構築」は予期せぬ挙動破壊を引き起こすため固く禁じる。

## 分割フェーズの厳守

1. **フェーズ1 (参照元調査)**: 編集厳禁。`grep` 等で依存を洗い出す。
2. **フェーズ2 (情報の付記)**: 調査結果を `[REF]` コメント等で記す。
3. **フェーズ3 (計画確定)**: 分割先の構成を決める。
4. **フェーズ4 (物理分割)**: **ロジック変更厳禁**。コピー＆ペーストで移動するのみ。関数名や内部の最適化は行わない。
5. **フェーズ5 (インポート更新)**: 参照元のパスをつなぎ直す。
6. **フェーズ6 (検証)**: 動作確認を行う。

## 絶対禁止事項
分割作業中に以下の「ついで」の作業を行ってはならない。
- リファクタリング（DRY化など）
- 関数名の変更
- フォーマットの変更
```

---

## §8. CSS_GUIDE.md (CSS管理規則)
**抽出先**: `docs/CSS_GUIDE.md`

```markdown
# CSS分割・改修ガイド

CSSは**宣言順・HTML構造・JSによる状態変化**に極めて強く依存する。
不用意な再配置はカスケードを崩壊させる。

## 1. 参照元調査と `[REF]` コメント
各CSSブロックを移動・分割する場合、HTML, JSからの使われ方を調査し必ずコメントを残す。

## 2. 分割時の絶対条件
1. **セレクタを変更してはならない**
2. **プロパティ値を変更・最適化してはならない**
3. **元の出現順序（カスケードの強さ）を維持しなければならない**
4. **`!important` を追加・削除してはならない**

CSS分割とは、文字列を別ファイルに切り出し、最終的な評価順が絶対に変わらないよう `<link>` タグを配置する「物理的移動」である。
```

---

## §9. INDEX.md (ガイドライン索引)
**抽出先**: `docs/INDEX.md`

```markdown
# AIコーディングマニュアル 索引

| ドキュメント | 内容 | 読むタイミング |
|--------------|------|----------------|
| **LLM_CONTEXT.md** | **LLM向け全ソース全文** | 開発開始時 / AIセッション開始時 |
| **[CORE_PRINCIPLES.md](./CORE_PRINCIPLES.md)** | **基本原則（最重要）** | 作業開始時に必ず読む |
| [SSOT_GUIDE.md](./SSOT_GUIDE.md) | 定数管理と自己修復 | 定数を追加/変更するとき |
| [COMMENT_GUIDE.md](./COMMENT_GUIDE.md) | コメント規約と `[REF]` | コードを書くとき |
| [MODULE_GUIDE.md](./MODULE_GUIDE.md) | モジュール設計・DI方式 | 新機能を実装するとき |
| [REFACTOR_GUIDE.md](./REFACTOR_GUIDE.md) | 非破壊的な物理分割 | ファイルを分ける/整理するとき |
| [CSS_GUIDE.md](./CSS_GUIDE.md) | カスケード保護規則 | CSSを修正/分割するとき |
```

---

## §10. ボイラープレート（設定と定数）

本セクションのファイル群は、プロジェクトのインフラや設定基盤となる。

### 10-1. wrangler.toml テンプレート
**抽出先**: `wrangler.toml` (※必要に応じて)
```toml
name = "vibe-starter-project"
main = "CloudflareWorkers_worker.js"
compatibility_date = "2024-01-01"

# [[kv_namespaces]]
# binding = "STATUS_CACHE"
# id = "xxxxxxxxxxxx"

# [[d1_databases]]
# binding = "DB"
# database_name = "vibe_db"
# database_id = "xxxxxxxxxxxx"

[vars]
# 環境変数・定数をここに配置
```

### 10-2. schema.sql 汎用データ構造
**抽出先**: `schema.sql` (※DB利用時)
```sql
-- 1. メタデータ・設定管理
CREATE TABLE IF NOT EXISTS configs (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. テナント・グループ管理
CREATE TABLE IF NOT EXISTS tenant_groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    password_hash TEXT,
    is_public INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. エンティティ管理（JSONで柔軟に拡張可能）
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    group_id TEXT,
    data TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES tenant_groups(id)
);
```

### 10-3. js/config.js (スケルトン)
**抽出先**: `webapp/js/config.js`
```javascript
/**
 * js/config.js - アプリケーション全体の設定
 * 
 * SSOT_GUIDE.md に基づく設定の窓口。
 * ハードコーディングを防ぐため、各種設定値をここで上書き・管理する。
 */
const hostname = window?.location?.hostname || 'localhost';
const isDev = hostname.startsWith('dev.') || hostname.includes('localhost') || hostname === '127.0.0.1';

export const CONFIG = {
    // API・インフラ関連
    remoteEndpoint: isDev ? "http://localhost:8787" : "https://production.api",
    
    // 同期・ポーリング間隔
    pollMs: 30000,
    
    // システム自己修復・キャッシュ制御など（必要に応じて）
    syncSelfHeal: {
        cacheTtlMs: 21600000, // 6時間
        conflictWarnThreshold: 3
    },

    // ストレージキー (SSOT化)
    storageKeys: {
        appState: 'app_state_cache',
        lastSync: 'app_last_sync'
    }
};
```

### 10-4. js/constants/timing.js (定数の一元管理例)
**抽出先**: `webapp/js/constants/timing.js`
```javascript
/**
 * js/constants/timing.js
 * タイミング、タイムアウト、時間に関する定数
 */

// UI表示関連
export const UI_TOAST_DURATION_MS = 3000;
export const DEBOUNCE_WAIT_MS = 300;

// 自動修復関連（config.jsのデフォルト値として参照される）
export const DEFAULT_SYNC_CACHE_TTL_MS = 6 * 60 * 60 * 1000;
export const DEFAULT_SYNC_REV_RESCUE_WINDOW_MS = 3 * 60 * 1000;
export const DEFAULT_SYNC_CONFLICT_STREAK_WARN_THRESHOLD = 3;
```

---

## §11. AIコンテキスト構築自動化スクリプト

常にAIへ最新かつ完全なソースコード（コンテキスト）を渡せるよう、一括結合するスクリプト。

### 11-1. PowerShell版 (Windows環境用)
**抽出先**: `scripts/build_llm_context.ps1`
```powershell
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
Set-Location $root

# 結合するファイルを列挙 (プロジェクトに合わせて適宜変更)
$files = @(
  "webapp/index.html",
  "webapp/styles.css",
  "webapp/js/config.js",
  "webapp/js/main.js",
  "schema.sql",
  "CloudflareWorkers_worker.js"
)

function Get-Lang([string]$f) {
  if ($f.EndsWith(".html")) { return "html" }
  if ($f.EndsWith(".css")) { return "css" }
  if ($f.EndsWith(".sql")) { return "sql" }
  if ($f.EndsWith(".json")) { return "json" }
  return "javascript"
}

$fileListMd = ($files | ForEach-Object { "- ``$_``" }) -join "`n"
$headerPath = Join-Path $root "scripts\LLM_CONTEXT_header.md"
if (-not (Test-Path -LiteralPath $headerPath)) { throw "Header template not found: $headerPath" }

$headerUtf8 = [System.Text.UTF8Encoding]::new($false)
$headerTemplate = [System.IO.File]::ReadAllText($headerPath, $headerUtf8)
$header = $headerTemplate.Replace("{{FILE_LIST}}", $fileListMd)

$sb = New-Object System.Text.StringBuilder
[void]$sb.Append($header)

foreach ($rel in $files) {
  $abs = Join-Path $root $rel
  if (-not (Test-Path -LiteralPath $abs)) { Write-Warning "Skip missing file: $rel"; continue }
  $body = [System.IO.File]::ReadAllText($abs, [System.Text.Encoding]::UTF8).Replace("`r`n", "`n")
  $lang = Get-Lang $rel
  [void]$sb.Append("### $rel`n`n```$lang`n$body`n````n`n")
}

$outPath = Join-Path $root "LLM_CONTEXT.md"
[System.IO.File]::WriteAllText($outPath, $sb.ToString(), [System.Text.UTF8Encoding]::new($false))
Write-Host "Success: Generated LLM_CONTEXT.md"
```

### 11-2. JS版 (Node.js環境用)
**抽出先**: `scripts/build_llm_context.mjs`
```javascript
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");

const files = [
  "webapp/index.html",
  "webapp/styles.css",
  "webapp/js/config.js",
  "webapp/js/main.js",
  "schema.sql",
  "CloudflareWorkers_worker.js"
];

function extLang(f) {
  if (f.endsWith(".html")) return "html";
  if (f.endsWith(".css")) return "css";
  if (f.endsWith(".sql")) return "sql";
  if (f.endsWith(".json")) return "json";
  return "javascript";
}

const fileListMd = files.map((f) => `- \`${f}\``).join("\n");
const headerPath = path.join(__dirname, "LLM_CONTEXT_header.md");
const headerTemplate = fs.readFileSync(headerPath, "utf8");
const header = headerTemplate.replace("{{FILE_LIST}}", fileListMd);

let out = header.replace(/\r\n/g, "\n");
for (const rel of files) {
  const abs = path.join(root, rel);
  if (!fs.existsSync(abs)) { console.warn("Skip missing:", rel); continue; }
  const body = fs.readFileSync(abs, "utf8").replace(/\r\n/g, "\n");
  out += `### ${rel}\n\n\`\`\`${extLang(rel)}\n${body}\n\`\`\`\n\n`;
}

const outPath = path.join(root, "LLM_CONTEXT.md");
fs.writeFileSync(outPath, out, "utf8");
console.log("Success: Generated LLM_CONTEXT.md", fs.statSync(outPath).size, "bytes");
```

### 11-3. ヘッダーテンプレート
**抽出先**: `scripts/LLM_CONTEXT_header.md`
```markdown
# LLM向けプロジェクト・コンテキスト 

本ドキュメントは **NotebookLM・外部LLM** がリポジトリを横断解析するための**単一ソース**です。
前半に要約、後半に**現行アプリの全ソース全文**を含みます。

## 結合に含まれるファイル一覧
{{FILE_LIST}}

## 後半: 全ソースコード
以下、各ファイルは `### 相対パス` の見出しの直後にコードブロックで**全文**を記載する。

---

```

---

## §12. アンチパターン集（地雷リスト）

AIが過去の失敗を繰り返さないための、具体的かつ技術的な地雷リストの例。
プロジェクト固有のトラップが発生した際、随時ここ（または別ファイル）に追記して共有すること。

*   **テーブルレイアウト崩れ (Table Squishing)**:
    *   `table-layout: auto` 環境において、特定の列に `width: 100%` を付与することを 絶対禁止 とする（他カラムが強制圧縮されるため）。
    *   幅を制御したい列には具体的な px または min/max-width を指定し、伸ばしたい列には `width: auto` を適用すること。
*   **!important 競合**:
    *   CSSで `!important` が付与されたクラス（例：`.hidden`）を持つ要素に対し、JSから直接 `style.display = 'block'` 等でインライン操作してはならない。
    *   常に `classList.remove('hidden')` によるクラス制御を優先し、スタイルのSSOTを維持せよ。
*   **プレースホルダ・エラーの放置**:
    *   `YOUR_API_KEY` のようなプレースホルダを検知した際、そのまま実行してエラーを発生させてはならない。起動時に設定不備を検知し、ユーザーに明示的な警告を出す（フェイルセーフ）ガードを実装せよ。
*   **動的UIの実行時エラー (Uncaught TypeError)**:
    *   外部データやDBから取得したオブジェクトのプロパティ（特にネストされた配列）にアクセスする際は、必ずオプショナルチェイニング（`?.`）や `|| []` によるデフォルト値の付与を行い、クラッシュを防ぐこと。
