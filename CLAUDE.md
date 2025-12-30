# CLAUDE.md - プロジェクトガイドライン

このファイルは Claude Code がこのリポジトリで作業する際のガイドラインです。

## プロジェクト概要

**merhist-python** は、メルカリの販売履歴と購入履歴を自動収集し、サムネイル付き Excel ファイルとして出力する Python ツールです。

### 主な機能

- 販売履歴・購入履歴の自動収集（Selenium によるブラウザ自動化）
- LINE 認証を経由した安全なログイン処理
- 商品画像のサムネイル付き Excel 出力（openpyxl）
- 増分更新対応（中断しても途中から再開可能）
- Slack 連携による認証コードのやり取り
- クロスプラットフォーム対応（Linux / Windows）

## ディレクトリ構成

```
src/
├── app.py                  # エントリーポイント（CLI）
└── merhist/
    ├── config.py           # 設定管理（dataclass ベース）
    ├── const.py            # 定数定義（URL、XPath 等）
    ├── crawler.py          # Web スクレイピング（Selenium）
    ├── exceptions.py       # カスタム例外
    ├── handle.py           # 状態管理（Handle クラス）
    ├── history.py          # Excel 生成ロジック
    ├── item.py             # データモデル（SoldItem, BoughtItem）
    └── py.typed            # PEP 561 型チェック対応マーカー

tests/
└── test_typecheck.py       # mypy 型チェックテスト

schema/
└── config.schema           # 設定値の JSON Schema

config.yaml                 # 設定ファイル（要作成）
config.example.yaml         # 設定ファイルのサンプル
```

## 開発コマンド

### 依存関係のインストール

```bash
uv sync
```

### アプリケーション実行

```bash
uv run python src/app.py              # 通常実行
uv run python src/app.py -e           # Excel 出力のみ
uv run python src/app.py --fA         # 全データ強制再収集
uv run python src/app.py --fB         # 購入履歴のみ強制再収集
uv run python src/app.py --fS         # 販売履歴のみ強制再収集
uv run python src/app.py -N           # サムネイルなし
uv run python src/app.py -D           # デバッグモード
```

### テスト実行

```bash
uv run pytest                         # テスト実行（4並列、E2E除外）
uv run pytest tests/e2e/              # E2E テスト（外部サーバー必要）
```

### 型チェック

```bash
uv run mypy src/merhist/              # mypy による型チェック
uv run pyright                        # pyright による型チェック
```

### リント・フォーマット

```bash
uv run ruff check src/                # リントチェック
uv run ruff format src/               # フォーマット
```

## コーディング規約

### Python バージョン

- Python 3.11 以上（推奨: 3.12）

### スタイル

- 最大行長: 110 文字（ruff 設定）
- ruff lint ルール: E, F, W, I, B, UP
- dataclass を積極的に使用（frozen dataclass 推奨）
- 型ヒントを必ず記述

### 型チェック

- mypy と pyright の両方でチェック
- `src/merhist/py.typed` により PEP 561 準拠

### 例外処理

- `merhist.exceptions` の例外クラスを使用
- 基底クラス: `MerhisError`
- ページ関連: `PageError`, `PageLoadError`, `InvalidURLFormatError`, `InvalidPageFormatError`
- 履歴取得: `HistoryFetchError`

## アーキテクチャ

### 実行フロー

```
app.py (エントリー)
    ↓
Config.load() で設定読み込み
    ↓
Handle インスタンス生成（キャッシュ復元）
    ↓
[非 export モード時]
    crawler.execute_login() → LINE 認証
    crawler.fetch_order_item_list() → 履歴収集
    ↓
history.generate_table_excel() → Excel 生成
    ↓
完了
```

### 主要クラス

- **Config** (`config.py`): 設定を保持する frozen dataclass
- **Handle** (`handle.py`): アプリケーション状態を管理（Selenium、取引情報、プログレスバー）
- **SoldItem / BoughtItem** (`item.py`): 取引データモデル
- **TradingInfo** (`handle.py`): 取引履歴情報を保持

