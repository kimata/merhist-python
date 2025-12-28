#!/usr/bin/env python3
# ruff: noqa: S101
"""
日付解析関数のテスト
"""
import datetime

import pytest

import merhist.crawler


class TestParseDate:
    """parse_date のテスト"""

    def test_standard_format(self):
        """標準フォーマット YYYY/MM/DD"""
        result = merhist.crawler.parse_date("2025/01/15")
        assert result == datetime.datetime(2025, 1, 15)

    def test_end_of_year(self):
        """年末の日付"""
        result = merhist.crawler.parse_date("2025/12/31")
        assert result == datetime.datetime(2025, 12, 31)

    def test_beginning_of_year(self):
        """年始の日付"""
        result = merhist.crawler.parse_date("2025/01/01")
        assert result == datetime.datetime(2025, 1, 1)

    def test_leap_year(self):
        """うるう年の2月29日"""
        result = merhist.crawler.parse_date("2024/02/29")
        assert result == datetime.datetime(2024, 2, 29)

    def test_invalid_format_raises_error(self):
        """無効なフォーマットでエラー"""
        with pytest.raises(ValueError):
            merhist.crawler.parse_date("2025-01-15")

    def test_invalid_date_raises_error(self):
        """存在しない日付でエラー"""
        with pytest.raises(ValueError):
            merhist.crawler.parse_date("2025/02/30")


class TestParseDatetime:
    """parse_datetime のテスト"""

    def test_japanese_format(self):
        """日本語フォーマット（デフォルト）"""
        result = merhist.crawler.parse_datetime("2025年01月15日 10:30")
        assert result == datetime.datetime(2025, 1, 15, 10, 30)

    def test_japanese_format_explicit(self):
        """日本語フォーマット（明示的指定）"""
        result = merhist.crawler.parse_datetime("2025年12月31日 23:59", is_japanese=True)
        assert result == datetime.datetime(2025, 12, 31, 23, 59)

    def test_slash_format(self):
        """スラッシュフォーマット"""
        result = merhist.crawler.parse_datetime("2025/01/15 10:30", is_japanese=False)
        assert result == datetime.datetime(2025, 1, 15, 10, 30)

    def test_midnight(self):
        """深夜0時"""
        result = merhist.crawler.parse_datetime("2025年01月01日 00:00")
        assert result == datetime.datetime(2025, 1, 1, 0, 0)

    def test_noon(self):
        """正午"""
        result = merhist.crawler.parse_datetime("2025年06月15日 12:00")
        assert result == datetime.datetime(2025, 6, 15, 12, 0)

    def test_invalid_japanese_format_raises_error(self):
        """無効な日本語フォーマットでエラー"""
        with pytest.raises(ValueError):
            merhist.crawler.parse_datetime("2025/01/15 10:30", is_japanese=True)

    def test_invalid_slash_format_raises_error(self):
        """無効なスラッシュフォーマットでエラー"""
        with pytest.raises(ValueError):
            merhist.crawler.parse_datetime("2025年01月15日 10:30", is_japanese=False)

    def test_missing_time_raises_error(self):
        """時刻なしでエラー"""
        with pytest.raises(ValueError):
            merhist.crawler.parse_datetime("2025年01月15日")
