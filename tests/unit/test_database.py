#!/usr/bin/env python3
# ruff: noqa: S101
"""
データベースアクセス層（Database）のテスト
"""

import datetime
import pathlib
from collections.abc import Generator

import pytest

import merhist.database
from merhist.database import Database
from merhist.database import _is_sqlite_file as is_sqlite_file
from merhist.item import BoughtItem, SoldItem

# === テスト用定数 ===
SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"


# === フィクスチャ ===
@pytest.fixture
def db(tmp_path: pathlib.Path) -> Generator[Database, None, None]:
    """テスト用データベースフィクスチャ"""
    db_path = tmp_path / "test.db"
    database = Database(db_path, SCHEMA_PATH)
    yield database
    database.close()


@pytest.fixture
def sample_sold_item() -> SoldItem:
    """テスト用 SoldItem フィクスチャ"""
    return SoldItem(
        id="m12345678901",
        name="テスト商品",
        order_url="https://jp.mercari.com/transaction/m12345678901",
        url="https://jp.mercari.com/item/m12345678901",
        shop="mercari.com",
        count=2,
        category=["本・雑誌・漫画", "漫画", "少年漫画"],
        condition="目立った傷や汚れなし",
        postage_charge="送料込み",
        seller_region="東京都",
        shipping_method="らくらくメルカリ便",
        purchase_date=datetime.datetime(2025, 1, 15, 10, 30),
        price=1500,
        commission=150,
        postage=200,
        commission_rate=10,
        profit=1150,
        completion_date=datetime.datetime(2025, 1, 18, 14, 0),
    )


@pytest.fixture
def sample_bought_item() -> BoughtItem:
    """テスト用 BoughtItem フィクスチャ"""
    return BoughtItem(
        id="m98765432101",
        name="購入テスト商品",
        order_url="https://jp.mercari.com/transaction/m98765432101",
        url="https://jp.mercari.com/item/m98765432101",
        shop="mercari.com",
        count=1,
        category=["家電・スマホ・カメラ", "スマートフォン本体"],
        condition="新品、未使用",
        postage_charge="送料込み",
        seller_region="大阪府",
        shipping_method="ゆうゆうメルカリ便",
        purchase_date=datetime.datetime(2025, 1, 20, 15, 45),
        price=25000,
    )


# === is_sqlite_file テスト ===
class TestIsSqliteFile:
    """is_sqlite_file 関数のテスト"""

    def test_valid_sqlite_file(self, db: Database, tmp_path: pathlib.Path):
        """SQLite ファイルを正しく判定"""
        db_path = tmp_path / "test.db"
        assert is_sqlite_file(db_path) is True

    def test_nonexistent_file(self, tmp_path: pathlib.Path):
        """存在しないファイルは False"""
        nonexistent = tmp_path / "nonexistent.db"
        assert is_sqlite_file(nonexistent) is False

    def test_empty_file(self, tmp_path: pathlib.Path):
        """空ファイルは False"""
        empty_file = tmp_path / "empty.db"
        empty_file.touch()
        assert is_sqlite_file(empty_file) is False

    def test_small_file(self, tmp_path: pathlib.Path):
        """16バイト未満のファイルは False"""
        small_file = tmp_path / "small.db"
        small_file.write_bytes(b"short")
        assert is_sqlite_file(small_file) is False

    def test_non_sqlite_file(self, tmp_path: pathlib.Path):
        """SQLite 以外のファイルは False"""
        text_file = tmp_path / "text.txt"
        text_file.write_text("This is not a SQLite file" * 10)
        assert is_sqlite_file(text_file) is False

    def test_file_with_fake_header(self, tmp_path: pathlib.Path):
        """SQLite ヘッダで始まるが不正なファイル"""
        fake_file = tmp_path / "fake.db"
        fake_file.write_bytes(merhist.database._SQLITE_MAGIC + b"\x00" * 100)
        assert is_sqlite_file(fake_file) is True  # ヘッダのみで判定


# === Database 初期化テスト ===
class TestDatabaseInit:
    """Database 初期化のテスト"""

    def test_creates_database_file(self, tmp_path: pathlib.Path):
        """データベースファイルが作成される"""
        db_path = tmp_path / "new.db"
        assert not db_path.exists()

        database = Database(db_path, SCHEMA_PATH)
        assert db_path.exists()
        database.close()

    def test_creates_tables(self, db: Database):
        """テーブルが作成される"""
        conn = db._get_conn()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        assert "sold_items" in tables
        assert "bought_items" in tables
        assert "metadata" in tables


