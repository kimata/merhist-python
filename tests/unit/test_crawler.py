#!/usr/bin/env python3
# ruff: noqa: S101
"""
crawler.py のテスト
"""

import datetime
import pathlib
import unittest.mock

import my_lib.graceful_shutdown
import pytest
import selenium.common.exceptions

import merhist.config
import merhist.crawler
import merhist.exceptions
import merhist.handle
import merhist.item
import merhist.parser
import merhist.xpath


class TestFetchItemDetail:
    """fetch_item_detail のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        yield h
        h.finish()

    def test_fetch_item_detail_success(self, handle):
        """正常に詳細情報を取得"""

        item = merhist.item.BoughtItem(
            id="m123",
            name="テスト商品",
            shop="mercari.com",
            price=1000,
            purchase_date=datetime.datetime(2025, 1, 1),
        )

        with (
            unittest.mock.patch("merhist.crawler._fetch_item_description") as mock_desc,
            unittest.mock.patch("merhist.crawler._fetch_item_transaction") as mock_trans,
        ):
            result = merhist.crawler._fetch_item_detail(handle, item)

            mock_desc.assert_called_once_with(handle, item)
            mock_trans.assert_called_once_with(handle, item)
            assert result.count == 1
            assert result.id == "m123"

    def test_fetch_item_detail_retry_on_error(self, handle):
        """エラー時にリトライ"""

        item = merhist.item.BoughtItem(
            id="m123",
            name="テスト商品",
            shop="mercari.com",
            price=1000,
            purchase_date=datetime.datetime(2025, 1, 1),
        )

        call_count = 0

        def mock_fetch_description(h, i):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("一時的なエラー")

        with (
            unittest.mock.patch(
                "merhist.crawler._fetch_item_description", side_effect=mock_fetch_description
            ),
            unittest.mock.patch("merhist.crawler._fetch_item_transaction"),
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
        ):
            result = merhist.crawler._fetch_item_detail(handle, item)

            assert call_count == 2
            assert result.id == "m123"

    def test_fetch_item_detail_max_retry_exceeded(self, handle):
        """最大リトライ回数を超えた場合"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")

        with (
            unittest.mock.patch(
                "merhist.crawler._fetch_item_description", side_effect=Exception("永続的なエラー")
            ),
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
        ):
            result = merhist.crawler._fetch_item_detail(handle, item)

            assert result.error == "永続的なエラー"

    def test_fetch_item_detail_debug_mode(self, handle):
        """デバッグモードでの動作"""
        handle.debug_mode = True
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com", price=1000)

        with (
            unittest.mock.patch("merhist.crawler._fetch_item_description"),
            unittest.mock.patch("merhist.crawler._fetch_item_transaction"),
            unittest.mock.patch("my_lib.pretty.format", return_value="formatted"),
        ):
            result = merhist.crawler._fetch_item_detail(handle, item)

            assert result.id == "m123"


class TestWaitForLoading:
    """wait_for_loading のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        yield h
        h.finish()

    def test_wait_for_loading_success(self, handle):
        """正常に読み込み完了を待機"""
        with unittest.mock.patch("time.sleep"):
            merhist.crawler._wait_for_loading(handle, "//div", sec=0.1)

            handle.selenium.wait.until.assert_called_once()

    def test_wait_for_loading_timeout_retry(self, handle):
        """タイムアウト時にリトライ"""
        handle.selenium.wait.until.side_effect = [
            selenium.common.exceptions.TimeoutException(),
            None,
        ]

        with unittest.mock.patch("time.sleep"):
            merhist.crawler._wait_for_loading(handle, "//div", sec=0.1, retry=True)

            assert handle.selenium.wait.until.call_count == 2
            handle.selenium.driver.refresh.assert_called_once()

    def test_wait_for_loading_timeout_no_retry(self, handle):
        """リトライなしでタイムアウト"""
        handle.selenium.wait.until.side_effect = selenium.common.exceptions.TimeoutException()

        with (
            unittest.mock.patch("time.sleep"),
            pytest.raises(selenium.common.exceptions.TimeoutException),
        ):
            merhist.crawler._wait_for_loading(handle, "//div", sec=0.1, retry=False)


class TestVisitUrl:
    """visit_url のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        yield h
        h.finish()

    def test_visit_url(self, handle):
        """URLにアクセス"""
        with unittest.mock.patch("time.sleep"):
            merhist.crawler._visit_url(handle, "https://example.com", "//div")

            handle.selenium.driver.get.assert_called_once_with("https://example.com")


class TestExecuteLogin:
    """execute_login のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
        config.selenium_data_dir_path = tmp_path / "selenium"
        config.debug_dir_path = tmp_path / "debug"
        config.thumb_dir_path = tmp_path / "thumb"
        config.captcha_file_path = tmp_path / "captcha.png"
        config.excel_file_path = tmp_path / "output" / "mercari.xlsx"
        config.login = unittest.mock.MagicMock()
        config.slack = unittest.mock.MagicMock()
        return config

    @pytest.fixture
    def handle(self, mock_config):
        """Handle インスタンス"""
        h = merhist.handle.Handle(config=mock_config)
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()
        h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
        yield h
        h.finish()

    def test_execute_login(self, handle):
        """ログイン実行"""
        with unittest.mock.patch("my_lib.store.mercari.login.execute") as mock_login:
            merhist.crawler.execute_login(handle)

            mock_login.assert_called_once()


class TestSaveThumbnail:
    """save_thumbnail のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
        config.selenium_data_dir_path = tmp_path / "selenium"
        config.debug_dir_path = tmp_path / "debug"
        config.thumb_dir_path = tmp_path / "thumb"
        config.captcha_file_path = tmp_path / "captcha.png"
        config.excel_file_path = tmp_path / "output" / "mercari.xlsx"
        return config

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        h = merhist.handle.Handle(config=mock_config)
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()
        h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
        # サムネイルディレクトリを作成
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)
        yield h
        h.finish()

    def test_save_thumbnail(self, handle):
        """サムネイル保存"""
        item = merhist.item.SoldItem(id="m123")

        mock_img_element = unittest.mock.MagicMock()
        mock_img_element.screenshot_as_png = b"fake_png_data"

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            unittest.mock.patch("PIL.Image.open"),
        ):
            handle.selenium.driver.find_element.return_value = mock_img_element

            merhist.crawler._save_thumbnail(handle, item, "https://example.com/thumb.jpg")

            handle.selenium.driver.find_element.assert_called_once()

    def test_save_thumbnail_empty_png_data(self, handle):
        """サムネイル画像データが空の場合"""
        item = merhist.item.SoldItem(id="m123")

        mock_img_element = unittest.mock.MagicMock()
        mock_img_element.screenshot_as_png = b""  # 空データ

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            pytest.raises(RuntimeError, match="サムネイル画像データが空です"),
        ):
            handle.selenium.driver.find_element.return_value = mock_img_element

            merhist.crawler._save_thumbnail(handle, item, "https://example.com/thumb.jpg")

    def test_save_thumbnail_zero_size_file(self, handle, tmp_path):
        """保存後のファイルサイズが0の場合"""
        import os

        item = merhist.item.SoldItem(id="m123")

        mock_img_element = unittest.mock.MagicMock()
        mock_img_element.screenshot_as_png = b"fake_png_data"

        # サムネイル保存先のパスを取得
        thumb_path = pathlib.Path(handle.get_thumb_path(item))
        thumb_path.parent.mkdir(parents=True, exist_ok=True)

        # 空のファイルを作成しておく
        thumb_path.touch()

        # stat をモックしてサイズを0に
        original_stat = os.stat

        def mock_stat(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            # st_size を上書きするためにnamedtupleから変換
            return os.stat_result(
                (
                    result.st_mode,
                    result.st_ino,
                    result.st_dev,
                    result.st_nlink,
                    result.st_uid,
                    result.st_gid,
                    0,
                    result.st_atime,
                    result.st_mtime,
                    result.st_ctime,
                )
            )

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            unittest.mock.patch.object(
                pathlib.Path, "stat", side_effect=lambda: unittest.mock.MagicMock(st_size=0)
            ),
            pytest.raises(RuntimeError, match="サムネイル画像のサイズが0です"),
        ):
            handle.selenium.driver.find_element.return_value = mock_img_element

            merhist.crawler._save_thumbnail(handle, item, "https://example.com/thumb.jpg")

    def test_save_thumbnail_corrupted_image(self, handle, tmp_path):
        """画像が破損している場合"""
        item = merhist.item.SoldItem(id="m123")

        mock_img_element = unittest.mock.MagicMock()
        mock_img_element.screenshot_as_png = b"fake_png_data"

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            unittest.mock.patch("PIL.Image.open") as mock_image_open,
            pytest.raises(RuntimeError, match="サムネイル画像が破損しています"),
        ):
            handle.selenium.driver.find_element.return_value = mock_img_element
            # verify() で例外を発生させる
            mock_img = unittest.mock.MagicMock()
            mock_img.verify.side_effect = Exception("Invalid image")
            mock_img.__enter__ = unittest.mock.MagicMock(return_value=mock_img)
            mock_img.__exit__ = unittest.mock.MagicMock(return_value=False)
            mock_image_open.return_value = mock_img

            merhist.crawler._save_thumbnail(handle, item, "https://example.com/thumb.jpg")


