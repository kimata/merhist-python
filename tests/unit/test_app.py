#!/usr/bin/env python3
# ruff: noqa: S101
"""
cli.py のテスト
"""

import unittest.mock

import pytest

import merhist.cli as app
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
        h.get_selenium_driver = unittest.mock.MagicMock(return_value=(mock_driver, mock_wait))  # type: ignore[method-assign]
        return h

    def test_execute_fetch_success(self, handle):
        """正常にフェッチ実行"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.crawler.execute_login") as mock_login,
            unittest.mock.patch("merhist.crawler.fetch_order_item_list") as mock_fetch,
        ):
            app._execute_fetch(handle, continue_mode)

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
            app._execute_fetch(handle, continue_mode)

            mock_dump.assert_called_once()

    def test_execute_fetch_invalid_session_id_exception(self, handle):
        """InvalidSessionIdException は特別扱い（ダンプなし）"""
        import selenium.common.exceptions

        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch(
                "merhist.crawler.execute_login",
                side_effect=selenium.common.exceptions.InvalidSessionIdException("セッション切れ"),
            ),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
            pytest.raises(selenium.common.exceptions.InvalidSessionIdException),
        ):
            app._execute_fetch(handle, continue_mode)

            # InvalidSessionIdException ではダンプされない
            mock_dump.assert_not_called()

    def test_execute_fetch_error_skips_dump_on_shutdown(self, handle):
        """シャットダウン要求時はダンプをスキップ"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.crawler.execute_login", side_effect=Exception("エラー")),
            unittest.mock.patch("merhist.crawler.is_shutdown_requested", return_value=True),
            unittest.mock.patch("my_lib.selenium_util.dump_page") as mock_dump,
        ):
            # シャットダウン要求時はエラーが再スローされない
            app._execute_fetch(handle, continue_mode)

            # ダンプはスキップされる
            mock_dump.assert_not_called()


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
            unittest.mock.patch("merhist.cli._execute_fetch") as mock_fetch,
        ):
            app.execute(mock_config, continue_mode, export_mode=True, debug_mode=True)

            mock_fetch.assert_not_called()
            mock_excel.assert_called_once()

    def test_execute_full_mode(self, mock_config):
        """フルモード（フェッチ＋エクスポート）"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.history.generate_table_excel") as mock_excel,
            unittest.mock.patch("merhist.cli._execute_fetch") as mock_fetch,
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
            unittest.mock.patch("merhist.cli._execute_fetch", side_effect=Exception("フェッチエラー")),
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
            unittest.mock.patch("merhist.cli._execute_fetch"),
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

    def test_execute_session_retry_on_invalid_session(self, mock_config):
        """InvalidSessionIdException でリトライ"""
        import selenium.common.exceptions

        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        call_count = 0

        def side_effect_fn(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise selenium.common.exceptions.InvalidSessionIdException("セッション切れ")
            # 2回目以降は成功

        with (
            unittest.mock.patch("merhist.history.generate_table_excel"),
            unittest.mock.patch("merhist.cli._execute_fetch", side_effect=side_effect_fn),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete,
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"),
        ):
            result = app.execute(
                mock_config,
                continue_mode,
                export_mode=False,
                debug_mode=True,
                clear_profile_on_browser_error=True,
            )

            assert result == 0
            mock_delete.assert_called_once()

    def test_execute_session_retry_max_exceeded(self, mock_config):
        """InvalidSessionIdException でリトライ上限超過"""
        import selenium.common.exceptions

        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.history.generate_table_excel"),
            unittest.mock.patch(
                "app._execute_fetch",
                side_effect=selenium.common.exceptions.InvalidSessionIdException("セッション切れ"),
            ),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete,
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"),
        ):
            result = app.execute(
                mock_config,
                continue_mode,
                export_mode=False,
                debug_mode=True,
                clear_profile_on_browser_error=True,
            )

            assert result == 1
            # リトライ回数分呼ばれる
            assert mock_delete.call_count >= 1

    def test_execute_session_error_no_retry_when_disabled(self, mock_config):
        """clear_profile_on_browser_error=False ではリトライしない"""
        import selenium.common.exceptions

        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.history.generate_table_excel"),
            unittest.mock.patch(
                "app._execute_fetch",
                side_effect=selenium.common.exceptions.InvalidSessionIdException("セッション切れ"),
            ),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete,
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"),
        ):
            result = app.execute(
                mock_config,
                continue_mode,
                export_mode=False,
                debug_mode=True,
                clear_profile_on_browser_error=False,
            )

            assert result == 1
            # プロファイル削除は呼ばれない
            mock_delete.assert_not_called()

    def test_execute_selenium_error(self, mock_config):
        """SeleniumError が発生した場合"""
        import my_lib.selenium_util

        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.history.generate_table_excel"),
            unittest.mock.patch(
                "app._execute_fetch",
                side_effect=my_lib.selenium_util.SeleniumError("Selenium エラー"),
            ),
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"),
        ):
            result = app.execute(mock_config, continue_mode, export_mode=False, debug_mode=True)

            assert result == 1

    def test_execute_login_error(self, mock_config):
        """LoginError が発生した場合"""
        import my_lib.store.mercari.exceptions

        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.history.generate_table_excel"),
            unittest.mock.patch(
                "app._execute_fetch",
                side_effect=my_lib.store.mercari.exceptions.LoginError("ログインエラー"),
            ),
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"),
        ):
            result = app.execute(mock_config, continue_mode, export_mode=False, debug_mode=True)

            assert result == 1

    def test_execute_general_error_skips_on_shutdown(self, mock_config):
        """シャットダウン要求時は一般エラーをスキップ"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.history.generate_table_excel"),
            unittest.mock.patch("merhist.cli._execute_fetch", side_effect=Exception("一般エラー")),
            unittest.mock.patch("merhist.crawler.is_shutdown_requested", return_value=True),
            unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"),
        ):
            result = app.execute(mock_config, continue_mode, export_mode=False, debug_mode=True)

            # シャットダウン要求時は正常終了扱い
            assert result == 0
