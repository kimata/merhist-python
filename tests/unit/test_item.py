#!/usr/bin/env python3
# ruff: noqa: S101
"""
データモデル（ItemBase, SoldItem, BoughtItem）のテスト
"""

import datetime

import pytest

import merhist.item


class TestItemBaseToDict:
    """ItemBase.to_dict のテスト"""

    def test_basic_fields(self):
        """基本フィールドの辞書変換"""
        item = merhist.item.ItemBase(id="m123", name="テスト商品")
        result = item.to_dict()
        assert result["id"] == "m123"
        assert result["name"] == "テスト商品"

    def test_none_excluded(self):
        """None 値は除外される"""
        item = merhist.item.ItemBase(id="m123", name="テスト", error=None)
        result = item.to_dict()
        assert "error" not in result

    def test_empty_list_excluded(self):
        """空リストは除外される"""
        item = merhist.item.ItemBase(id="m123", name="テスト", category=[])
        result = item.to_dict()
        assert "category" not in result

    def test_non_empty_list_included(self):
        """非空リストは含まれる"""
        item = merhist.item.ItemBase(id="m123", category=["本", "漫画"])
        result = item.to_dict()
        assert result["category"] == ["本", "漫画"]

    def test_datetime_included(self):
        """datetime 値は含まれる"""
        dt = datetime.datetime(2025, 1, 15, 10, 30)
        item = merhist.item.ItemBase(id="m123", purchase_date=dt)
        result = item.to_dict()
        assert result["purchase_date"] == dt

    def test_default_values_included(self):
        """デフォルト値（空文字列、0など）は含まれる"""
        item = merhist.item.ItemBase(id="", name="", count=1)
        result = item.to_dict()
        assert result["id"] == ""
        assert result["name"] == ""
        assert result["count"] == 1


class TestItemBaseGetItem:
    """ItemBase.__getitem__ のテスト"""

    def test_existing_field(self):
        """存在するフィールドへのアクセス"""
        item = merhist.item.ItemBase(id="m123", name="テスト商品")
        assert item["id"] == "m123"
        assert item["name"] == "テスト商品"

    def test_none_field(self):
        """None フィールドへのアクセス"""
        item = merhist.item.ItemBase(id="m123", error=None)
        assert item["error"] is None

    def test_nonexistent_field_raises_error(self):
        """存在しないフィールドでエラー"""
        item = merhist.item.ItemBase(id="m123")
        with pytest.raises(AttributeError):
            _ = item["nonexistent"]


class TestItemBaseContains:
    """ItemBase.__contains__ のテスト"""

    def test_existing_value(self):
        """値が存在するフィールド"""
        item = merhist.item.ItemBase(id="m123", name="テスト")
        assert "id" in item
        assert "name" in item

    def test_none_value_not_in(self):
        """None 値のフィールドは False"""
        item = merhist.item.ItemBase(id="m123", error=None)
        assert "error" not in item

    def test_empty_list_not_in(self):
        """空リストのフィールドは False"""
        item = merhist.item.ItemBase(id="m123", category=[])
        assert "category" not in item

    def test_non_empty_list_in(self):
        """非空リストのフィールドは True"""
        item = merhist.item.ItemBase(id="m123", category=["本"])
        assert "category" in item

    def test_nonexistent_field_not_in(self):
        """存在しないフィールドは False"""
        item = merhist.item.ItemBase(id="m123")
        assert "nonexistent" not in item

    def test_empty_string_in(self):
        """空文字列は True（to_dict と異なる動作）"""
        item = merhist.item.ItemBase(id="", name="")
        assert "id" in item
        assert "name" in item


