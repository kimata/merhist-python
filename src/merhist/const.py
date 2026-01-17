#!/usr/bin/env python3
"""
定数定義

URL やページ設定など、XPath セレクタ以外の定数を定義します。
XPath セレクタは selectors.py を参照してください。
"""

from __future__ import annotations

import random

SOLD_ITEM_PER_PAGE: int = 20

# Selenium プロファイル名
SELENIUM_PROFILE_NAME: str = "Merhist"

BOUGHT_HIST_URL: str = "https://jp.mercari.com/mypage/purchases"

SOLD_HIST_URL: str = "https://jp.mercari.com/mypage/listings/sold?page={page}"

ITEM_NORMAL_TRANSACTION_URL: str = "https://jp.mercari.com/transaction/{id}"
ITEM_SHOP_TRANSACTION_URL: str = "https://mercari-shops.com/orders/{id}"

ITEM_NORMAL_DESCRIPTION_URL: str = "https://jp.mercari.com/item/{id}"
ITEM_SHOP_DESCRIPTION_URL: str = "https://jp.mercari.com/shops/product/{id}"

# デバッグダンプ用のランダムID最大値
DEBUG_DUMP_ID_MAX: int = 100


def gen_debug_dump_id() -> int:
    """デバッグダンプ用のランダムIDを生成"""
    return random.randint(0, DEBUG_DUMP_ID_MAX - 1)  # noqa: S311