class TestFetchItemTransaction:
    """fetch_item_transaction のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        yield h
        h.finish()

    def test_fetch_item_transaction_normal(self, handle):
        """通常アイテムのトランザクション取得"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        with unittest.mock.patch("merhist.crawler._fetch_item_transaction_normal") as mock_normal:
            merhist.crawler._fetch_item_transaction(handle, item)

            mock_normal.assert_called_once_with(handle, item)

    def test_fetch_item_transaction_shop(self, handle):
        """Shopsアイテムのトランザクション取得"""
        item = merhist.item.BoughtItem(id="abc123", shop="mercari-shops.com")

        with unittest.mock.patch("merhist.crawler._fetch_item_transaction_shop") as mock_shop:
            merhist.crawler._fetch_item_transaction(handle, item)

            mock_shop.assert_called_once_with(handle, item)


class TestFetchSoldItemList:
    """fetch_sold_item_list のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        h.progress_manager = unittest.mock.MagicMock()  # type: ignore[attr-defined]
        yield h
        h.finish()

    def test_fetch_sold_item_list_no_items(self, handle):
        """販売アイテムなし"""
        handle.trading.sold_total_count = 0

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 0
        mock_counter.count = 0
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        with unittest.mock.patch("merhist.crawler._fetch_sold_count") as mock_count:
            mock_count.side_effect = lambda h: setattr(h.trading, "sold_total_count", 0)

            merhist.crawler._fetch_sold_item_list(handle, continue_mode=True)

            mock_count.assert_called_once()

    def test_fetch_sold_item_list_already_cached(self, handle):
        """既にキャッシュ済み"""
        # DB に 10 件のアイテムを追加してキャッシュ済み状態をシミュレート
        for i in range(10):
            item = merhist.item.SoldItem(id=f"s{i}", name=f"商品{i}", price=100)
            handle.db.upsert_sold_item(item)
        handle.trading.sold_total_count = 10

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 10
        mock_counter.count = 10
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        with (
            unittest.mock.patch("merhist.crawler._fetch_sold_count"),
            unittest.mock.patch("merhist.crawler._fetch_sold_item_list_by_page") as mock_fetch_page,
        ):
            merhist.crawler._fetch_sold_item_list(handle, continue_mode=True)

            # 全てキャッシュ済みなのでページ取得は呼ばれない
            mock_fetch_page.assert_not_called()


class TestFetchBoughtItemInfoList:
    """fetch_bought_item_info_list のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        yield h
        h.finish()

    def test_fetch_bought_item_info_list_success(self, handle):
        """正常に購入履歴取得"""
        with (
            unittest.mock.patch(
                "merhist.crawler._fetch_bought_item_info_list_impl", return_value=[]
            ) as mock_impl,
        ):
            result = merhist.crawler._fetch_bought_item_info_list(handle, continue_mode=True)

            mock_impl.assert_called_once()
            assert result == []

    def test_fetch_bought_item_info_list_retry(self, handle):
        """リトライ動作"""
        call_count = 0

        def mock_impl(h, c):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("一時的エラー")
            return []

        with (
            unittest.mock.patch("merhist.crawler._fetch_bought_item_info_list_impl", side_effect=mock_impl),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler._fetch_bought_item_info_list(handle, continue_mode=True)

            assert call_count == 2
            assert result == []

    def test_fetch_bought_item_info_list_max_retry(self, handle):
        """最大リトライ回数超過"""
        with (
            unittest.mock.patch(
                "merhist.crawler._fetch_bought_item_info_list_impl", side_effect=Exception("永続的エラー")
            ),
            unittest.mock.patch("time.sleep"),
            pytest.raises(Exception, match="永続的エラー"),
        ):
            merhist.crawler._fetch_bought_item_info_list(handle, continue_mode=True)


class TestFetchBoughtItemList:
    """fetch_bought_item_list のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        h.progress_manager = unittest.mock.MagicMock()  # type: ignore[attr-defined]
        yield h
        h.finish()

    def test_fetch_bought_item_list_empty(self, handle):
        """購入履歴なし"""
        mock_counter = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        with unittest.mock.patch("merhist.crawler._fetch_bought_item_info_list", return_value=[]):
            merhist.crawler._fetch_bought_item_list(handle, continue_mode=True)

    def test_fetch_bought_item_list_with_items(self, handle):
        """購入履歴あり"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")

        mock_counter = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        with (
            unittest.mock.patch("merhist.crawler._fetch_bought_item_info_list", return_value=[item]),
            unittest.mock.patch("merhist.crawler._fetch_item_detail", return_value=item) as mock_detail,
        ):
            merhist.crawler._fetch_bought_item_list(handle, continue_mode=True)

            mock_detail.assert_called_once()
            assert handle.get_bought_checked_count() == 1

    def test_fetch_bought_item_list_cached(self, handle):
        """キャッシュ済みアイテムはスキップ"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")
        # DB に直接アイテムを追加してキャッシュ済み状態をシミュレート
        handle.db.upsert_bought_item(item)

        mock_counter = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        with (
            unittest.mock.patch("merhist.crawler._fetch_bought_item_info_list", return_value=[item]),
            unittest.mock.patch("merhist.crawler._fetch_item_detail") as mock_detail,
        ):
            merhist.crawler._fetch_bought_item_list(handle, continue_mode=True)

            # キャッシュ済みなので詳細取得は呼ばれない
            mock_detail.assert_not_called()


class TestFetchOrderItemList:
    """fetch_order_item_list のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        h.progress_manager = unittest.mock.MagicMock()  # type: ignore[attr-defined]
        yield h
        h.finish()

    def test_fetch_order_item_list(self, handle):
        """注文履歴取得"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.crawler._fetch_sold_item_list") as mock_sold,
            unittest.mock.patch("merhist.crawler._fetch_bought_item_list") as mock_bought,
        ):
            merhist.crawler.fetch_order_item_list(handle, continue_mode)

            mock_sold.assert_called_once_with(handle, True)
            mock_bought.assert_called_once_with(handle, True)

    def test_fetch_order_item_list_force_mode(self, handle):
        """強制取得モード"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": False, "sold": False}

        with (
            unittest.mock.patch("merhist.crawler._fetch_sold_item_list") as mock_sold,
            unittest.mock.patch("merhist.crawler._fetch_bought_item_list") as mock_bought,
        ):
            merhist.crawler.fetch_order_item_list(handle, continue_mode)

            mock_sold.assert_called_once_with(handle, False)
            mock_bought.assert_called_once_with(handle, False)


