#!/usr/bin/env python3
# ruff: noqa: S101
"""
crawler.py のテスト
"""
import unittest.mock

import pytest
import selenium.common.exceptions

import merhist.config
import merhist.crawler
import merhist.exceptions
import merhist.handle
import merhist.item


class TestFetchItemDetail:
    """fetch_item_detail のテスト"""

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
        with unittest.mock.patch("my_lib.serializer.load", return_value=merhist.handle.TradingInfo()):
            return merhist.handle.Handle(config=mock_config)

    def test_fetch_item_detail_success(self, handle):
        """正常に詳細情報を取得"""
        import datetime

        item = merhist.item.BoughtItem(
            id="m123", name="テスト商品", shop="mercari.com", price=1000,
            purchase_date=datetime.datetime(2025, 1, 1)
        )

        with (
            unittest.mock.patch("merhist.crawler.fetch_item_description") as mock_desc,
            unittest.mock.patch("merhist.crawler.fetch_item_transaction") as mock_trans,
        ):
            result = merhist.crawler.fetch_item_detail(handle, item, debug_mode=False)

            mock_desc.assert_called_once_with(handle, item)
            mock_trans.assert_called_once_with(handle, item)
            assert result.count == 1
            assert result.id == "m123"

    def test_fetch_item_detail_retry_on_error(self, handle):
        """エラー時にリトライ"""
        import datetime

        item = merhist.item.BoughtItem(
            id="m123", name="テスト商品", shop="mercari.com", price=1000,
            purchase_date=datetime.datetime(2025, 1, 1)
        )

        call_count = 0

        def mock_fetch_description(h, i):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("一時的なエラー")

        with (
            unittest.mock.patch("merhist.crawler.fetch_item_description", side_effect=mock_fetch_description),
            unittest.mock.patch("merhist.crawler.fetch_item_transaction"),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler.fetch_item_detail(handle, item, debug_mode=False)

            assert call_count == 2
            assert result.id == "m123"

    def test_fetch_item_detail_max_retry_exceeded(self, handle):
        """最大リトライ回数を超えた場合"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")

        with (
            unittest.mock.patch(
                "merhist.crawler.fetch_item_description", side_effect=Exception("永続的なエラー")
            ),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler.fetch_item_detail(handle, item, debug_mode=False)

            assert result.error == "永続的なエラー"

    def test_fetch_item_detail_debug_mode(self, handle):
        """デバッグモードでの動作"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com", price=1000)

        with (
            unittest.mock.patch("merhist.crawler.fetch_item_description"),
            unittest.mock.patch("merhist.crawler.fetch_item_transaction"),
            unittest.mock.patch("my_lib.pretty.format", return_value="formatted"),
        ):
            result = merhist.crawler.fetch_item_detail(handle, item, debug_mode=True)

            assert result.id == "m123"


class TestWaitForLoading:
    """wait_for_loading のテスト"""

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
        with unittest.mock.patch("my_lib.serializer.load", return_value=merhist.handle.TradingInfo()):
            h = merhist.handle.Handle(config=mock_config)
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            return h

    def test_wait_for_loading_success(self, handle):
        """正常に読み込み完了を待機"""
        with unittest.mock.patch("time.sleep"):
            merhist.crawler.wait_for_loading(handle, "//div", sec=0.1)

            handle.selenium.wait.until.assert_called_once()

    def test_wait_for_loading_timeout_retry(self, handle):
        """タイムアウト時にリトライ"""
        handle.selenium.wait.until.side_effect = [
            selenium.common.exceptions.TimeoutException(),
            None,
        ]

        with unittest.mock.patch("time.sleep"):
            merhist.crawler.wait_for_loading(handle, "//div", sec=0.1, retry=True)

            assert handle.selenium.wait.until.call_count == 2
            handle.selenium.driver.refresh.assert_called_once()

    def test_wait_for_loading_timeout_no_retry(self, handle):
        """リトライなしでタイムアウト"""
        handle.selenium.wait.until.side_effect = selenium.common.exceptions.TimeoutException()

        with (
            unittest.mock.patch("time.sleep"),
            pytest.raises(selenium.common.exceptions.TimeoutException),
        ):
            merhist.crawler.wait_for_loading(handle, "//div", sec=0.1, retry=False)


class TestVisitUrl:
    """visit_url のテスト"""

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
        with unittest.mock.patch("my_lib.serializer.load", return_value=merhist.handle.TradingInfo()):
            h = merhist.handle.Handle(config=mock_config)
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            return h

    def test_visit_url(self, handle):
        """URLにアクセス"""
        with unittest.mock.patch("time.sleep"):
            merhist.crawler.visit_url(handle, "https://example.com", "//div")

            handle.selenium.driver.get.assert_called_once_with("https://example.com")


