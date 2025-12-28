#!/usr/bin/env python3
# ruff: noqa: S101
"""
設定パースのテスト
"""
import pathlib
import unittest.mock

import openpyxl.styles
import pytest

from merhist.config import (
    Config,
    DataConfig,
    ExcelConfig,
    ExcelFontConfig,
    LoginConfig,
    MercariCacheConfig,
    MercariDataConfig,
    OutputConfig,
)


class TestMercariCacheConfig:
    """MercariCacheConfig のテスト"""

    def test_parse(self):
        """辞書からパース"""
        data = {"order": "data/cache/order.pickle", "thumb": "data/cache/thumb"}
        config = MercariCacheConfig.parse(data)
        assert config.order == "data/cache/order.pickle"
        assert config.thumb == "data/cache/thumb"

    def test_frozen(self):
        """frozen dataclass（変更不可）"""
        config = MercariCacheConfig(order="order.pickle", thumb="thumb")
        with pytest.raises(AttributeError):
            config.order = "new_value"  # type: ignore[misc]

    def test_missing_key_raises_error(self):
        """必須キーが欠けているとエラー"""
        data = {"order": "order.pickle"}  # thumb が欠けている
        with pytest.raises(KeyError):
            MercariCacheConfig.parse(data)


class TestMercariDataConfig:
    """MercariDataConfig のテスト"""

    def test_parse(self):
        """辞書からパース"""
        data = {"cache": {"order": "order.pickle", "thumb": "thumb"}}
        config = MercariDataConfig.parse(data)
        assert config.cache.order == "order.pickle"
        assert config.cache.thumb == "thumb"


class TestDataConfig:
    """DataConfig のテスト"""

    def test_parse(self):
        """辞書からパース"""
        data = {
            "selenium": "data/selenium",
            "debug": "data/debug",
            "mercari": {"cache": {"order": "order.pickle", "thumb": "thumb"}},
        }
        config = DataConfig.parse(data)
        assert config.selenium == "data/selenium"
        assert config.debug == "data/debug"
        assert config.mercari.cache.order == "order.pickle"


class TestExcelFontConfig:
    """ExcelFontConfig のテスト"""

    def test_parse(self):
        """辞書からパース"""
        data = {"name": "BIZ UDGothic", "size": 12}
        config = ExcelFontConfig.parse(data)
        assert config.name == "BIZ UDGothic"
        assert config.size == 12

    def test_to_openpyxl_font(self):
        """openpyxl.styles.Font への変換"""
        config = ExcelFontConfig(name="Arial", size=10)
        font = config.to_openpyxl_font()
        assert isinstance(font, openpyxl.styles.Font)
        assert font.name == "Arial"
        assert font.size == 10

    def test_various_fonts(self):
        """様々なフォント設定"""
        fonts = [
            {"name": "メイリオ", "size": 11},
            {"name": "MS Gothic", "size": 9},
            {"name": "游ゴシック", "size": 14},
        ]
        for font_data in fonts:
            config = ExcelFontConfig.parse(font_data)
            font = config.to_openpyxl_font()
            assert font.name == font_data["name"]
            assert font.size == font_data["size"]


class TestExcelConfig:
    """ExcelConfig のテスト"""

    def test_parse(self):
        """辞書からパース"""
        data = {"font": {"name": "BIZ UDGothic", "size": 12}, "table": "output/mercari.xlsx"}
        config = ExcelConfig.parse(data)
        assert config.font.name == "BIZ UDGothic"
        assert config.font.size == 12
        assert config.table == "output/mercari.xlsx"


class TestOutputConfig:
    """OutputConfig のテスト"""

    def test_parse(self):
        """辞書からパース"""
        data = {
            "captcha": "output/captcha.png",
            "excel": {"font": {"name": "Arial", "size": 10}, "table": "output/result.xlsx"},
        }
        config = OutputConfig.parse(data)
        assert config.captcha == "output/captcha.png"
        assert config.excel.table == "output/result.xlsx"
        assert config.excel.font.name == "Arial"


class TestConfigPathProperties:
    """Config のパスプロパティのテスト（手動構築）"""

    @pytest.fixture
    def sample_config_data(self):
        """サンプル設定データ"""
        return {
            "selenium": "data/selenium",
            "debug": "data/debug",
            "mercari": {"cache": {"order": "cache/order.pickle", "thumb": "cache/thumb"}},
        }

    @pytest.fixture
    def sample_output_data(self):
        """サンプル出力設定データ"""
        return {
            "captcha": "output/captcha.png",
            "excel": {"font": {"name": "Arial", "size": 10}, "table": "output/mercari.xlsx"},
        }

    def test_data_config_paths(self, sample_config_data):
        """DataConfig のパス設定"""
        config = DataConfig.parse(sample_config_data)
        base = pathlib.Path("/app")

        assert base / config.selenium == pathlib.Path("/app/data/selenium")
        assert base / config.debug == pathlib.Path("/app/data/debug")
        assert base / config.mercari.cache.order == pathlib.Path("/app/cache/order.pickle")
        assert base / config.mercari.cache.thumb == pathlib.Path("/app/cache/thumb")

    def test_output_config_paths(self, sample_output_data):
        """OutputConfig のパス設定"""
        config = OutputConfig.parse(sample_output_data)
        base = pathlib.Path("/app")

        assert base / config.captcha == pathlib.Path("/app/output/captcha.png")
        assert base / config.excel.table == pathlib.Path("/app/output/mercari.xlsx")


