#!/usr/bin/env python3
"""カスタム例外クラス定義"""

from __future__ import annotations


class MerhisError(Exception):
    """Merhist 基底例外"""


class PageError(MerhisError):
    """ページ関連エラーの基底クラス"""

    def __init__(self, message: str, url: str = "") -> None:
        super().__init__(message)
        self.url = url

    def __str__(self) -> str:
        if self.url:
            return f"{self.args[0]} (URL: {self.url})"
        return str(self.args[0])


class PageLoadError(PageError):
    """ページ読み込み失敗"""


class InvalidURLFormatError(PageError):
    """URL形式が不正"""


class InvalidPageFormatError(PageError):
    """ページ形式が不正"""


class HistoryFetchError(MerhisError):
    """履歴取得失敗"""


class ThumbnailError(MerhisError):
    """サムネイル画像エラーの基底クラス"""

    def __init__(self, message: str, path: str = "") -> None:
        super().__init__(message)
        self.path = path

    def __str__(self) -> str:
        if self.path:
            return f"{self.args[0]}: {self.path}"
        return str(self.args[0])


class ThumbnailEmptyError(ThumbnailError):
    """サムネイル画像データが空"""


class ThumbnailSizeError(ThumbnailError):
    """サムネイル画像のサイズが0"""


class ThumbnailCorruptError(ThumbnailError):
    """サムネイル画像が破損"""