# === 販売アイテム（SoldItem）テスト ===
class TestSoldItemCRUD:
    """SoldItem の CRUD 操作テスト"""

    def test_upsert_new_item(self, db: Database, sample_sold_item: SoldItem):
        """新規アイテムの挿入"""
        db.upsert_sold_item(sample_sold_item)
        assert db.exists_sold_item(sample_sold_item.id) is True

    def test_upsert_updates_existing(self, db: Database, sample_sold_item: SoldItem):
        """既存アイテムの更新"""
        db.upsert_sold_item(sample_sold_item)

        # 値を変更して更新
        updated_item = SoldItem(
            id=sample_sold_item.id,
            name="更新後の商品名",
            price=2000,
            profit=1800,
        )
        db.upsert_sold_item(updated_item)

        items = db.get_sold_item_list()
        assert len(items) == 1
        assert items[0].name == "更新後の商品名"
        assert items[0].price == 2000

    def test_exists_sold_item_false(self, db: Database):
        """存在しないアイテムは False"""
        assert db.exists_sold_item("nonexistent") is False

    def test_get_sold_count_empty(self, db: Database):
        """空のときは 0"""
        assert db.get_sold_count() == 0

    def test_get_sold_count(self, db: Database, sample_sold_item: SoldItem):
        """アイテム数を正しく返す"""
        db.upsert_sold_item(sample_sold_item)
        assert db.get_sold_count() == 1

        # 別のアイテムを追加
        item2 = SoldItem(id="m00000000002", name="商品2", price=500)
        db.upsert_sold_item(item2)
        assert db.get_sold_count() == 2

    def test_get_sold_item_list_empty(self, db: Database):
        """空のリストを返す"""
        items = db.get_sold_item_list()
        assert items == []

    def test_get_sold_item_list_ordered(self, db: Database):
        """completion_date でソートされる"""
        item1 = SoldItem(
            id="m001",
            name="商品1",
            completion_date=datetime.datetime(2025, 1, 20),
        )
        item2 = SoldItem(
            id="m002",
            name="商品2",
            completion_date=datetime.datetime(2025, 1, 10),
        )
        item3 = SoldItem(
            id="m003",
            name="商品3",
            completion_date=datetime.datetime(2025, 1, 15),
        )

        db.upsert_sold_item(item1)
        db.upsert_sold_item(item2)
        db.upsert_sold_item(item3)

        items = db.get_sold_item_list()
        assert [i.id for i in items] == ["m002", "m003", "m001"]

    def test_sold_item_all_fields_preserved(self, db: Database, sample_sold_item: SoldItem):
        """全フィールドが保存・復元される"""
        db.upsert_sold_item(sample_sold_item)
        items = db.get_sold_item_list()
        item = items[0]

        assert item.id == sample_sold_item.id
        assert item.name == sample_sold_item.name
        assert item.order_url == sample_sold_item.order_url
        assert item.url == sample_sold_item.url
        assert item.shop == sample_sold_item.shop
        assert item.count == sample_sold_item.count
        assert item.category == sample_sold_item.category
        assert item.condition == sample_sold_item.condition
        assert item.postage_charge == sample_sold_item.postage_charge
        assert item.seller_region == sample_sold_item.seller_region
        assert item.shipping_method == sample_sold_item.shipping_method
        assert item.purchase_date == sample_sold_item.purchase_date
        assert item.price == sample_sold_item.price
        assert item.commission == sample_sold_item.commission
        assert item.postage == sample_sold_item.postage
        assert item.commission_rate == sample_sold_item.commission_rate
        assert item.profit == sample_sold_item.profit
        assert item.completion_date == sample_sold_item.completion_date


class TestSoldItemCategory:
    """SoldItem のカテゴリ（JSON配列）テスト"""

    def test_category_json_serialization(self, db: Database):
        """カテゴリが JSON としてシリアライズされる"""
        item = SoldItem(
            id="m001",
            name="商品",
            category=["本・雑誌・漫画", "漫画", "少年漫画"],
        )
        db.upsert_sold_item(item)

        items = db.get_sold_item_list()
        assert items[0].category == ["本・雑誌・漫画", "漫画", "少年漫画"]

    def test_empty_category(self, db: Database):
        """空のカテゴリは空リストに復元される"""
        item = SoldItem(id="m001", name="商品", category=[])
        db.upsert_sold_item(item)

        items = db.get_sold_item_list()
        assert items[0].category == []

    def test_category_with_unicode(self, db: Database):
        """日本語を含むカテゴリ"""
        item = SoldItem(
            id="m001",
            name="商品",
            category=["ファッション", "メンズ", "トップス"],
        )
        db.upsert_sold_item(item)

        items = db.get_sold_item_list()
        assert items[0].category == ["ファッション", "メンズ", "トップス"]


