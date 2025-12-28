#!/usr/bin/env python3
# ruff: noqa: S101
"""
カスタム例外クラスのテスト
"""
import pytest

import merhist.exceptions


class TestMerhisError:
    """MerhisError のテスト"""

    def test_base_exception(self):
        """基底例外として機能する"""
        with pytest.raises(merhist.exceptions.MerhisError):
            raise merhist.exceptions.MerhisError("テストエラー")

    def test_message(self):
        """メッセージを保持する"""
        error = merhist.exceptions.MerhisError("テストメッセージ")
        assert str(error) == "テストメッセージ"


class TestPageError:
    """PageError のテスト"""

    def test_with_url(self):
        """URLありの場合"""
        error = merhist.exceptions.PageError("ページエラー", "https://example.com")
        assert error.url == "https://example.com"
        assert "ページエラー" in str(error)
        assert "https://example.com" in str(error)

    def test_without_url(self):
        """URLなしの場合"""
        error = merhist.exceptions.PageError("ページエラー")
        assert error.url == ""
        assert str(error) == "ページエラー"

    def test_inheritance(self):
        """MerhisError を継承している"""
        error = merhist.exceptions.PageError("テスト")
        assert isinstance(error, merhist.exceptions.MerhisError)


class TestPageLoadError:
    """PageLoadError のテスト"""

    def test_inheritance(self):
        """PageError を継承している"""
        error = merhist.exceptions.PageLoadError("読み込み失敗", "https://example.com")
        assert isinstance(error, merhist.exceptions.PageError)
        assert isinstance(error, merhist.exceptions.MerhisError)

    def test_str_format(self):
        """文字列フォーマット"""
        error = merhist.exceptions.PageLoadError("読み込み失敗", "https://example.com/page")
        assert "読み込み失敗" in str(error)
        assert "https://example.com/page" in str(error)


class TestInvalidURLFormatError:
    """InvalidURLFormatError のテスト"""

    def test_inheritance(self):
        """PageError を継承している"""
        error = merhist.exceptions.InvalidURLFormatError("不正なURL", "invalid-url")
        assert isinstance(error, merhist.exceptions.PageError)

    def test_str_format(self):
        """文字列フォーマット"""
        error = merhist.exceptions.InvalidURLFormatError("URLが不正", "bad://url")
        assert "URLが不正" in str(error)
        assert "bad://url" in str(error)


class TestInvalidPageFormatError:
    """InvalidPageFormatError のテスト"""

    def test_inheritance(self):
        """PageError を継承している"""
        error = merhist.exceptions.InvalidPageFormatError("形式不正")
        assert isinstance(error, merhist.exceptions.PageError)


class TestHistoryFetchError:
    """HistoryFetchError のテスト"""

    def test_inheritance(self):
        """MerhisError を継承している"""
        error = merhist.exceptions.HistoryFetchError("取得失敗")
        assert isinstance(error, merhist.exceptions.MerhisError)

    def test_message(self):
        """メッセージを保持する"""
        error = merhist.exceptions.HistoryFetchError("履歴取得に失敗しました")
        assert str(error) == "履歴取得に失敗しました"