class TestExecuteLogin:
    """execute_login のテスト"""

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
        config.login = unittest.mock.MagicMock()
        config.slack = unittest.mock.MagicMock()
        return config

    @pytest.fixture
    def handle(self, mock_config):
        """Handle インスタンス"""
        with unittest.mock.patch("my_lib.serializer.load", return_value=merhist.handle.TradingInfo()):
            h = merhist.handle.Handle(config=mock_config)
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            return h

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
        config.cache_file_path = tmp_path / "cache" / "order.pickle"
        config.selenium_data_dir_path = tmp_path / "selenium"
        config.debug_dir_path = tmp_path / "debug"
        config.thumb_dir_path = tmp_path / "thumb"
        config.captcha_file_path = tmp_path / "captcha.png"
        config.excel_file_path = tmp_path / "output" / "mercari.xlsx"
        return config

    @pytest.fixture
    def handle(self, mock_config, tmp_path):
        """Handle インスタンス"""
        with unittest.mock.patch("my_lib.serializer.load", return_value=merhist.handle.TradingInfo()):
            h = merhist.handle.Handle(config=mock_config)
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            # サムネイルディレクトリを作成
            (tmp_path / "thumb").mkdir(parents=True, exist_ok=True)
            return h

    def test_save_thumbnail(self, handle):
        """サムネイル保存"""
        item = merhist.item.SoldItem(id="m123")

        mock_img_element = unittest.mock.MagicMock()
        mock_img_element.screenshot_as_png = b"fake_png_data"

        with unittest.mock.patch("my_lib.selenium_util.browser_tab"):
            handle.selenium.driver.find_element.return_value = mock_img_element

            merhist.crawler.save_thumbnail(handle, item, "https://example.com/thumb.jpg")

            handle.selenium.driver.find_element.assert_called_once()


