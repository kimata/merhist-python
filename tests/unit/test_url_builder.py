#!/usr/bin/env python3
# ruff: noqa: S101
"""
URL生成・解析関数のテスト
"""
import pytest

import merhist.crawler
import merhist.exceptions
from merhist.item import BoughtItem, SoldItem


class TestGenSellHistUrl:
    """gen_sell_hist_url のテスト"""

    def test_page_1(self):
        """ページ1のURL生成"""
        url = merhist.crawler.gen_sell_hist_url(1)
        assert url == "https://jp.mercari.com/mypage/listings/sold?page=1"

    def test_page_10(self):
        """ページ10のURL生成"""
        url = merhist.crawler.gen_sell_hist_url(10)
        assert url == "https://jp.mercari.com/mypage/listings/sold?page=10"

    def test_page_100(self):
        """ページ100のURL生成"""
        url = merhist.crawler.gen_sell_hist_url(100)
        assert url == "https://jp.mercari.com/mypage/listings/sold?page=100"


class TestGenItemTransactionUrl:
    """gen_item_transaction_url のテスト"""

    def test_normal_mercari(self):
        """通常のメルカリアイテム"""
        item = SoldItem(id="m12345678901", shop="mercari.com")
        url = merhist.crawler.gen_item_transaction_url(item)
        assert url == "https://jp.mercari.com/transaction/m12345678901"

    def test_mercari_shops(self):
        """メルカリShopsアイテム"""
        item = BoughtItem(id="abc123xyz", shop="mercari-shops.com")
        url = merhist.crawler.gen_item_transaction_url(item)
        assert url == "https://mercari-shops.com/orders/abc123xyz"

    def test_empty_shop_treated_as_normal(self):
        """shop が空の場合は通常メルカリ扱い"""
        item = SoldItem(id="m99999999999", shop="")
        url = merhist.crawler.gen_item_transaction_url(item)
        assert url == "https://jp.mercari.com/transaction/m99999999999"


class TestGenItemDescriptionUrl:
    """gen_item_description_url のテスト"""

    def test_normal_mercari(self):
        """通常のメルカリアイテム"""
        item = SoldItem(id="m12345678901", shop="mercari.com")
        url = merhist.crawler.gen_item_description_url(item)
        assert url == "https://jp.mercari.com/item/m12345678901"

    def test_mercari_shops(self):
        """メルカリShopsアイテム"""
        item = BoughtItem(id="abc123xyz", shop="mercari-shops.com")
        url = merhist.crawler.gen_item_description_url(item)
        assert url == "https://jp.mercari.com/shops/product/abc123xyz"

    def test_empty_shop_treated_as_normal(self):
        """shop が空の場合は通常メルカリ扱い"""
        item = SoldItem(id="m99999999999", shop="")
        url = merhist.crawler.gen_item_description_url(item)
        assert url == "https://jp.mercari.com/item/m99999999999"


class TestSetItemIdFromOrderUrl:
    """set_item_id_from_order_url のテスト"""

    def test_normal_mercari_transaction_url(self):
        """通常のメルカリ取引URL"""
        item = BoughtItem(order_url="https://jp.mercari.com/transaction/m12345678901")
        merhist.crawler.set_item_id_from_order_url(item)
        assert item.id == "m12345678901"
        assert item.shop == "mercari.com"

    def test_normal_mercari_with_trailing_slash(self):
        """末尾スラッシュ付きURL"""
        item = BoughtItem(order_url="https://jp.mercari.com/transaction/m12345678901/")
        merhist.crawler.set_item_id_from_order_url(item)
        assert item.id == "m12345678901"
        assert item.shop == "mercari.com"

    def test_mercari_shops_order_url(self):
        """メルカリShopsの注文URL"""
        item = BoughtItem(order_url="https://mercari-shops.com/orders/abc123xyz")
        merhist.crawler.set_item_id_from_order_url(item)
        assert item.id == "abc123xyz"
        assert item.shop == "mercari-shops.com"

    def test_mercari_shops_with_trailing_slash(self):
        """メルカリShops末尾スラッシュ付きURL"""
        item = BoughtItem(order_url="https://mercari-shops.com/orders/abc123xyz/")
        merhist.crawler.set_item_id_from_order_url(item)
        assert item.id == "abc123xyz"
        assert item.shop == "mercari-shops.com"

    def test_invalid_url_raises_error(self):
        """無効なURLでエラー"""
        item = BoughtItem(order_url="https://example.com/invalid")
        with pytest.raises(merhist.exceptions.InvalidURLFormatError):
            merhist.crawler.set_item_id_from_order_url(item)

    def test_empty_url_raises_error(self):
        """空のURLでエラー"""
        item = BoughtItem(order_url="")
        with pytest.raises(merhist.exceptions.InvalidURLFormatError):
            merhist.crawler.set_item_id_from_order_url(item)
