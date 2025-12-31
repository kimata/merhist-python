#!/usr/bin/env python3
"""SQLite データベースアクセス層"""

from __future__ import annotations

import datetime
import json
import logging
import pathlib
import shutil
import sqlite3
import zoneinfo
from typing import TYPE_CHECKING

import merhist.item

if TYPE_CHECKING:
    from typing import Any

SQLITE_MAGIC = b"SQLite format 3\x00"


def is_sqlite_file(path: pathlib.Path) -> bool:
    """ファイルが SQLite 形式かどうかを判定"""
    if not path.exists() or path.stat().st_size < 16:
        return False
    with path.open("rb") as f:
        header = f.read(16)
    return header.startswith(SQLITE_MAGIC)


class Database:
    """SQLite データベースアクセス層"""

    def __init__(self, db_path: pathlib.Path, schema_path: pathlib.Path) -> None:
        self._db_path = db_path
        self._schema_path = schema_path
        self._conn: sqlite3.Connection | None = None
        self._init_database()

    def _init_database(self) -> None:
        """データベースを初期化"""
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row

        with self._schema_path.open("r", encoding="utf-8") as f:
            schema = f.read()
        self._conn.executescript(schema)
        self._conn.commit()

    def close(self) -> None:
        """データベース接続を閉じる"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        """接続を取得"""
        if self._conn is None:
            raise RuntimeError("Database connection is closed")
        return self._conn

    # --- 販売アイテム ---
    def upsert_sold_item(self, item: merhist.item.SoldItem) -> None:
        """販売アイテムを挿入または更新"""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO sold_items (
                id, name, order_url, url, shop, count, category, condition,
                postage_charge, seller_region, shipping_method, purchase_date,
                error, price, commission, postage, commission_rate, profit, completion_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.id,
                item.name,
                item.order_url,
                item.url,
                item.shop,
                item.count,
                json.dumps(item.category, ensure_ascii=False) if item.category else None,
                item.condition,
                item.postage_charge,
                item.seller_region,
                item.shipping_method,
                item.purchase_date.isoformat() if item.purchase_date else None,
                item.error,
                item.price,
                item.commission,
                item.postage,
                item.commission_rate,
                item.profit,
                item.completion_date.isoformat() if item.completion_date else None,
            ),
        )
        conn.commit()

    def exists_sold_item(self, item_id: str) -> bool:
        """販売アイテムが存在するか確認"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT 1 FROM sold_items WHERE id = ?", (item_id,))
        return cursor.fetchone() is not None

    def get_sold_item_list(self) -> list[merhist.item.SoldItem]:
        """販売アイテムリストを取得（completion_date 順）"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM sold_items ORDER BY completion_date")
        return [self._row_to_sold_item(row) for row in cursor.fetchall()]

    def get_sold_count(self) -> int:
        """販売アイテム数を取得"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM sold_items")
        result = cursor.fetchone()
        return result[0] if result else 0

    def _row_to_sold_item(self, row: sqlite3.Row) -> merhist.item.SoldItem:
        """Row を SoldItem に変換"""
        return merhist.item.SoldItem(
            id=row["id"],
            name=row["name"],
            order_url=row["order_url"] or "",
            url=row["url"] or "",
            shop=row["shop"] or "",
            count=row["count"] or 1,
            category=json.loads(row["category"]) if row["category"] else [],
            condition=row["condition"] or "",
            postage_charge=row["postage_charge"] or "",
            seller_region=row["seller_region"] or "",
            shipping_method=row["shipping_method"] or "",
            purchase_date=self._parse_datetime(row["purchase_date"]),
            error=row["error"],
            price=row["price"] or 0,
            commission=row["commission"] or 0,
            postage=row["postage"] or 0,
            commission_rate=row["commission_rate"] or 0,
            profit=row["profit"] or 0,
            completion_date=self._parse_datetime(row["completion_date"]),
        )

    # --- 購入アイテム ---
    def upsert_bought_item(self, item: merhist.item.BoughtItem) -> None:
        """購入アイテムを挿入または更新"""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO bought_items (
                id, name, order_url, url, shop, count, category, condition,
                postage_charge, seller_region, shipping_method, purchase_date,
                error, price
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.id,
                item.name,
                item.order_url,
                item.url,
                item.shop,
                item.count,
                json.dumps(item.category, ensure_ascii=False) if item.category else None,
                item.condition,
                item.postage_charge,
                item.seller_region,
                item.shipping_method,
                item.purchase_date.isoformat() if item.purchase_date else None,
                item.error,
                item.price,
            ),
        )
        conn.commit()

    def exists_bought_item(self, item_id: str) -> bool:
        """購入アイテムが存在するか確認"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT 1 FROM bought_items WHERE id = ?", (item_id,))
        return cursor.fetchone() is not None

    def get_bought_item_list(self) -> list[merhist.item.BoughtItem]:
        """購入アイテムリストを取得（purchase_date 順）"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM bought_items ORDER BY purchase_date")
        return [self._row_to_bought_item(row) for row in cursor.fetchall()]

    def get_bought_count(self) -> int:
        """購入アイテム数を取得"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM bought_items")
        result = cursor.fetchone()
        return result[0] if result else 0

    def _row_to_bought_item(self, row: sqlite3.Row) -> merhist.item.BoughtItem:
        """Row を BoughtItem に変換"""
        return merhist.item.BoughtItem(
            id=row["id"],
            name=row["name"],
            order_url=row["order_url"] or "",
            url=row["url"] or "",
            shop=row["shop"] or "",
            count=row["count"] or 1,
            category=json.loads(row["category"]) if row["category"] else [],
            condition=row["condition"] or "",
            postage_charge=row["postage_charge"] or "",
            seller_region=row["seller_region"] or "",
            shipping_method=row["shipping_method"] or "",
            purchase_date=self._parse_datetime(row["purchase_date"]),
            error=row["error"],
            price=row["price"],
        )

    # --- メタデータ ---
    def get_metadata(self, key: str, default: str = "") -> str:
        """メタデータを取得"""
        conn = self._get_conn()
        cursor = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

    def set_metadata(self, key: str, value: str) -> None:
        """メタデータを設定"""
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()

    def get_metadata_int(self, key: str, default: int = 0) -> int:
        """メタデータを整数として取得"""
        value = self.get_metadata(key, str(default))
        try:
            return int(value)
        except ValueError:
            return default

    def set_metadata_int(self, key: str, value: int) -> None:
        """メタデータを整数として設定"""
        self.set_metadata(key, str(value))

    # --- ユーティリティ ---
    @staticmethod
    def _parse_datetime(value: str | None) -> datetime.datetime | None:
        """ISO 8601 文字列を datetime に変換（timezone なし）"""
        if not value:
            return None
        try:
            dt = datetime.datetime.fromisoformat(value)
            # Excel が timezone 付き datetime をサポートしないため、timezone を削除
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except ValueError:
            return None

    def migrate_from_trading_info(self, trading_info: Any) -> None:
        """TradingInfo からデータを移行"""
        logging.info("pickle から SQLite へ移行を開始します...")

        # 販売アイテム
        for item in trading_info.sold_item_list:
            self.upsert_sold_item(item)
        logging.info("販売アイテム %d 件を移行しました", len(trading_info.sold_item_list))

        # 購入アイテム
        for item in trading_info.bought_item_list:
            self.upsert_bought_item(item)
        logging.info("購入アイテム %d 件を移行しました", len(trading_info.bought_item_list))

        # メタデータ
        self.set_metadata_int("sold_total_count", trading_info.sold_total_count)
        self.set_metadata_int("bought_total_count", trading_info.bought_total_count)
        self.set_metadata("last_modified", trading_info.last_modified.isoformat())

        logging.info("SQLite への移行が完了しました")


def open_database(
    db_path: pathlib.Path,
    schema_path: pathlib.Path,
) -> Database:
    """データベースを開く（pickle なら自動変換）"""
    if db_path.exists() and not is_sqlite_file(db_path):
        logging.info("pickle ファイルを検出しました。SQLite に変換します...")

        # pickle を読み込み
        import my_lib.serializer

        from merhist.handle import TradingInfo

        trading_info = my_lib.serializer.load(db_path, TradingInfo())

        # バックアップ作成
        backup_path = db_path.with_suffix(".dat.bak")
        shutil.copy(db_path, backup_path)
        logging.info("バックアップを作成しました: %s", backup_path)

        # 既存ファイルを削除して新規 SQLite 作成
        db_path.unlink()
        db = Database(db_path, schema_path)
        db.migrate_from_trading_info(trading_info)

        return db

    return Database(db_path, schema_path)
