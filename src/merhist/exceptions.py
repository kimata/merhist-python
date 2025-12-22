#!/usr/bin/env python3
"""カスタム例外クラス定義"""

from __future__ import annotations


class MerhisError(Exception):
    """Merhist 基底例外"""


class LoginError(MerhisError):
    """ログイン失敗"""


class PageLoadError(MerhisError):
    """ページ読み込み失敗"""

    def __init__(self, message: str, url: str = "") -> None:
        super().__init__(message)
        self.url = url


class InvalidURLFormatError(MerhisError):
    """URL形式が不正"""

    def __init__(self, message: str, url: str = "") -> None:
        super().__init__(message)
        self.url = url


class InvalidPageFormatError(MerhisError):
    """ページ形式が不正"""

    def __init__(self, message: str, url: str = "") -> None:
        super().__init__(message)
        self.url = url


class ItemFetchError(MerhisError):
    """商品情報取得失敗"""

    def __init__(self, message: str, item_id: str = "") -> None:
        super().__init__(message)
        self.item_id = item_id


class HistoryFetchError(MerhisError):
    """履歴取得失敗"""