class TestShutdownControl:
    """シャットダウン制御関数のテスト"""

    def test_is_shutdown_requested_initial(self):
        """初期状態では False"""
        my_lib.graceful_shutdown.reset_shutdown_flag()
        assert merhist.crawler.is_shutdown_requested() is False

    def test_reset_shutdown_flag(self):
        """フラグリセット"""
        # フラグを True に設定してからリセット
        my_lib.graceful_shutdown.request_shutdown()
        assert merhist.crawler.is_shutdown_requested() is True

        my_lib.graceful_shutdown.reset_shutdown_flag()
        assert merhist.crawler.is_shutdown_requested() is False

    def test_setup_signal_handler(self):
        """シグナルハンドラの設定"""
        # 例外が発生しないことを確認
        my_lib.graceful_shutdown.setup_signal_handler()


class TestFetchItemDescription:
    """fetch_item_description のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        yield h
        h.finish()

    def test_fetch_item_description_not_found(self, handle):
        """商品ページが見つからない場合"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            unittest.mock.patch("merhist.crawler._wait_for_loading"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", side_effect=[True, False]),
        ):
            merhist.crawler._fetch_item_description(handle, item)

            assert item.error == "商品情報ページが見つかりませんでした．"

    def test_fetch_item_description_deleted(self, handle):
        """商品ページが削除されている場合"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            unittest.mock.patch("merhist.crawler._wait_for_loading"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", side_effect=[False, True]),
        ):
            merhist.crawler._fetch_item_description(handle, item)

            assert item.error == "商品情報ページが削除されています．"

    def test_fetch_item_description_success(self, handle):
        """正常に商品説明を取得"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        # モック要素を作成
        mock_row_title = unittest.mock.MagicMock()
        mock_row_title.text = "商品の状態"
        mock_row_body = unittest.mock.MagicMock()
        mock_row_body.text = "新品、未使用"

        def find_element_side_effect(by, xpath):
            if "title" in xpath.lower() or "dt" in xpath.lower():
                return mock_row_title
            return mock_row_body

        handle.selenium.driver.find_elements.return_value = [unittest.mock.MagicMock()]  # 1行
        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            unittest.mock.patch("merhist.crawler._wait_for_loading"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),
        ):
            merhist.crawler._fetch_item_description(handle, item)

            assert item.condition == "新品、未使用"

    def test_fetch_item_description_category(self, handle):
        """カテゴリー情報を取得"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        # モック要素を作成
        mock_row_title = unittest.mock.MagicMock()
        mock_row_title.text = "カテゴリー"

        # カテゴリーのパンくずリスト
        mock_breadcrumb1 = unittest.mock.MagicMock()
        mock_breadcrumb1.text = "家電"
        mock_breadcrumb2 = unittest.mock.MagicMock()
        mock_breadcrumb2.text = "スマートフォン"

        def find_element_side_effect(by, xpath):
            return mock_row_title

        def find_elements_side_effect(by, xpath):
            if "a" in xpath.lower() or "link" in xpath.lower():
                return [mock_breadcrumb1, mock_breadcrumb2]
            return [unittest.mock.MagicMock()]  # 1行

        handle.selenium.driver.find_elements.side_effect = find_elements_side_effect
        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            unittest.mock.patch("merhist.crawler._wait_for_loading"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),
        ):
            merhist.crawler._fetch_item_description(handle, item)

            assert item.category == ["家電", "スマートフォン"]


class TestFetchItemTransactionNormal:
    """fetch_item_transaction_normal のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        yield h
        h.finish()

    def test_fetch_item_transaction_normal_page_error(self, handle):
        """ページエラーの場合"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")
        handle.selenium.driver.current_url = "https://example.com/error"

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=True),
            pytest.raises(merhist.exceptions.PageLoadError),
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

    def test_fetch_item_transaction_normal_no_purchase_date(self, handle):
        """購入日時がない場合"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        # 空のリストを返す（行がない）
        handle.selenium.driver.find_elements.return_value = []

        # サムネイル用モック
        mock_thumb = unittest.mock.MagicMock()
        mock_thumb.get_attribute.return_value = None
        handle.selenium.driver.find_element.return_value = mock_thumb

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),
            pytest.raises(merhist.exceptions.InvalidPageFormatError),
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

    def test_fetch_item_transaction_normal_success(self, handle, tmp_path):
        """正常に取引情報を取得"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        # サムネイルディレクトリを作成
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)

        # 情報行のモック
        mock_row = unittest.mock.MagicMock()

        # タイトルと本文のモック
        mock_title = unittest.mock.MagicMock()
        mock_title.text = "購入日時"
        mock_body_span = unittest.mock.MagicMock()
        mock_body_span.text = "2024年1月15日 10:30"
        mock_thumb_elem = unittest.mock.MagicMock()
        mock_thumb_elem.get_attribute.return_value = None  # サムネイルなし

        call_count = 0

        def find_element_side_effect(by, xpath):
            nonlocal call_count
            call_count += 1
            if "thumbnail" in xpath.lower() or "img" in xpath.lower():
                return mock_thumb_elem
            if "title" in xpath.lower() or "dt" in xpath.lower():
                return mock_title
            return mock_body_span

        handle.selenium.driver.find_elements.return_value = [mock_row]  # 1行
        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),
            unittest.mock.patch("merhist.parser.parse_datetime", return_value="2024-01-15 10:30:00"),
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

            assert item.purchase_date == "2024-01-15 10:30:00"

    def test_fetch_item_transaction_normal_with_thumbnail(self, handle, tmp_path):
        """サムネイル付きで取引情報を取得"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        # サムネイルディレクトリを作成
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)

        # 情報行のモック
        mock_row = unittest.mock.MagicMock()
        mock_title = unittest.mock.MagicMock()
        mock_title.text = "購入日時"
        mock_body_span = unittest.mock.MagicMock()
        mock_body_span.text = "2024年1月15日 10:30"
        mock_thumb_elem = unittest.mock.MagicMock()
        mock_thumb_elem.get_attribute.return_value = "https://example.com/thumb.jpg"

        def find_element_side_effect(by, xpath):
            if "thumbnail" in xpath.lower() or "img" in xpath.lower():
                return mock_thumb_elem
            if "title" in xpath.lower() or "dt" in xpath.lower():
                return mock_title
            return mock_body_span

        handle.selenium.driver.find_elements.return_value = [mock_row]
        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),
            unittest.mock.patch("merhist.parser.parse_datetime", return_value="2024-01-15 10:30:00"),
            unittest.mock.patch("merhist.crawler._save_thumbnail") as mock_save,
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

            assert item.purchase_date == "2024-01-15 10:30:00"
            mock_save.assert_called_once()


