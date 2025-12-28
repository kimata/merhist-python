#!/usr/bin/env python3
# ruff: noqa: S101
"""
セレクタ関数のテスト
"""
import merhist.selectors


class TestNthElement:
    """nth_element のテスト"""

    def test_first_element(self):
        """1番目の要素"""
        result = merhist.selectors.nth_element("//div", 1)
        assert result == "(//div)[1]"

    def test_tenth_element(self):
        """10番目の要素"""
        result = merhist.selectors.nth_element("//ul/li", 10)
        assert result == "(//ul/li)[10]"

    def test_complex_xpath(self):
        """複雑なXPath"""
        base = '//div[@class="container"]//span'
        result = merhist.selectors.nth_element(base, 5)
        assert result == f"({base})[5]"


class TestSoldItemColumn:
    """sold_item_column のテスト"""

    def test_first_column(self):
        """1番目のカラム"""
        result = merhist.selectors.sold_item_column("//tr[1]", 1)
        assert result == "(//tr[1]//td)[1]"

    def test_ninth_column(self):
        """9番目のカラム"""
        result = merhist.selectors.sold_item_column("//tr[5]", 9)
        assert result == "(//tr[5]//td)[9]"


class TestSelectorConstants:
    """セレクタ定数のテスト"""

    def test_navigation_top_exists(self):
        """NAVIGATION_TOP が定義されている"""
        assert merhist.selectors.NAVIGATION_TOP
        assert "merNavigationTop" in merhist.selectors.NAVIGATION_TOP

    def test_sold_list_item_exists(self):
        """SOLD_LIST_ITEM が定義されている"""
        assert merhist.selectors.SOLD_LIST_ITEM
        assert "listing-container" in merhist.selectors.SOLD_LIST_ITEM

    def test_bought_list_exists(self):
        """BOUGHT_LIST が定義されている"""
        assert merhist.selectors.BOUGHT_LIST
        assert "purchase-item-list" in merhist.selectors.BOUGHT_LIST
