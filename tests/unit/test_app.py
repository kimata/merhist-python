#!/usr/bin/env python3
# ruff: noqa: S101
"""
app.py のテスト
"""

import unittest.mock

import pytest

import app
import merhist.config
import merhist.crawler
import merhist.handle


class TestExecuteFetch:
    """execute_fetch のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "order.pickle"
        config.selenium_data_dir_path = tmp_path / "selenium"
        config.debug_dir_path = tmp_path / "debug"
        config.thumb_dir_path = tmp_path / "thumb"
        config.captcha_file_path = tmp_path / "captcha.png"
        config.excel_file_path = tmp_path / "output" / "mercari.xlsx"
        return config

    @pytest.fixture
    def handle(self, mock_config):
        """Handle インスタンス"""
        h = merhist.handle.Handle(config=mock_config)
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()
        h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
        return h

    def test_execute_fetch_success(self, handle):
        """正常にフェッチ実行"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.crawler.execute_login") as mock_login,
            unittest.mock.patch("merhist.crawler.fetch_order_item_list") as mock_fetch,
        ):
            app.execute_fetch(handle, continue_mode)

            mock_login.assert_called_once_with(handle)
            mock_fetch.assert_called_once_with(handle, continue_mode)

    def test_execute_fetch_error_dumps_page(self, handle):
        """エラー時にページダンプ"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.crawler.execute_login", side_effect=Exception("ログインエラー")),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(Exception, match="ログインエラー"),
        ):
            app.execute_fetch(handle, continue_mode)

            mock_dump.assert_called_once()


class TestExecute:
    """execute のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "order.pickle"
        config.selenium_data_dir_path = tmp_path / "selenium"
        config.debug_dir_path = tmp_path / "debug"
        config.thumb_dir_path = tmp_path / "thumb"
        config.captcha_file_path = tmp_path / "captcha.png"
        config.excel_file_path = tmp_path / "output" / "mercari.xlsx"
        return config

    def test_execute_export_mode_only(self, mock_config):
        """エクスポートモードのみ"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.history.generate_table_excel") as mock_excel,
            unittest.mock.patch("app.execute_fetch") as mock_fetch,
        ):
            app.execute(mock_config, continue_mode, export_mode=True, debug_mode=True)

            mock_fetch.assert_not_called()
            mock_excel.assert_called_once()

    def test_execute_full_mode(self, mock_config):
        """フルモード（フェッチ＋エクスポート）"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.history.generate_table_excel") as mock_excel,
            unittest.mock.patch("app.execute_fetch") as mock_fetch,
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"),
        ):
            app.execute(mock_config, continue_mode, export_mode=False, debug_mode=True)

            mock_fetch.assert_called_once()
            mock_excel.assert_called_once()

    def test_execute_fetch_error_continues_to_excel(self, mock_config):
        """フェッチエラー時もExcel生成を試行"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.history.generate_table_excel") as mock_excel,
            unittest.mock.patch("app.execute_fetch", side_effect=Exception("フェッチエラー")),
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"),
        ):
            app.execute(mock_config, continue_mode, export_mode=False, debug_mode=True)

            # エラーが発生してもExcel生成は試行される
            mock_excel.assert_called_once()

    def test_execute_excel_error(self, mock_config):
        """Excel生成エラー"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch(
                "merhist.history.generate_table_excel", side_effect=Exception("Excel生成エラー")
            ),
            unittest.mock.patch("app.execute_fetch"),
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"),
        ):
            # エラーは発生しない（内部でキャッチ）
            app.execute(mock_config, continue_mode, export_mode=False, debug_mode=True)

    def test_execute_with_thumb(self, mock_config):
        """サムネイル付きで実行"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with unittest.mock.patch("merhist.history.generate_table_excel") as mock_excel:
            app.execute(mock_config, continue_mode, export_mode=True, need_thumb=True, debug_mode=True)

            # need_thumb=True で呼ばれることを確認
            call_args = mock_excel.call_args
            assert call_args[0][2] is True  # need_thumb

    def test_execute_without_thumb(self, mock_config):
        """サムネイルなしで実行"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with unittest.mock.patch("merhist.history.generate_table_excel") as mock_excel:
            app.execute(mock_config, continue_mode, export_mode=True, need_thumb=False, debug_mode=True)

            # need_thumb=False で呼ばれることを確認
            call_args = mock_excel.call_args
            assert call_args[0][2] is False  # need_thumb

    def test_execute_non_debug_mode_waits_for_input(self, mock_config):
        """非デバッグモードでは入力待ちになる"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.history.generate_table_excel"),
            unittest.mock.patch("builtins.input", return_value="") as mock_input,
        ):
            app.execute(mock_config, continue_mode, export_mode=True, debug_mode=False)

            mock_input.assert_called_once()