class TestGetBoughtItemInfoList:
    """get_bought_item_info_list のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        yield h
        h.finish()

    def test_get_bought_item_info_list_offset_error(self, handle):
        """オフセットがリスト長より大きい場合"""
        handle.selenium.driver.find_elements.return_value = []  # 0件

        item_list: list[merhist.item.BoughtItem] = []

        with pytest.raises(merhist.exceptions.HistoryFetchError, match="読み込みが正常にできていません"):
            merhist.crawler._get_bought_item_info_list(handle, page=1, offset=1, item_list=item_list)

    def test_get_bought_item_info_list_empty(self, handle):
        """空リスト"""
        handle.selenium.driver.find_elements.return_value = []

        item_list: list[merhist.item.BoughtItem] = []
        list_length, is_found_new = merhist.crawler._get_bought_item_info_list(
            handle, page=1, offset=0, item_list=item_list
        )

        assert list_length == 0
        assert is_found_new is False
        assert item_list == []

    def test_get_bought_item_info_list_with_items(self, handle):
        """アイテムがある場合"""

        # モック要素を作成
        mock_item_elem = unittest.mock.MagicMock()
        handle.selenium.driver.find_elements.return_value = [mock_item_elem]

        # find_element のモック
        mock_name = unittest.mock.MagicMock()
        mock_name.text = "テスト商品"
        mock_link = unittest.mock.MagicMock()
        mock_link.get_attribute.return_value = "https://jp.mercari.com/transaction/m12345"
        mock_datetime = unittest.mock.MagicMock()
        mock_datetime.text = "2025/01/15 10:30"

        def find_element_side_effect(by, xpath):
            if merhist.xpath.BOUGHT_ITEM_LABEL in xpath:
                return mock_name
            elif merhist.xpath.BOUGHT_ITEM_LINK in xpath:
                return mock_link
            elif merhist.xpath.BOUGHT_ITEM_DATETIME in xpath:
                return mock_datetime
            return mock_name

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        item_list: list[merhist.item.BoughtItem] = []  # type: ignore[name-defined]
        list_length, is_found_new = merhist.crawler._get_bought_item_info_list(  # type: ignore[attr-defined]
            handle, page=1, offset=0, item_list=item_list, continue_mode=True
        )

        assert list_length == 1
        assert is_found_new is True
        assert len(item_list) == 1
        assert item_list[0].name == "テスト商品"
        assert item_list[0].id == "m12345"

    def test_get_bought_item_info_list_cached_continue_mode(self, handle):
        """continue_mode でキャッシュ済みの場合はスキップ"""

        # DBにキャッシュを追加
        cached_item = merhist.item.BoughtItem(id="m12345", name="キャッシュ済み")  # type: ignore[attr-defined]
        handle.db.upsert_bought_item(cached_item)

        # モック要素
        mock_item_elem = unittest.mock.MagicMock()
        handle.selenium.driver.find_elements.return_value = [mock_item_elem]

        mock_name = unittest.mock.MagicMock()
        mock_name.text = "テスト商品"
        mock_link = unittest.mock.MagicMock()
        mock_link.get_attribute.return_value = "https://jp.mercari.com/transaction/m12345"
        mock_datetime = unittest.mock.MagicMock()
        mock_datetime.text = "2025/01/15 10:30"

        def find_element_side_effect(by, xpath):
            if merhist.xpath.BOUGHT_ITEM_LABEL in xpath:
                return mock_name
            elif merhist.xpath.BOUGHT_ITEM_LINK in xpath:
                return mock_link
            elif merhist.xpath.BOUGHT_ITEM_DATETIME in xpath:
                return mock_datetime
            return mock_name

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        item_list: list[merhist.item.BoughtItem] = []  # type: ignore[name-defined]
        list_length, is_found_new = merhist.crawler._get_bought_item_info_list(  # type: ignore[attr-defined]
            handle, page=1, offset=0, item_list=item_list, continue_mode=True
        )

        # キャッシュ済みなので is_found_new は False、リストにも追加されない
        assert list_length == 1
        assert is_found_new is False
        assert len(item_list) == 0


class TestFetchSoldCount:
    """fetch_sold_count のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        yield h
        h.finish()

    def test_fetch_sold_count(self, handle):
        """販売件数取得"""
        mock_paging = unittest.mock.MagicMock()
        mock_paging.text = "1～20/全42件"  # parse_sold_count が期待するフォーマット
        handle.selenium.driver.find_element.return_value = mock_paging

        with unittest.mock.patch("merhist.crawler._visit_url"):
            merhist.crawler._fetch_sold_count(handle)

            assert handle.trading.sold_total_count == 42


class TestContinueModeTypedDict:
    """ContinueMode TypedDict のテスト"""

    def test_continue_mode_creation(self):
        """ContinueMode の作成"""
        mode: merhist.crawler.ContinueMode = {"bought": True, "sold": False}

        assert mode["bought"] is True
        assert mode["sold"] is False


