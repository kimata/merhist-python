#!/usr/bin/env python3
"""
XPath セレクタ定義

メルカリのページ要素を特定するための XPath セレクタを集約します。
UI変更時はこのファイルのみを修正すれば対応できます。
"""
from __future__ import annotations

# =============================================================================
# 共通セレクタ
# =============================================================================

# ナビゲーション・ローディング
NAVIGATION_TOP = '//div[@class="merNavigationTop"]'
NOTIFICATION_BUTTON = '//button[contains(@class, "iconButton") and @aria-label="お知らせ"]'
LOADING_ICON = '//div[contains(@class, "merIconLoading")]'

# =============================================================================
# 商品説明ページ
# =============================================================================

ITEM_DESC_INFO_ROW = (
    '//div[contains(@class, "merHeading") and .//h2[contains(text(), "商品の情報")]]'
    '/following-sibling::div//div[contains(@class, "merDisplayRow")]'
)
ITEM_DESC_ROW_TITLE = '//div[contains(@class, "title")]'
ITEM_DESC_ROW_BODY = '//div[contains(@class, "body")]'
ITEM_DESC_ROW_BODY_LINKS = '//div[contains(@class, "body")]//a'
ITEM_DESC_NOT_FOUND = '//div[contains(@class, "merEmptyState")]//p[contains(text(), "見つかりません")]'
ITEM_DESC_DELETED = '//div[contains(@class, "merEmptyState")]//p[contains(text(), "削除されました")]'

# =============================================================================
# 取引ページ（通常メルカリ）
# =============================================================================

TRANSACTION_INFO_ROW = (
    '//div[contains(@data-testid, "transaction:information-for-")]'
    '//div[contains(@class, "merDisplayRow")]'
)
TRANSACTION_ROW_TITLE = '//div[contains(@class, "title__")]/span'
TRANSACTION_ROW_BODY = '//div[contains(@class, "body__")]'
TRANSACTION_ROW_BODY_SPAN = '//div[contains(@class, "body__")]/span'
TRANSACTION_ROW_NUMBER = './/span[contains(@class, "number__")]'
TRANSACTION_PAGE_ERROR = '//div[contains(@class, "merEmptyState")]//p[contains(text(), "ページの読み込みに失敗")]'
TRANSACTION_THUMBNAIL = '//img[contains(@alt, "サムネイル")]'

# =============================================================================
# 取引ページ（メルカリShops）
# =============================================================================

SHOP_TRANSACTION_INFO = (
    '//h2[contains(@class, "chakra-heading") and contains(text(), "取引情報")]/following-sibling::ul'
)
SHOP_TRANSACTION_PRICE = '//p[@data-testid="select-payment-method"]/ancestor::li[1]//p[contains(text(),"￥")]'
SHOP_TRANSACTION_THUMBNAIL = '//img[@alt="shop-image"]'
SHOP_TRANSACTION_PHOTO_NAME = '//div[@data-testid="photo-name"]'

# =============================================================================
# 販売履歴ページ
# =============================================================================

SOLD_LIST_ITEM = '//div[@data-testid="listing-container"]//table//tbody/tr'
SOLD_PAGING = '//div[@data-testid="listing-container"]/p[contains(text(), "件") and contains(text(), "全")]'
SOLD_ITEM_LINK = '//a[@data-testid="sold-item-link"]'
SOLD_ITEM_PRICE_NUMBER = '//span[contains(text(), "¥")]/following-sibling::span'

# =============================================================================
# 購入履歴ページ
# =============================================================================

BOUGHT_LIST = '//ul[@data-testid="purchase-item-list"]'
BOUGHT_LIST_ITEM = BOUGHT_LIST + "/li"
BOUGHT_ITEM_LABEL = '//p[@data-testid="item-label"]'
BOUGHT_ITEM_LINK = "//a"
BOUGHT_ITEM_DATETIME = '//span[contains(text(), "/") and contains(text(), ":")]'
BOUGHT_MORE_BUTTON = '//button[span[contains(normalize-space(), "もっと見る")]]'


# =============================================================================
# 動的セレクタ生成関数
# =============================================================================


def nth_element(base_xpath: str, index: int) -> str:
    """n番目の要素を選択するセレクタを生成

    Args:
        base_xpath: ベースとなるXPath
        index: 1始まりのインデックス

    Returns:
        n番目の要素を選択するXPath
    """
    return f"({base_xpath})[{index}]"


def sold_item_column(item_xpath: str, col_index: int) -> str:
    """販売履歴アイテムの n 番目のカラムを選択

    Args:
        item_xpath: アイテム行のXPath
        col_index: カラムのインデックス（1始まり）

    Returns:
        カラムを選択するXPath
    """
    return f"({item_xpath}//td)[{col_index}]"