class TestSoldItemNullHandling:
    """SoldItem の NULL 値処理テスト"""

    def test_null_fields_have_defaults(self, db: Database):
        """NULL フィールドはデフォルト値に変換される"""
        item = SoldItem(id="m001", name="最小限の商品")
        db.upsert_sold_item(item)

        items = db.get_sold_item_list()
        restored = items[0]

        assert restored.order_url == ""
        assert restored.url == ""
        assert restored.shop == ""
        assert restored.count == 1
        assert restored.category == []
        assert restored.condition == ""
        assert restored.postage_charge == ""
        assert restored.seller_region == ""
        assert restored.shipping_method == ""
        assert restored.price == 0
        assert restored.commission == 0
        assert restored.postage == 0
        assert restored.commission_rate == 0
        assert restored.profit == 0

    def test_error_field_preserved(self, db: Database):
        """error フィールドが保存される"""
        item = SoldItem(id="m001", name="エラー商品", error="ページ読み込み失敗")
        db.upsert_sold_item(item)

        items = db.get_sold_item_list()
        assert items[0].error == "ページ読み込み失敗"


# === 購入アイテム（BoughtItem）テスト ===
class TestBoughtItemCRUD:
    """BoughtItem の CRUD 操作テスト"""

    def test_upsert_new_item(self, db: Database, sample_bought_item: BoughtItem):
        """新規アイテムの挿入"""
        db.upsert_bought_item(sample_bought_item)
        assert db.exists_bought_item(sample_bought_item.id) is True

    def test_upsert_updates_existing(self, db: Database, sample_bought_item: BoughtItem):
        """既存アイテムの更新"""
        db.upsert_bought_item(sample_bought_item)

        updated_item = BoughtItem(
            id=sample_bought_item.id,
            name="更新後の購入商品",
            price=30000,
        )
        db.upsert_bought_item(updated_item)

        items = db.get_bought_item_list()
        assert len(items) == 1
        assert items[0].name == "更新後の購入商品"
        assert items[0].price == 30000

    def test_exists_bought_item_false(self, db: Database):
        """存在しないアイテムは False"""
        assert db.exists_bought_item("nonexistent") is False

    def test_get_bought_count_empty(self, db: Database):
        """空のときは 0"""
        assert db.get_bought_count() == 0

    def test_get_bought_count(self, db: Database, sample_bought_item: BoughtItem):
        """アイテム数を正しく返す"""
        db.upsert_bought_item(sample_bought_item)
        assert db.get_bought_count() == 1

    def test_get_bought_item_list_ordered(self, db: Database):
        """purchase_date でソートされる"""
        item1 = BoughtItem(
            id="m001",
            name="商品1",
            purchase_date=datetime.datetime(2025, 1, 20),
        )
        item2 = BoughtItem(
            id="m002",
            name="商品2",
            purchase_date=datetime.datetime(2025, 1, 10),
        )
        item3 = BoughtItem(
            id="m003",
            name="商品3",
            purchase_date=datetime.datetime(2025, 1, 15),
        )

        db.upsert_bought_item(item1)
        db.upsert_bought_item(item2)
        db.upsert_bought_item(item3)

        items = db.get_bought_item_list()
        assert [i.id for i in items] == ["m002", "m003", "m001"]

    def test_bought_item_all_fields_preserved(self, db: Database, sample_bought_item: BoughtItem):
        """全フィールドが保存・復元される"""
        db.upsert_bought_item(sample_bought_item)
        items = db.get_bought_item_list()
        item = items[0]

        assert item.id == sample_bought_item.id
        assert item.name == sample_bought_item.name
        assert item.order_url == sample_bought_item.order_url
        assert item.url == sample_bought_item.url
        assert item.shop == sample_bought_item.shop
        assert item.count == sample_bought_item.count
        assert item.category == sample_bought_item.category
        assert item.condition == sample_bought_item.condition
        assert item.postage_charge == sample_bought_item.postage_charge
        assert item.seller_region == sample_bought_item.seller_region
        assert item.shipping_method == sample_bought_item.shipping_method
        assert item.purchase_date == sample_bought_item.purchase_date
        assert item.price == sample_bought_item.price


class TestBoughtItemNullPrice:
    """BoughtItem の price が None の場合のテスト"""

    def test_null_price_preserved(self, db: Database):
        """price=None がそのまま保存・復元される"""
        item = BoughtItem(id="m001", name="価格なし商品", price=None)
        db.upsert_bought_item(item)

        items = db.get_bought_item_list()
        assert items[0].price is None