class TestConstantsAndUrls:
    """定数と URL 生成のテスト"""

    def test_mercari_normal_constant(self):
        """MERCARI_NORMAL 定数"""
        assert merhist.crawler._MERCARI_NORMAL == "mercari.com"

    def test_mercari_shop_constant(self):
        """MERCARI_SHOP 定数"""
        assert merhist.crawler._MERCARI_SHOP == "mercari-shops.com"

    def test_status_constants(self):
        """ステータス定数"""
        assert merhist.crawler._STATUS_SOLD_PAGE == "[収集] 販売ページ"
        assert merhist.crawler._STATUS_SOLD_ITEM == "[収集] 販売商品"
        assert merhist.crawler._STATUS_BOUGHT_ITEM == "[収集] 購入商品"

    def test_retry_constants(self):
        """リトライ定数"""
        assert merhist.crawler._FETCH_RETRY_COUNT == 3


class TestFetchItemTransactionShop:
    """_fetch_item_transaction_shop のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
        config.selenium_data_dir_path = tmp_path / "selenium"
        config.debug_dir_path = tmp_path / "debug"
        config.thumb_dir_path = tmp_path / "thumb"
        config.captcha_file_path = tmp_path / "captcha.png"
        config.excel_file_path = tmp_path / "output" / "mercari.xlsx"
        return config

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        h = merhist.handle.Handle(config=mock_config)
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()
        h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)
        yield h
        h.finish()

    def test_fetch_item_transaction_shop_success(self, handle):
        """メルカリショップ取引の取得成功"""

        item = merhist.item.BoughtItem(id="abc123", shop="mercari-shops.com")

        # 価格要素のモック
        mock_price_elem = unittest.mock.MagicMock()
        mock_price_elem.text = "￥1,500"
        # サムネイル要素のモック
        mock_thumb_elem = unittest.mock.MagicMock()
        mock_thumb_elem.get_attribute.return_value = "https://example.com/shop-thumb.jpg"

        def find_element_side_effect(by, xpath):
            if merhist.xpath.SHOP_TRANSACTION_PRICE in xpath:
                return mock_price_elem
            if merhist.xpath.SHOP_TRANSACTION_THUMBNAIL in xpath:
                return mock_thumb_elem
            return mock_price_elem

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.crawler._save_thumbnail") as mock_save,
        ):
            merhist.crawler._fetch_item_transaction_shop(handle, item)

            assert item.price == 1500
            mock_save.assert_called_once()

    def test_fetch_item_transaction_shop_no_thumbnail(self, handle):
        """サムネイルなしのメルカリショップ取引"""

        item = merhist.item.BoughtItem(id="abc123", shop="mercari-shops.com")

        mock_price_elem = unittest.mock.MagicMock()
        mock_price_elem.text = "￥2,000"
        mock_thumb_elem = unittest.mock.MagicMock()
        mock_thumb_elem.get_attribute.return_value = None  # サムネイルなし

        def find_element_side_effect(by, xpath):
            if merhist.xpath.SHOP_TRANSACTION_PRICE in xpath:
                return mock_price_elem
            if merhist.xpath.SHOP_TRANSACTION_THUMBNAIL in xpath:
                return mock_thumb_elem
            return mock_price_elem

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.crawler._save_thumbnail") as mock_save,
        ):
            merhist.crawler._fetch_item_transaction_shop(handle, item)

            assert item.price == 2000
            mock_save.assert_not_called()


class TestFetchItemTransactionNormalPriceParsing:
    """価格パース処理（送料あり/なし）のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
        config.selenium_data_dir_path = tmp_path / "selenium"
        config.debug_dir_path = tmp_path / "debug"
        config.thumb_dir_path = tmp_path / "thumb"
        config.captcha_file_path = tmp_path / "captcha.png"
        config.excel_file_path = tmp_path / "output" / "mercari.xlsx"
        return config

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        h = merhist.handle.Handle(config=mock_config)
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()
        h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
        (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)
        yield h
        h.finish()

    def test_fetch_item_transaction_normal_price_with_shipping(self, handle):
        """送料込みの価格パース"""

        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        # 情報行のモック（購入日時と価格）
        mock_date_row = unittest.mock.MagicMock()
        mock_price_row = unittest.mock.MagicMock()

        # 要素モック
        mock_title = unittest.mock.MagicMock()
        mock_title.text = "購入日時"  # デフォルトは購入日時
        mock_body_span = unittest.mock.MagicMock()
        mock_body_span.text = "2024年1月15日 10:30"
        mock_body = unittest.mock.MagicMock()
        mock_body.text = "1,000円（送料込み）"
        mock_body.find_element.return_value = unittest.mock.MagicMock(text="1,000")
        mock_thumb = unittest.mock.MagicMock()
        mock_thumb.get_attribute.return_value = None

        call_count = [0]

        def find_elements_side_effect(by, xpath):
            if merhist.xpath.TRANSACTION_INFO_ROW in xpath:
                return [mock_date_row, mock_price_row]
            return []

        def find_element_side_effect(by, xpath):
            if merhist.xpath.TRANSACTION_THUMBNAIL in xpath:
                return mock_thumb
            if merhist.xpath.TRANSACTION_ROW_TITLE in xpath:
                call_count[0] += 1
                if call_count[0] == 1:
                    mock_title.text = "購入日時"
                else:
                    mock_title.text = "商品代金"
                return mock_title
            if merhist.xpath.TRANSACTION_ROW_BODY_SPAN in xpath:
                return mock_body_span
            if merhist.xpath.TRANSACTION_ROW_BODY in xpath:
                return mock_body
            return mock_thumb

        handle.selenium.driver.find_elements.side_effect = find_elements_side_effect
        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),
            unittest.mock.patch("merhist.parser.parse_datetime", return_value="2024-01-15 10:30:00"),
            unittest.mock.patch("merhist.parser.parse_price_with_shipping", return_value=1000),
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

            assert item.purchase_date is not None

    def test_fetch_item_transaction_normal_price_separate_shipping(self, handle):
        """送料別の価格パース"""

        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        # 情報行のモック（購入日時と価格）
        mock_date_row = unittest.mock.MagicMock()
        mock_price_row = unittest.mock.MagicMock()

        # 要素モック
        mock_title = unittest.mock.MagicMock()
        mock_body_span = unittest.mock.MagicMock()
        mock_body_span.text = "2024年1月15日 10:30"
        mock_body = unittest.mock.MagicMock()
        mock_body.text = "1,000円"  # 送料込みではない
        mock_number = unittest.mock.MagicMock()
        mock_number.text = "1,000"
        mock_body.find_element.return_value = mock_number
        mock_thumb = unittest.mock.MagicMock()
        mock_thumb.get_attribute.return_value = None

        call_count = [0]

        def find_elements_side_effect(by, xpath):
            if merhist.xpath.TRANSACTION_INFO_ROW in xpath:
                return [mock_date_row, mock_price_row]
            return []

        def find_element_side_effect(by, xpath):
            if merhist.xpath.TRANSACTION_THUMBNAIL in xpath:
                return mock_thumb
            if merhist.xpath.TRANSACTION_ROW_TITLE in xpath:
                call_count[0] += 1
                if call_count[0] == 1:
                    mock_title.text = "購入日時"
                else:
                    mock_title.text = "商品代金"
                return mock_title
            if merhist.xpath.TRANSACTION_ROW_BODY_SPAN in xpath:
                return mock_body_span
            if merhist.xpath.TRANSACTION_ROW_BODY in xpath:
                return mock_body
            return mock_thumb

        handle.selenium.driver.find_elements.side_effect = find_elements_side_effect
        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),
            unittest.mock.patch("merhist.parser.parse_datetime", return_value="2024-01-15 10:30:00"),
            unittest.mock.patch("merhist.parser.parse_price_with_shipping", return_value=1000) as mock_parse,
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

            assert item.purchase_date is not None
            # 送料別なので number_text が渡される
            mock_parse.assert_called()