class TestItemBaseSetField:
    """ItemBase.set_field のテスト"""

    def test_valid_field(self):
        """有効なフィールド名"""
        item = merhist.item.ItemBase()
        item.set_field("id", "m123")
        item.set_field("name", "テスト商品")
        assert item.id == "m123"
        assert item.name == "テスト商品"

    def test_invalid_field_raises_error(self):
        """無効なフィールド名でエラー"""
        item = merhist.item.ItemBase()
        with pytest.raises(ValueError) as exc_info:
            item.set_field("invalid_field", "value")
        assert "Unknown field" in str(exc_info.value)
        assert "invalid_field" in str(exc_info.value)

    def test_typo_field_raises_error(self):
        """タイポしたフィールド名でエラー"""
        item = merhist.item.ItemBase()
        with pytest.raises(ValueError):
            item.set_field("nmae", "テスト")  # name のタイポ


class TestSoldItem:
    """SoldItem のテスト"""

    def test_inheritance(self):
        """ItemBase を継承している"""
        item = merhist.item.SoldItem(id="m123", name="テスト", price=1000)
        assert isinstance(item, merhist.item.ItemBase)

    def test_sold_specific_fields(self):
        """SoldItem 固有フィールド"""
        item = merhist.item.SoldItem(
            id="m123",
            price=1500,
            commission=150,
            postage=200,
            commission_rate=10,
            profit=1150,
            completion_date=datetime.datetime(2025, 1, 18, 14, 0),
        )
        assert item.price == 1500
        assert item.commission == 150
        assert item.postage == 200
        assert item.commission_rate == 10
        assert item.profit == 1150
        assert item.completion_date == datetime.datetime(2025, 1, 18, 14, 0)

    def test_to_dict_includes_sold_fields(self):
        """to_dict に SoldItem 固有フィールドが含まれる"""
        item = merhist.item.SoldItem(id="m123", price=1500, profit=1350)
        result = item.to_dict()
        assert result["price"] == 1500
        assert result["profit"] == 1350

    def test_set_field_with_sold_fields(self):
        """set_field で SoldItem 固有フィールドを設定"""
        item = merhist.item.SoldItem()
        item.set_field("price", 2000)
        item.set_field("commission", 200)
        assert item.price == 2000
        assert item.commission == 200


class TestBoughtItem:
    """BoughtItem のテスト"""

    def test_inheritance(self):
        """ItemBase を継承している"""
        item = merhist.item.BoughtItem(id="m123", name="テスト", price=5000)
        assert isinstance(item, merhist.item.ItemBase)

    def test_bought_specific_fields(self):
        """BoughtItem 固有フィールド"""
        item = merhist.item.BoughtItem(id="m123", price=25000)
        assert item.price == 25000

    def test_price_can_be_none(self):
        """price は None を許容"""
        item = merhist.item.BoughtItem(id="m123", price=None)
        assert item.price is None

    def test_to_dict_with_none_price(self):
        """to_dict で None の price は除外"""
        item = merhist.item.BoughtItem(id="m123", price=None)
        result = item.to_dict()
        assert "price" not in result

    def test_to_dict_with_price(self):
        """to_dict で price が含まれる"""
        item = merhist.item.BoughtItem(id="m123", price=5000)
        result = item.to_dict()
        assert result["price"] == 5000


class TestItemFixtures:
    """フィクスチャを使用したテスト"""

    def test_sold_item_fixture(self, sold_item):
        """sold_item フィクスチャの検証"""
        assert sold_item.id == "m12345678901"
        assert sold_item.name == "テスト商品"
        assert sold_item.price == 1500
        assert sold_item.profit == 1350
        assert len(sold_item.category) == 3

    def test_bought_item_fixture(self, bought_item):
        """bought_item フィクスチャの検証"""
        assert bought_item.id == "m98765432101"
        assert bought_item.name == "購入テスト商品"
        assert bought_item.price == 25000

    def test_shop_item_fixture(self, shop_item):
        """shop_item フィクスチャの検証"""
        assert shop_item.id == "abc123xyz"
        assert shop_item.shop == "mercari-shops.com"
        assert shop_item.price == 3000
