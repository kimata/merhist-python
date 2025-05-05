#!/usr/bin/env python3
SOLD_ITEM_PER_PAGE = 20

LOGIN_URL = "https://jp.mercari.com"

BOUGHT_HIST_URL = "https://jp.mercari.com/mypage/purchases"
BOUGHT_HIST_ITEM_XPATH = '//div[@id="my-page-main-content"]//div[contains(@class, "merListItem")]'

LOADING_BUTTON_XPATH = '//div[contains(@class, "merIconLoading")]'

SOLD_HIST_URL = "https://jp.mercari.com/mypage/listings/sold?page={page}"
SOLD_HIST_PAGING_XPATH = '//div[contains(@class, "merTab")]/following-sibling::p[contains(@class, "merText")]'

ITEM_NORMAL_TRANSACTION_URL = "https://jp.mercari.com/transaction/{id}"
ITEM_SHOP_TRANSACTION_URL = "https://mercari-shops.com/orders/{id}"

ITEM_NORMAL_DESCRIPTION_URL = "https://jp.mercari.com/item/{id}"
ITEM_SHOP_DESCRIPTION_URL = "https://jp.mercari.com/shops/product/{id}"
