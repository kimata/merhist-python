#!/usr/bin/env python3
"""商品情報のデータクラス定義"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field, fields
from typing import Any


@dataclass
class ItemBase:
    """商品情報の基底クラス"""

    id: str = ""
    name: str = ""
    order_url: str = ""
    url: str = ""
    shop: str = ""
    count: int = 1
    category: list[str] = field(default_factory=list)
    condition: str = ""
    postage_charge: str = ""
    seller_region: str = ""
    shipping_method: str = ""
    purchase_date: datetime.datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """辞書に変換（None や空リストは除外）"""
        result: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            # None は除外
            if value is None:
                continue
            # 空リストは除外
            if isinstance(value, list) and len(value) == 0:
                continue
            result[f.name] = value
        return result

    def __getitem__(self, key: str) -> Any:
        """dict 互換のキーアクセスをサポート"""
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        """dict 互換の in 演算子をサポート（to_dict() と同じ条件）"""
        if not hasattr(self, key):
            return False
        value = getattr(self, key)
        if value is None:
            return False
        return not (isinstance(value, list) and len(value) == 0)

    def set_field(self, name: str, value: Any) -> None:
        """フィールド名を検証して値を設定する（タイポ防止）"""
        valid_fields = {f.name for f in fields(self)}
        if name not in valid_fields:
            raise ValueError(f"Unknown field: {name} (valid: {', '.join(sorted(valid_fields))})")
        setattr(self, name, value)


@dataclass
class SoldItem(ItemBase):
    """販売アイテム"""

    price: int = 0
    commission: int = 0
    postage: int = 0
    commission_rate: int = 0
    profit: int = 0
    completion_date: datetime.datetime | None = None


@dataclass
class BoughtItem(ItemBase):
    """購入アイテム"""

    price: int | None = None