class TestFetchSoldItemListByPage:
    """_fetch_sold_item_list_by_page のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        # モックカウンターを作成し get_progress_bar がこれを返すようにする
        mock_counter = unittest.mock.MagicMock()
        h.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]
        h.trading.sold_total_count = 10
        yield h
        h.finish()

    def test_fetch_sold_item_list_by_page_empty(self, handle):
        """空のページ"""
        handle.selenium.driver.find_elements.return_value = []

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler._fetch_sold_item_list_by_page(handle, page=1, continue_mode=True)

            assert result is False

    def test_fetch_sold_item_list_by_page_with_items(self, handle):
        """アイテムありのページ"""

        mock_row = unittest.mock.MagicMock()
        handle.selenium.driver.find_elements.return_value = [mock_row]

        # link 要素のモック
        mock_link = unittest.mock.MagicMock()
        mock_link.text = "テスト商品"
        mock_link.get_attribute.return_value = "https://jp.mercari.com/transaction/m12345"

        # 価格要素のモック
        mock_price = unittest.mock.MagicMock()
        mock_price.text = "1,000"

        # レート要素のモック
        mock_rate = unittest.mock.MagicMock()
        mock_rate.text = "10%"

        # 日付要素のモック
        mock_date = unittest.mock.MagicMock()
        mock_date.text = "2025/01/15"

        def find_element_side_effect(by, xpath):
            if merhist.xpath.SOLD_ITEM_LINK in xpath:
                return mock_link
            if merhist.xpath.SOLD_ITEM_PRICE_NUMBER in xpath:
                return mock_price
            # rate と date はカラム位置で判断（それ以外のカラム）
            return mock_date

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.crawler._fetch_item_detail") as mock_detail,
            unittest.mock.patch("merhist.parser.parse_price", return_value=1000),
            unittest.mock.patch("merhist.parser.parse_rate", return_value=10.0),
            unittest.mock.patch("merhist.parser.parse_date", return_value=datetime.date(2025, 1, 15)),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler._fetch_sold_item_list_by_page(handle, page=1, continue_mode=False)

            assert result is True
            mock_detail.assert_called_once()

    def test_fetch_sold_item_list_by_page_cached(self, handle):
        """キャッシュ済みアイテム"""

        # DB にキャッシュを追加
        cached_item = merhist.item.SoldItem(id="m12345", name="キャッシュ済み", price=1000)
        handle.db.upsert_sold_item(cached_item)

        mock_row = unittest.mock.MagicMock()
        handle.selenium.driver.find_elements.return_value = [mock_row]

        mock_link = unittest.mock.MagicMock()
        mock_link.text = "テスト商品"
        mock_link.get_attribute.return_value = "https://jp.mercari.com/transaction/m12345"
        mock_price = unittest.mock.MagicMock()
        mock_price.text = "1,000"
        mock_date = unittest.mock.MagicMock()
        mock_date.text = "2025/01/15"

        def find_element_side_effect(by, xpath):
            if merhist.xpath.SOLD_ITEM_LINK in xpath:
                return mock_link
            if merhist.xpath.SOLD_ITEM_PRICE_NUMBER in xpath:
                return mock_price
            return mock_date

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.crawler._fetch_item_detail") as mock_detail,
            unittest.mock.patch("merhist.parser.parse_price", return_value=1000),
            unittest.mock.patch("merhist.parser.parse_rate", return_value=10.0),
            unittest.mock.patch("merhist.parser.parse_date", return_value=datetime.date(2025, 1, 15)),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler._fetch_sold_item_list_by_page(handle, page=1, continue_mode=True)

            # キャッシュ済みなので詳細取得は呼ばれない
            mock_detail.assert_not_called()
            assert result is False

    def test_fetch_sold_item_list_by_page_first_fetch_error(self, handle):
        """最初のアイテム取得失敗でエラー"""

        mock_row = unittest.mock.MagicMock()
        handle.selenium.driver.find_elements.return_value = [mock_row]

        mock_link = unittest.mock.MagicMock()
        mock_link.text = "テスト商品"
        mock_link.get_attribute.return_value = "https://jp.mercari.com/transaction/m12345"
        mock_price = unittest.mock.MagicMock()
        mock_price.text = "1,000"
        mock_date = unittest.mock.MagicMock()
        mock_date.text = "2025/01/15"

        def find_element_side_effect(by, xpath):
            if merhist.xpath.SOLD_ITEM_LINK in xpath:
                return mock_link
            if merhist.xpath.SOLD_ITEM_PRICE_NUMBER in xpath:
                return mock_price
            return mock_date

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        def mock_fetch_detail(h, item):
            item.error = "取得失敗"

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.crawler._fetch_item_detail", side_effect=mock_fetch_detail),
            unittest.mock.patch("merhist.parser.parse_price", return_value=1000),
            unittest.mock.patch("merhist.parser.parse_rate", return_value=10.0),
            unittest.mock.patch("merhist.parser.parse_date", return_value=datetime.date(2025, 1, 15)),
            unittest.mock.patch("time.sleep"),
            pytest.raises(merhist.exceptions.HistoryFetchError, match="取得失敗"),
        ):
            merhist.crawler._fetch_sold_item_list_by_page(handle, page=1, continue_mode=False)

    def test_fetch_sold_item_list_by_page_debug_mode(self, handle):
        """デバッグモードでは1件のみ処理"""

        handle.debug_mode = True

        mock_row1 = unittest.mock.MagicMock()
        mock_row2 = unittest.mock.MagicMock()
        handle.selenium.driver.find_elements.return_value = [mock_row1, mock_row2]

        mock_link = unittest.mock.MagicMock()
        mock_link.text = "テスト商品"
        mock_link.get_attribute.return_value = "https://jp.mercari.com/transaction/m12345"
        mock_price = unittest.mock.MagicMock()
        mock_price.text = "1,000"
        mock_date = unittest.mock.MagicMock()
        mock_date.text = "2025/01/15"

        def find_element_side_effect(by, xpath):
            if merhist.xpath.SOLD_ITEM_LINK in xpath:
                return mock_link
            if merhist.xpath.SOLD_ITEM_PRICE_NUMBER in xpath:
                return mock_price
            return mock_date

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.crawler._fetch_item_detail") as mock_detail,
            unittest.mock.patch("merhist.parser.parse_price", return_value=1000),
            unittest.mock.patch("merhist.parser.parse_rate", return_value=10.0),
            unittest.mock.patch("merhist.parser.parse_date", return_value=datetime.date(2025, 1, 15)),
            unittest.mock.patch("time.sleep"),
        ):
            merhist.crawler._fetch_sold_item_list_by_page(handle, page=1, continue_mode=False)

            # デバッグモードなので1回のみ
            mock_detail.assert_called_once()


class TestFetchSoldItemListShutdown:
    """_fetch_sold_item_list のシャットダウン処理テスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        h.progress_manager = unittest.mock.MagicMock()  # type: ignore[attr-defined]
        yield h
        h.finish()

    def test_fetch_sold_item_list_shutdown_requested(self, handle):
        """シャットダウンリクエスト時の処理"""
        handle.trading.sold_total_count = 10

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 10
        mock_counter.count = 0
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        with (
            unittest.mock.patch("merhist.crawler._fetch_sold_count"),
            unittest.mock.patch("merhist.crawler.is_shutdown_requested", return_value=True),
        ):
            merhist.crawler._fetch_sold_item_list(handle, continue_mode=True)

            # シャットダウン時はプログレスバー更新が行われない
            # (update は呼ばれていない)

    def test_fetch_sold_item_list_pages_with_no_new_items(self, handle):
        """新しいアイテムがない場合の早期終了"""
        handle.trading.sold_total_count = 40  # 2ページ分

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 2
        mock_counter.count = 0
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        with (
            unittest.mock.patch("merhist.crawler._fetch_sold_count"),
            unittest.mock.patch("merhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch(
                "merhist.crawler._fetch_sold_item_list_by_page", return_value=False
            ) as mock_fetch,
        ):
            merhist.crawler._fetch_sold_item_list(handle, continue_mode=True)

            # 新規アイテムがないので1ページで終了
            mock_fetch.assert_called_once()

    def test_fetch_sold_item_list_multiple_pages(self, handle):
        """複数ページの取得（全ページを処理）"""
        handle.trading.sold_total_count = 40  # 2ページ分

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 2
        mock_counter.count = 0
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        with (
            unittest.mock.patch("merhist.crawler._fetch_sold_count"),
            unittest.mock.patch("merhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch(
                "merhist.crawler._fetch_sold_item_list_by_page", return_value=True
            ) as mock_fetch,
        ):
            merhist.crawler._fetch_sold_item_list(handle, continue_mode=False)

            # continue_mode=False なので全ページ取得
            assert mock_fetch.call_count == 2

    def test_fetch_sold_item_list_debug_mode_stops_after_first_page(self, handle):
        """デバッグモードでは1ページで終了"""
        handle.debug_mode = True
        handle.trading.sold_total_count = 60  # 3ページ分

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 3
        mock_counter.count = 0
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        with (
            unittest.mock.patch("merhist.crawler._fetch_sold_count"),
            unittest.mock.patch("merhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch(
                "merhist.crawler._fetch_sold_item_list_by_page", return_value=True
            ) as mock_fetch,
        ):
            merhist.crawler._fetch_sold_item_list(handle, continue_mode=False)

            # デバッグモードなので1ページで終了
            assert mock_fetch.call_count == 1