class TestLoginConfig:
    """LoginConfig のテスト"""

    def test_parse(self):
        """辞書からパース"""
        line_config = unittest.mock.MagicMock()
        mercari_config = unittest.mock.MagicMock()

        with (
            unittest.mock.patch(
                "my_lib.store.mercari.config.parse_line_login", return_value=line_config
            ) as mock_line,
            unittest.mock.patch(
                "my_lib.store.mercari.config.parse_mercari_login", return_value=mercari_config
            ) as mock_mercari,
        ):
            data = {"line": {"user": "test"}, "mercari": {"email": "test@example.com"}}
            config = LoginConfig.parse(data)

            mock_line.assert_called_once_with({"user": "test"})
            mock_mercari.assert_called_once_with({"email": "test@example.com"})
            assert config.line == line_config
            assert config.mercari == mercari_config


class TestConfig:
    """Config のテスト"""

    @pytest.fixture
    def mock_login_config(self):
        """モック LoginConfig"""
        return unittest.mock.MagicMock()

    @pytest.fixture
    def sample_full_config_data(self):
        """完全な設定データ"""
        return {
            "base_dir": "/app",
            "login": {"line": {}, "mercari": {}},
            "data": {
                "selenium": "data/selenium",
                "debug": "data/debug",
                "mercari": {"cache": {"order": "cache/order.pickle", "thumb": "cache/thumb"}},
            },
            "output": {
                "captcha": "output/captcha.png",
                "excel": {"font": {"name": "Arial", "size": 10}, "table": "output/mercari.xlsx"},
            },
        }

    def test_load_without_slack(self, sample_full_config_data):
        """Slack設定なしでロード"""
        with (
            unittest.mock.patch(
                "my_lib.store.mercari.config.parse_line_login",
                return_value=unittest.mock.MagicMock(),
            ),
            unittest.mock.patch(
                "my_lib.store.mercari.config.parse_mercari_login",
                return_value=unittest.mock.MagicMock(),
            ),
        ):
            config = Config.load(sample_full_config_data)

            assert config.base_dir == pathlib.Path("/app")
            assert isinstance(config.data, DataConfig)
            assert isinstance(config.output, OutputConfig)

    def test_load_with_slack_captcha(self, sample_full_config_data):
        """Slack captcha設定ありでロード"""
        sample_full_config_data["slack"] = {
            "captcha": {"bot_token": "token", "channel": {"id": "C123", "name": "test"}},
        }

        with (
            unittest.mock.patch(
                "my_lib.store.mercari.config.parse_line_login",
                return_value=unittest.mock.MagicMock(),
            ),
            unittest.mock.patch(
                "my_lib.store.mercari.config.parse_mercari_login",
                return_value=unittest.mock.MagicMock(),
            ),
        ):
            config = Config.load(sample_full_config_data)
            assert config.base_dir == pathlib.Path("/app")

    def test_path_properties(self, sample_full_config_data):
        """パスプロパティのテスト"""
        with (
            unittest.mock.patch(
                "my_lib.store.mercari.config.parse_line_login",
                return_value=unittest.mock.MagicMock(),
            ),
            unittest.mock.patch(
                "my_lib.store.mercari.config.parse_mercari_login",
                return_value=unittest.mock.MagicMock(),
            ),
        ):
            config = Config.load(sample_full_config_data)

            assert config.cache_file_path == pathlib.Path("/app/cache/order.pickle")
            assert config.excel_file_path == pathlib.Path("/app/output/mercari.xlsx")
            assert config.thumb_dir_path == pathlib.Path("/app/cache/thumb")
            assert config.selenium_data_dir_path == pathlib.Path("/app/data/selenium")
            assert config.debug_dir_path == pathlib.Path("/app/data/debug")
            assert config.captcha_file_path == pathlib.Path("/app/output/captcha.png")

    def test_excel_font_property(self, sample_full_config_data):
        """excel_font プロパティのテスト"""
        with (
            unittest.mock.patch(
                "my_lib.store.mercari.config.parse_line_login",
                return_value=unittest.mock.MagicMock(),
            ),
            unittest.mock.patch(
                "my_lib.store.mercari.config.parse_mercari_login",
                return_value=unittest.mock.MagicMock(),
            ),
        ):
            config = Config.load(sample_full_config_data)
            font = config.excel_font

            assert isinstance(font, openpyxl.styles.Font)
            assert font.name == "Arial"
            assert font.size == 10
