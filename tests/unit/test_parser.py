#!/usr/bin/env python3
# ruff: noqa: S101
"""
パース関数のテスト
"""
import pytest

import merhist.exceptions
import merhist.parser


class TestParsePrice:
    """parse_price のテスト"""

    def test_yen_symbol(self):
        """円記号付き価格"""
        assert merhist.parser.parse_price("¥1,500") == 1500

    def test_fullwidth_yen_symbol(self):
        """全角円記号付き価格"""
        assert merhist.parser.parse_price("￥1,500") == 1500

    def test_no_symbol(self):
        """記号なし価格"""
        assert merhist.parser.parse_price("1,500") == 1500

    def test_large_price(self):
        """大きい金額"""
        assert merhist.parser.parse_price("¥1,234,567") == 1234567

    def test_small_price(self):
        """小さい金額"""
        assert merhist.parser.parse_price("¥100") == 100

    def test_zero(self):
        """ゼロ"""
        assert merhist.parser.parse_price("0") == 0

    def test_with_spaces(self):
        """前後の空白"""
        assert merhist.parser.parse_price("  ¥1,500  ") == 1500

    def test_empty_raises_error(self):
        """空文字でエラー"""
        with pytest.raises(ValueError):
            merhist.parser.parse_price("")

    def test_only_symbol_raises_error(self):
        """記号のみでエラー"""
        with pytest.raises(ValueError):
            merhist.parser.parse_price("¥")


class TestParseRate:
    """parse_rate のテスト"""

    def test_normal(self):
        """通常の手数料率"""
        assert merhist.parser.parse_rate("10%") == 10

    def test_single_digit(self):
        """1桁の手数料率"""
        assert merhist.parser.parse_rate("5%") == 5

    def test_with_spaces(self):
        """前後の空白"""
        assert merhist.parser.parse_rate("  10%  ") == 10

    def test_empty_raises_error(self):
        """空文字でエラー"""
        with pytest.raises(ValueError):
            merhist.parser.parse_rate("")

    def test_only_percent_raises_error(self):
        """パーセント記号のみでエラー"""
        with pytest.raises(ValueError):
            merhist.parser.parse_rate("%")


class TestParseSoldCount:
    """parse_sold_count のテスト"""

    def test_normal(self):
        """通常のページング形式"""
        assert merhist.parser.parse_sold_count("1～20/全100件") == 100

    def test_large_count(self):
        """大きい件数"""
        assert merhist.parser.parse_sold_count("1～20/全12345件") == 12345

    def test_single_page(self):
        """1ページ分のみ"""
        assert merhist.parser.parse_sold_count("1～5/全5件") == 5

    def test_invalid_format_raises_error(self):
        """無効な形式でエラー"""
        with pytest.raises(merhist.exceptions.InvalidPageFormatError):
            merhist.parser.parse_sold_count("invalid text")

    def test_empty_raises_error(self):
        """空文字でエラー"""
        with pytest.raises(merhist.exceptions.InvalidPageFormatError):
            merhist.parser.parse_sold_count("")


class TestParsePriceWithShipping:
    """parse_price_with_shipping のテスト"""

    def test_shipping_included(self):
        """送料込みの場合は0を返す"""
        assert merhist.parser.parse_price_with_shipping("送料込み") == 0

    def test_shipping_included_with_other_text(self):
        """送料込みを含むテキスト"""
        assert merhist.parser.parse_price_with_shipping("配送料: 送料込み") == 0

    def test_with_number_text(self):
        """送料別の場合は数値テキストからパース"""
        assert merhist.parser.parse_price_with_shipping("配送料", "1,500") == 1500

    def test_body_text_only(self):
        """body_text のみの場合"""
        assert merhist.parser.parse_price_with_shipping("¥500") == 500

    def test_number_text_with_symbol(self):
        """number_text に記号付き"""
        assert merhist.parser.parse_price_with_shipping("配送料", "¥800") == 800