class TestFetchBoughtItemInfoListImpl:
    """_fetch_bought_item_info_list_impl のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        yield h
        h.finish()

    def test_fetch_bought_item_info_list_impl_empty(self, handle):
        """空の購入履歴"""
        handle.selenium.driver.find_elements.return_value = []

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),
        ):
            result = merhist.crawler._fetch_bought_item_info_list_impl(handle, continue_mode=True)

            assert result == []

    def test_fetch_bought_item_info_list_impl_end_of_list(self, handle):
        """リスト終端（もっと見るボタンなし）"""

        mock_item = unittest.mock.MagicMock()
        handle.selenium.driver.find_elements.return_value = [mock_item]

        mock_name = unittest.mock.MagicMock()
        mock_name.text = "テスト商品"
        mock_link = unittest.mock.MagicMock()
        mock_link.get_attribute.return_value = "https://jp.mercari.com/transaction/m12345"
        mock_datetime = unittest.mock.MagicMock()
        mock_datetime.text = "2025/01/15 10:30"

        def find_element_side_effect(by, xpath):
            if merhist.xpath.BOUGHT_ITEM_LABEL in xpath:
                return mock_name
            elif merhist.xpath.BOUGHT_ITEM_LINK in xpath:
                return mock_link
            elif merhist.xpath.BOUGHT_ITEM_DATETIME in xpath:
                return mock_datetime
            return mock_name

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),  # ボタンなし
        ):
            result = merhist.crawler._fetch_bought_item_info_list_impl(handle, continue_mode=False)

            # ボタンがないので "Detected end of list" で終了
            assert len(result) == 1

    def test_fetch_bought_item_info_list_impl_with_more_button(self, handle):
        """もっと見るボタンがある場合"""

        # 最初のページ
        mock_item = unittest.mock.MagicMock()
        handle.selenium.driver.find_elements.return_value = [mock_item]

        mock_name = unittest.mock.MagicMock()
        mock_name.text = "テスト商品"
        mock_link = unittest.mock.MagicMock()
        mock_link.get_attribute.return_value = "https://jp.mercari.com/transaction/m12345"
        mock_datetime = unittest.mock.MagicMock()
        mock_datetime.text = "2025/01/15 10:30"

        def find_element_side_effect(by, xpath):
            if merhist.xpath.BOUGHT_ITEM_LABEL in xpath:
                return mock_name
            elif merhist.xpath.BOUGHT_ITEM_LINK in xpath:
                return mock_link
            elif merhist.xpath.BOUGHT_ITEM_DATETIME in xpath:
                return mock_datetime
            return mock_name

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        # 1回目: ボタンあり、2回目: ボタンなし
        button_exists = [True, False]
        button_call_count = [0]

        def xpath_exists_side_effect(driver, xpath):
            if "more" in xpath.lower() or "button" in xpath.lower():
                result = (
                    button_exists[button_call_count[0]]
                    if button_call_count[0] < len(button_exists)
                    else False
                )
                button_call_count[0] += 1
                return result
            return False

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", side_effect=xpath_exists_side_effect),
            unittest.mock.patch("my_lib.selenium_util.click_xpath"),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler._fetch_bought_item_info_list_impl(handle, continue_mode=True)

            assert len(result) >= 1

    def test_fetch_bought_item_info_list_impl_debug_mode(self, handle):
        """デバッグモードでの動作"""
        handle.debug_mode = True

        mock_item = unittest.mock.MagicMock()
        handle.selenium.driver.find_elements.return_value = [mock_item]

        mock_name = unittest.mock.MagicMock()
        mock_name.text = "テスト商品"
        mock_link = unittest.mock.MagicMock()
        mock_link.get_attribute.return_value = "https://jp.mercari.com/transaction/m12345"
        mock_datetime = unittest.mock.MagicMock()
        mock_datetime.text = "2025/01/15 10:30"

        def find_element_side_effect(by, xpath):
            if merhist.xpath.BOUGHT_ITEM_LABEL in xpath:
                return mock_name
            elif merhist.xpath.BOUGHT_ITEM_LINK in xpath:
                return mock_link
            elif merhist.xpath.BOUGHT_ITEM_DATETIME in xpath:
                return mock_datetime
            return mock_name

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=True),  # ボタンあり
            unittest.mock.patch("my_lib.selenium_util.click_xpath"),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler._fetch_bought_item_info_list_impl(handle, continue_mode=True)

            # デバッグモードなので早期終了
            assert len(result) >= 1


class TestFetchBoughtItemListBranches:
    """_fetch_bought_item_list の分岐テスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        h.progress_manager = unittest.mock.MagicMock()  # type: ignore[attr-defined]
        yield h
        h.finish()

    def test_fetch_bought_item_list_shutdown_requested(self, handle):
        """シャットダウンリクエスト時"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")

        mock_counter = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        with (
            unittest.mock.patch("merhist.crawler._fetch_bought_item_info_list", return_value=[item]),
            unittest.mock.patch("merhist.crawler.is_shutdown_requested", return_value=True),
            unittest.mock.patch("merhist.crawler._fetch_item_detail") as mock_detail,
        ):
            merhist.crawler._fetch_bought_item_list(handle, continue_mode=True)

            # シャットダウンリクエストなので詳細取得は呼ばれない
            mock_detail.assert_not_called()

    def test_fetch_bought_item_list_first_fetch_error(self, handle):
        """最初のアイテム取得失敗"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")

        mock_counter = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        def mock_fetch_detail(h, i):
            i.error = "取得失敗"

        with (
            unittest.mock.patch("merhist.crawler._fetch_bought_item_info_list", return_value=[item]),
            unittest.mock.patch("merhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("merhist.crawler._fetch_item_detail", side_effect=mock_fetch_detail),
            pytest.raises(merhist.exceptions.HistoryFetchError, match="取得失敗"),
        ):
            merhist.crawler._fetch_bought_item_list(handle, continue_mode=True)

    def test_fetch_bought_item_list_debug_mode(self, handle):
        """デバッグモードでは1件のみ処理"""
        handle.debug_mode = True

        item1 = merhist.item.BoughtItem(id="m123", name="テスト商品1", shop="mercari.com")
        item2 = merhist.item.BoughtItem(id="m456", name="テスト商品2", shop="mercari.com")

        mock_counter = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)  # type: ignore[method-assign]

        with (
            unittest.mock.patch("merhist.crawler._fetch_bought_item_info_list", return_value=[item1, item2]),
            unittest.mock.patch("merhist.crawler.is_shutdown_requested", return_value=False),
            unittest.mock.patch("merhist.crawler._fetch_item_detail") as mock_detail,
        ):
            merhist.crawler._fetch_bought_item_list(handle, continue_mode=False)

            # デバッグモードなので1回のみ
            mock_detail.assert_called_once()


