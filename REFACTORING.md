# リファクタリング計画

このドキュメントは、merhist-python のテスト可能性向上を目的としたリファクタリング計画を記載しています。

## 目的

1. メルカリにアクセスしてページを解析する部分とそれ以外のロジックを分離する
2. メルカリにアクセスせずに行える処理についてユニットテストを作成する
3. Coveralls でカバレッジレポートを公開できるようにする

## 現状分析

### モジュール構成

| ファイル | 行数 | 役割 |
|----------|------|------|
| crawler.py | 774 | Webスクレイピング（Selenium使用） |
| history.py | 291 | Excel生成 |
| config.py | 193 | 設定管理 |
| handle.py | 172 | 状態管理 |
| item.py | 83 | データモデル |
| exceptions.py | 38 | カスタム例外 |
| const.py | 23 | 定数定義 |

### 課題

- `crawler.py` が最大のモジュール（774行）で、以下が混在：
  - Selenium操作（ブラウザ制御、要素取得）
  - ページ解析ロジック（HTML要素からデータ抽出）
  - URL生成・解析（純粋関数）
  - 日付パース（純粋関数）
- Selenium依存が強く、単体テストが困難
- XPath がハードコードされている

## リファクタリング方針

### Phase 1: 既存の純粋ロジックのテスト作成

**リファクタリング不要** - 既存コードを変更せずにテストを作成

対象となる純粋ロジック：

| 関数/クラス | ファイル | 説明 |
|-------------|----------|------|
| `gen_sell_hist_url()` | crawler.py | 販売履歴URLの生成 |
| `gen_item_transaction_url()` | crawler.py | 取引情報URLの生成 |
| `gen_item_description_url()` | crawler.py | 商品説明URLの生成 |
| `parse_date()` | crawler.py | 日付文字列のパース |
| `parse_datetime()` | crawler.py | 日時文字列のパース |
| `set_item_id_from_order_url()` | crawler.py | URLからアイテムIDを抽出 |
| `ItemBase`, `SoldItem`, `BoughtItem` | item.py | データモデル |
| `Config.load()` | config.py | 設定のパース |
| `SHEET_DEF` | history.py | Excel定義 |

作成するテストファイル：

```
tests/
├── conftest.py              # 共通フィクスチャ
└── unit/
    ├── test_url_builder.py  # URL生成関数のテスト
    ├── test_date_parser.py  # 日付解析関数のテスト
    ├── test_item.py         # データモデルのテスト
    ├── test_config.py       # 設定パースのテスト
    └── test_history.py      # Excel定義のテスト
```

### Phase 2: スクレイピング結果のパース処理を分離

**リファクタリング必要** - パース処理を純粋関数に抽出

現在 `fetch_item_description()` などに埋め込まれているデータ抽出ロジックを分離：

```python
# 新規: src/merhist/parsers.py

def parse_price_text(text: str) -> int:
    """価格テキストから数値を抽出

    例: '¥1,234' -> 1234
    """

def parse_info_row(label: str, rows: list[tuple[str, str]]) -> str | None:
    """情報行リストからラベルに対応する値を取得"""

def parse_category_from_breadcrumb(breadcrumb_text: str) -> list[str]:
    """パンくずテキストからカテゴリリストを抽出"""

def parse_commission_rate(rate_text: str) -> int:
    """手数料率テキストから数値を抽出

    例: '10%' -> 10
    """
```

### Phase 3: XPathセレクタの定数化

**リファクタリング必要** - ハードコードされたXPathを定数に集約

```python
# 新規: src/merhist/selectors.py

class MercariSelectors:
    """メルカリページのXPathセレクタ"""

    # ナビゲーション
    NOTIFICATION_BUTTON = '//button[contains(@class, "iconButton") and @aria-label="お知らせ"]'
    NAVIGATION_TOP = '//div[@class="merNavigationTop"]'

    # 商品情報ページ
    INFO_HEADING = '//div[contains(@class, "merHeading") and .//h2[contains(text(), "商品の情報")]]'
    INFO_ROW = './/div[@data-testid="description-cell"]'

    # 販売履歴ページ
    SOLD_ITEM_TABLE = '//div[@data-testid="listing-container"]//table//tbody/tr'
    SOLD_PAGING = '//div[@data-testid="listing-container"]/p'

    # 購入履歴ページ
    BOUGHT_ITEM_LIST = '//ul[@data-testid="purchase-item-list"]'
    LOAD_MORE_BUTTON = '//div[contains(@class, "merIconLoading")]'
```

## 実装スケジュール

| Phase | 内容 | 状態 | リファクタリング |
|-------|------|------|------------------|
| 1 | 既存純粋ロジックのテスト作成 | ✅ 完了 | 不要 |
| 2 | パース関数の分離とテスト | ✅ 完了 | 必要 |
| 3 | XPathセレクタ定数化 | ✅ 完了 | 必要 |

### 実装結果

**Phase 1** (2025-12-28)
- `tests/conftest.py`: 共通フィクスチャ
- `tests/unit/test_url_builder.py`: URL生成・解析テスト
- `tests/unit/test_date_parser.py`: 日付解析テスト
- `tests/unit/test_item.py`: データモデルテスト
- `tests/unit/test_config.py`: 設定パーステスト

**Phase 2** (2025-12-28)
- `src/merhist/parser.py`: パース関数を集約
  - `parse_date()`, `parse_datetime()`
  - `parse_price()`, `parse_rate()`
  - `parse_sold_count()`, `parse_price_with_shipping()`
- `tests/unit/test_parser.py`: パース関数テスト

**Phase 3** (2025-12-28)
- `src/merhist/selectors.py`: XPathセレクタを集約
- `src/merhist/const.py`: URLとページ設定のみに整理

**テスト結果**: 96テスト全てパス、カバレッジ43%

## 期待される成果

- ユニットテストによるコードの品質保証
- Coveralls でのカバレッジレポート公開
- コードの保守性向上（関心の分離）
- 将来のメルカリUI変更への対応が容易に

## 参考

テスト構造は `../amazon-bot/tests` を参考にしています：

- `conftest.py`: 共通フィクスチャ（環境モック、Slackモック等）
- `unit/`: ユニットテスト
- モック戦略: `MagicMock` + `patch` でSelenium操作をモック