class TestFetchItemTransaction:
    """fetch_item_transaction のテスト"""

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
        with unittest.mock.patch("my_lib.serializer.load", return_value=merhist.handle.TradingInfo()):
            h = merhist.handle.Handle(config=mock_config)
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            return h

    def test_fetch_item_transaction_normal(self, handle):
        """通常アイテムのトランザクション取得"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        with unittest.mock.patch("merhist.crawler.fetch_item_transaction_normal") as mock_normal:
            merhist.crawler.fetch_item_transaction(handle, item)

            mock_normal.assert_called_once_with(handle, item)

    def test_fetch_item_transaction_shop(self, handle):
        """Shopsアイテムのトランザクション取得"""
        item = merhist.item.BoughtItem(id="abc123", shop="mercari-shops.com")

        with unittest.mock.patch("merhist.crawler.fetch_item_transaction_shop") as mock_shop:
            merhist.crawler.fetch_item_transaction(handle, item)

            mock_shop.assert_called_once_with(handle, item)


class TestFetchSoldItemList:
    """fetch_sold_item_list のテスト"""

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
        with unittest.mock.patch("my_lib.serializer.load", return_value=merhist.handle.TradingInfo()):
            h = merhist.handle.Handle(config=mock_config)
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            h.progress_manager = unittest.mock.MagicMock()
            return h

    def test_fetch_sold_item_list_no_items(self, handle):
        """販売アイテムなし"""
        handle.trading.sold_total_count = 0
        handle.trading.sold_checked_count = 0

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 0
        mock_counter.count = 0
        handle.progress_bar = {
            merhist.crawler.STATUS_SOLD_PAGE: mock_counter,
            merhist.crawler.STATUS_SOLD_ITEM: mock_counter,
        }

        with (
            unittest.mock.patch("merhist.crawler.fetch_sold_count") as mock_count,
            unittest.mock.patch("my_lib.serializer.store"),
        ):
            mock_count.side_effect = lambda h: setattr(h.trading, "sold_total_count", 0)

            merhist.crawler.fetch_sold_item_list(handle, continue_mode=True, debug_mode=False)

            mock_count.assert_called_once()

    def test_fetch_sold_item_list_already_cached(self, handle):
        """既にキャッシュ済み"""
        handle.trading.sold_total_count = 10
        handle.trading.sold_checked_count = 10

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 10
        mock_counter.count = 10
        handle.progress_bar = {
            merhist.crawler.STATUS_SOLD_PAGE: mock_counter,
            merhist.crawler.STATUS_SOLD_ITEM: mock_counter,
        }

        with (
            unittest.mock.patch("merhist.crawler.fetch_sold_count"),
            unittest.mock.patch("merhist.crawler.fetch_sold_item_list_by_page") as mock_fetch_page,
            unittest.mock.patch("my_lib.serializer.store"),
        ):
            merhist.crawler.fetch_sold_item_list(handle, continue_mode=True, debug_mode=False)

            # 全てキャッシュ済みなのでページ取得は呼ばれない
            mock_fetch_page.assert_not_called()


class TestFetchBoughtItemInfoList:
    """fetch_bought_item_info_list のテスト"""

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
        with unittest.mock.patch("my_lib.serializer.load", return_value=merhist.handle.TradingInfo()):
            h = merhist.handle.Handle(config=mock_config)
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            return h

    def test_fetch_bought_item_info_list_success(self, handle):
        """正常に購入履歴取得"""
        with (
            unittest.mock.patch(
                "merhist.crawler.fetch_bought_item_info_list_impl", return_value=[]
            ) as mock_impl,
        ):
            result = merhist.crawler.fetch_bought_item_info_list(handle, continue_mode=True, debug_mode=False)

            mock_impl.assert_called_once()
            assert result == []

    def test_fetch_bought_item_info_list_retry(self, handle):
        """リトライ動作"""
        call_count = 0

        def mock_impl(h, c, d):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("一時的エラー")
            return []

        with (
            unittest.mock.patch("merhist.crawler.fetch_bought_item_info_list_impl", side_effect=mock_impl),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler.fetch_bought_item_info_list(handle, continue_mode=True, debug_mode=False)

            assert call_count == 2
            assert result == []

    def test_fetch_bought_item_info_list_max_retry(self, handle):
        """最大リトライ回数超過"""
        with (
            unittest.mock.patch(
                "merhist.crawler.fetch_bought_item_info_list_impl", side_effect=Exception("永続的エラー")
            ),
            unittest.mock.patch("time.sleep"),
            pytest.raises(Exception, match="永続的エラー"),
        ):
            merhist.crawler.fetch_bought_item_info_list(handle, continue_mode=True, debug_mode=False)


class TestFetchBoughtItemList:
    """fetch_bought_item_list のテスト"""

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
        with unittest.mock.patch("my_lib.serializer.load", return_value=merhist.handle.TradingInfo()):
            h = merhist.handle.Handle(config=mock_config)
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            h.progress_manager = unittest.mock.MagicMock()
            return h

    def test_fetch_bought_item_list_empty(self, handle):
        """購入履歴なし"""
        mock_counter = unittest.mock.MagicMock()
        handle.progress_bar = {merhist.crawler.STATUS_BOUGHT_ITEM: mock_counter}

        with (
            unittest.mock.patch("merhist.crawler.fetch_bought_item_info_list", return_value=[]),
            unittest.mock.patch("my_lib.serializer.store"),
        ):
            merhist.crawler.fetch_bought_item_list(handle, continue_mode=True, debug_mode=False)

    def test_fetch_bought_item_list_with_items(self, handle):
        """購入履歴あり"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")

        mock_counter = unittest.mock.MagicMock()
        handle.progress_bar = {merhist.crawler.STATUS_BOUGHT_ITEM: mock_counter}

        with (
            unittest.mock.patch("merhist.crawler.fetch_bought_item_info_list", return_value=[item]),
            unittest.mock.patch("merhist.crawler.fetch_item_detail", return_value=item) as mock_detail,
            unittest.mock.patch("my_lib.serializer.store"),
        ):
            merhist.crawler.fetch_bought_item_list(handle, continue_mode=True, debug_mode=False)

            mock_detail.assert_called_once()
            assert len(handle.trading.bought_item_list) == 1

    def test_fetch_bought_item_list_cached(self, handle):
        """キャッシュ済みアイテムはスキップ"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")
        handle.trading.bought_item_id_stat["m123"] = True

        mock_counter = unittest.mock.MagicMock()
        handle.progress_bar = {merhist.crawler.STATUS_BOUGHT_ITEM: mock_counter}

        with (
            unittest.mock.patch("merhist.crawler.fetch_bought_item_info_list", return_value=[item]),
            unittest.mock.patch("merhist.crawler.fetch_item_detail") as mock_detail,
            unittest.mock.patch("my_lib.serializer.store"),
        ):
            merhist.crawler.fetch_bought_item_list(handle, continue_mode=True, debug_mode=False)

            # キャッシュ済みなので詳細取得は呼ばれない
            mock_detail.assert_not_called()


class TestFetchOrderItemList:
    """fetch_order_item_list のテスト"""

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
        with unittest.mock.patch("my_lib.serializer.load", return_value=merhist.handle.TradingInfo()):
            h = merhist.handle.Handle(config=mock_config)
            mock_driver = unittest.mock.MagicMock()
            mock_wait = unittest.mock.MagicMock()
            h.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)
            h.progress_manager = unittest.mock.MagicMock()
            return h

    def test_fetch_order_item_list(self, handle):
        """注文履歴取得"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.crawler.fetch_sold_item_list") as mock_sold,
            unittest.mock.patch("merhist.crawler.fetch_bought_item_list") as mock_bought,
        ):
            merhist.crawler.fetch_order_item_list(handle, continue_mode, debug_mode=False)

            mock_sold.assert_called_once_with(handle, True, False)
            mock_bought.assert_called_once_with(handle, True, False)

    def test_fetch_order_item_list_force_mode(self, handle):
        """強制取得モード"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": False, "sold": False}

        with (
            unittest.mock.patch("merhist.crawler.fetch_sold_item_list") as mock_sold,
            unittest.mock.patch("merhist.crawler.fetch_bought_item_list") as mock_bought,
        ):
            merhist.crawler.fetch_order_item_list(handle, continue_mode, debug_mode=False)

            mock_sold.assert_called_once_with(handle, False, False)
            mock_bought.assert_called_once_with(handle, False, False)
