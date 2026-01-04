#!/usr/bin/env python3
"""
定数定義

URL やページ設定など、XPath セレクタ以外の定数を定義します。
XPath セレクタは selectors.py を参照してください。
"""

from __future__ import annotations

SOLD_ITEM_PER_PAGE: int = 20

# Selenium プロファイル名
SELENIUM_PROFILE_NAME: str = "Merhist"

BOUGHT_HIST_URL: str = "https://jp.mercari.com/mypage/purchases"

SOLD_HIST_URL: str = "https://jp.mercari.com/mypage/listings/sold?page={page}"

ITEM_NORMAL_TRANSACTION_URL: str = "https://jp.mercari.com/transaction/{id}"
ITEM_SHOP_TRANSACTION_URL: str = "https://mercari-shops.com/orders/{id}"

ITEM_NORMAL_DESCRIPTION_URL: str = "https://jp.mercari.com/item/{id}"
ITEM_SHOP_DESCRIPTION_URL: str = "https://jp.mercari.com/shops/product/{id}"