### 外部依存

- **selenium / undetected-chromedriver**: ブラウザ自動化
- **openpyxl**: Excel 生成
- **pillow**: 画像処理
- **enlighten**: プログレスバー表示
- **my-lib**: 作者の共通ライブラリ（git 経由でインストール）

## 重要な注意事項

### プロジェクト設定ファイルの編集禁止

`pyproject.toml` をはじめとする一般的なプロジェクト管理ファイルは、`../py-project` で一元管理しています。

- **直接編集しないでください**
- 修正が必要な場合は `../py-project` を使って更新してください
- 変更を行う前に、何を変更したいのかを説明し、確認を取ってください

対象ファイル例:
- `pyproject.toml`
- `.pre-commit-config.yaml`
- `.gitlab-ci.yml`
- その他の共通設定ファイル

### ドキュメント更新の検討

コードを更新した際は、以下のドキュメントを更新する必要がないか検討してください：

- `README.md`: ユーザー向けの使用方法、機能説明
- `CLAUDE.md`: 開発ガイドライン、アーキテクチャ説明

特に以下の変更時は更新を検討：
- 新しいコマンドラインオプションの追加
- 新機能の追加
- アーキテクチャの変更
- 依存関係の大きな変更

### セキュリティ考慮事項

- `config.yaml` には LINE のログイン情報が含まれるため、リポジトリにコミットしないこと
- `.gitignore` で `config.yaml` が除外されていることを確認
- 認証情報やトークンをコードにハードコードしない

## テスト

### テスト構成

- `tests/test_typecheck.py`: mypy による静的型チェック
- E2E テストは `tests/e2e/` に配置（デフォルトで除外）

### テスト設定

- タイムアウト: 300 秒
- 並列実行: 4 プロセス
- カバレッジレポート: `reports/coverage/`
- HTML レポート: `reports/pytest.html`

## コードパターン

### インポートスタイル

`from xxx import yyy` は基本的に使用せず、`import xxx` としてモジュールをインポートし、参照時は `xxx.yyy` と完全修飾名で記述する：

```python
# 推奨
import my_lib.selenium_util

driver = my_lib.selenium_util.create_driver(...)

# 非推奨
from my_lib.selenium_util import create_driver

driver = create_driver(...)
```

これにより、関数やクラスがどのモジュールに属しているかが明確になり、コードの可読性と保守性が向上する。

### 型アノテーションと型情報のないライブラリ

型情報を持たないライブラリを使用する場合、大量の `# type: ignore[union-attr]` を記載する代わりに、変数に `Any` 型を明示的に指定する：

```python
from typing import Any

# 推奨: Any 型を明示して type: ignore を不要にする
result: Any = some_untyped_lib.call()
result.method1()
result.method2()

# 非推奨: 大量の type: ignore コメント
result = some_untyped_lib.call()  # type: ignore[union-attr]
result.method1()  # type: ignore[union-attr]
result.method2()  # type: ignore[union-attr]
```

これにより、コードの可読性を維持しつつ型チェッカーのエラーを抑制できる。

### pyright エラーへの対処方針

pyright のエラー対策として、各行に `# type: ignore` コメントを記載して回避するのは**最後の手段**とする。

**優先順位：**
1. **型推論できるようにコードを修正する** - 変数の初期化時に型が明確になるようにする
2. **型アノテーションを追加する** - 関数の引数や戻り値、変数に適切な型を指定する
3. **Any 型を使用する** - 型情報のないライブラリの場合（上記セクション参照）
4. **`# type: ignore` コメント** - 上記で解決できない場合の最終手段

```python
# 推奨: 型推論可能なコード
items: list[str] = []
items.append("value")

# 非推奨: type: ignore の多用
items = []  # type: ignore[var-annotated]
items.append("value")  # type: ignore[union-attr]
```

**例外：** テストコードでは、モックやフィクスチャの都合上 `# type: ignore` の使用を許容する。

## ライセンス

Apache License Version 2.0
