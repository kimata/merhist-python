#!/usr/bin/env python3
from __future__ import annotations

SOLD_ITEM_PER_PAGE: int = 20

MERCARI_URL: str = "https://jp.mercari.com"

BOUGHT_HIST_URL: str = "https://jp.mercari.com/mypage/purchases"
BOUGHT_HIST_ITEM_XPATH: str = '//ul[@data-testid="purchase-item-list"]'

LOADING_BUTTON_XPATH: str = '//div[contains(@class, "merIconLoading")]'

SOLD_HIST_URL: str = "https://jp.mercari.com/mypage/listings/sold?page={page}"
SOLD_HIST_PAGING_XPATH: str = (
    '//div[@data-testid="listing-container"]/p[contains(text(), "件") and contains(text(), "全")]'
)

ITEM_NORMAL_TRANSACTION_URL: str = "https://jp.mercari.com/transaction/{id}"
ITEM_SHOP_TRANSACTION_URL: str = "https://mercari-shops.com/orders/{id}"

ITEM_NORMAL_DESCRIPTION_URL: str = "https://jp.mercari.com/item/{id}"
ITEM_SHOP_DESCRIPTION_URL: str = "https://jp.mercari.com/shops/product/{id}"