# === メタデータテスト ===
class TestMetadata:
    """メタデータ操作のテスト"""

    def test_set_get_metadata(self, db: Database):
        """メタデータの保存・取得"""
        db.set_metadata("key1", "value1")
        assert db.get_metadata("key1") == "value1"

    def test_get_metadata_default(self, db: Database):
        """存在しないキーはデフォルト値"""
        assert db.get_metadata("nonexistent", "default") == "default"

    def test_get_metadata_empty_default(self, db: Database):
        """デフォルト値が空文字列"""
        assert db.get_metadata("nonexistent") == ""

    def test_update_metadata(self, db: Database):
        """メタデータの更新"""
        db.set_metadata("key1", "value1")
        db.set_metadata("key1", "value2")
        assert db.get_metadata("key1") == "value2"

    def test_set_get_metadata_int(self, db: Database):
        """整数メタデータの保存・取得"""
        db.set_metadata_int("count", 42)
        assert db.get_metadata_int("count") == 42

    def test_get_metadata_int_default(self, db: Database):
        """存在しない整数キーはデフォルト値"""
        assert db.get_metadata_int("nonexistent", 100) == 100

    def test_get_metadata_int_invalid_value(self, db: Database):
        """不正な値はデフォルト値に変換"""
        db.set_metadata("invalid", "not a number")
        assert db.get_metadata_int("invalid", 0) == 0

    def test_metadata_unicode(self, db: Database):
        """日本語メタデータ"""
        db.set_metadata("日本語キー", "日本語の値")
        assert db.get_metadata("日本語キー") == "日本語の値"


# === 日時パーステスト ===
class TestParseDatetime:
    """_parse_datetime のテスト"""

    def test_iso_format(self):
        """ISO 8601 形式のパース"""
        result = Database._parse_datetime("2025-01-15T10:30:00")
        assert result == datetime.datetime(2025, 1, 15, 10, 30, 0)

    def test_date_only(self):
        """日付のみのパース"""
        result = Database._parse_datetime("2025-01-15")
        assert result == datetime.datetime(2025, 1, 15, 0, 0, 0)

    def test_with_timezone(self):
        """タイムゾーン付きはタイムゾーンが削除される"""
        result = Database._parse_datetime("2025-01-15T10:30:00+09:00")
        assert result is not None
        assert result.tzinfo is None
        assert result == datetime.datetime(2025, 1, 15, 10, 30, 0)

    def test_none_value(self):
        """None は None を返す"""
        result = Database._parse_datetime(None)
        assert result is None

    def test_empty_string(self):
        """空文字列は None を返す"""
        result = Database._parse_datetime("")
        assert result is None

    def test_invalid_format(self):
        """不正な形式は None を返す"""
        result = Database._parse_datetime("invalid")
        assert result is None


# === 接続管理テスト ===
class TestConnectionManagement:
    """接続管理のテスト"""

    def test_close_connection(self, tmp_path: pathlib.Path):
        """接続を閉じる"""
        db_path = tmp_path / "test.db"
        database = Database(db_path, SCHEMA_PATH)
        database.close()
        assert database._conn is None

    def test_access_after_close_raises_error(self, tmp_path: pathlib.Path):
        """閉じた後のアクセスでエラー"""
        db_path = tmp_path / "test.db"
        database = Database(db_path, SCHEMA_PATH)
        database.close()

        with pytest.raises(RuntimeError, match="connection is closed"):
            database.get_sold_count()

    def test_close_twice_is_safe(self, tmp_path: pathlib.Path):
        """2回閉じてもエラーにならない"""
        db_path = tmp_path / "test.db"
        database = Database(db_path, SCHEMA_PATH)
        database.close()
        database.close()  # エラーにならない


# === 永続性テスト ===
class TestPersistence:
    """データの永続性テスト"""

    def test_data_persists_after_reopen(self, tmp_path: pathlib.Path):
        """DB を再オープンしてもデータが保持される"""
        db_path = tmp_path / "persist.db"

        # データを挿入
        db1 = Database(db_path, SCHEMA_PATH)
        item = SoldItem(id="m001", name="永続化テスト", price=1000)
        db1.upsert_sold_item(item)
        db1.set_metadata("version", "1.0")
        db1.close()

        # 再オープン
        db2 = Database(db_path, SCHEMA_PATH)
        items = db2.get_sold_item_list()
        assert len(items) == 1
        assert items[0].name == "永続化テスト"
        assert db2.get_metadata("version") == "1.0"
        db2.close()


# === open_database 関数テスト ===
class TestOpenDatabase:
    """open_database 関数のテスト"""

    def test_open_database(self, tmp_path: pathlib.Path):
        """open_database でデータベースを開く"""
        db_path = tmp_path / "test.db"
        database = merhist.database.open_database(db_path, SCHEMA_PATH)
        assert database is not None
        assert isinstance(database, Database)
        database.close()