class TestFetchOrderItemListShutdown:
    """fetch_order_item_list のシャットダウン処理テスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        h.progress_manager = unittest.mock.MagicMock()  # type: ignore[attr-defined]
        yield h
        h.finish()

    def test_fetch_order_item_list_shutdown_after_sold(self, handle):
        """販売履歴取得後のシャットダウン"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("my_lib.graceful_shutdown.set_live_display"),
            unittest.mock.patch("my_lib.graceful_shutdown.setup_signal_handler"),
            unittest.mock.patch("my_lib.graceful_shutdown.reset_shutdown_flag"),
            unittest.mock.patch("merhist.crawler._fetch_sold_item_list"),
            unittest.mock.patch("merhist.crawler._fetch_bought_item_list") as mock_bought,
            unittest.mock.patch("merhist.crawler.is_shutdown_requested", return_value=True),
        ):
            merhist.crawler.fetch_order_item_list(handle, continue_mode)

            # シャットダウン後は購入履歴取得が呼ばれない
            mock_bought.assert_not_called()


class TestGetBoughtItemInfoListForceMod:
    """_get_bought_item_info_list の強制モードテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
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
        yield h
        h.finish()

    def test_get_bought_item_info_list_force_mode_adds_cached(self, handle):
        """強制モードではキャッシュ済みもリストに追加"""

        # DBにキャッシュを追加
        cached_item = merhist.item.BoughtItem(id="m12345", name="キャッシュ済み")
        handle.db.upsert_bought_item(cached_item)

        mock_item_elem = unittest.mock.MagicMock()
        handle.selenium.driver.find_elements.return_value = [mock_item_elem]

        mock_name = unittest.mock.MagicMock()
        mock_name.text = "テスト商品"
        mock_link = unittest.mock.MagicMock()
        mock_link.get_attribute.return_value = "https://jp.mercari.com/transaction/m12345"
        mock_datetime = unittest.mock.MagicMock()
        mock_datetime.text = "2025/01/15 10:30"

        def find_element_side_effect(by, xpath):
            if merhist.xpath.BOUGHT_ITEM_LABEL in xpath:
                return mock_name
            elif merhist.xpath.BOUGHT_ITEM_LINK in xpath:
                return mock_link
            elif merhist.xpath.BOUGHT_ITEM_DATETIME in xpath:
                return mock_datetime
            return mock_name

        handle.selenium.driver.find_element.side_effect = find_element_side_effect

        item_list: list[merhist.item.BoughtItem] = []
        list_length, is_found_new = merhist.crawler._get_bought_item_info_list(
            handle,
            page=1,
            offset=0,
            item_list=item_list,
            continue_mode=False,  # 強制モード
        )

        # 強制モードなのでキャッシュ済みでもリストに追加
        assert list_length == 1
        assert len(item_list) == 1  # キャッシュ済みでも追加される


class TestLoginError:
    """ログインエラーのテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
        config.selenium_data_dir_path = tmp_path / "selenium"
        config.debug_dir_path = tmp_path / "debug"
        config.thumb_dir_path = tmp_path / "thumb"
        config.captcha_file_path = tmp_path / "captcha.png"
        config.excel_file_path = tmp_path / "output" / "mercari.xlsx"
        config.login = unittest.mock.MagicMock()
        config.slack = unittest.mock.MagicMock()
        return config

    @pytest.fixture
    def handle(self, mock_config):
        """Handle インスタンス"""
        h = merhist.handle.Handle(config=mock_config)
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()
        h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
        yield h
        h.finish()

    def test_execute_login_error(self, handle):
        """ログインエラー時の例外"""
        import my_lib.store.mercari.exceptions

        with (
            unittest.mock.patch("my_lib.store.mercari.login.execute", side_effect=Exception("認証失敗")),
            pytest.raises(
                my_lib.store.mercari.exceptions.LoginError, match="メルカリへのログインに失敗しました"
            ),
        ):
            merhist.crawler.execute_login(handle)
