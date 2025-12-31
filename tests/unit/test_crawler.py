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
        import datetime

        item = merhist.item.BoughtItem(
            id="m123", name="テスト商品", shop="mercari.com", price=1000,
            purchase_date=datetime.datetime(2025, 1, 1)
        )

        with (
            unittest.mock.patch("merhist.crawler.fetch_item_description") as mock_desc,
            unittest.mock.patch("merhist.crawler.fetch_item_transaction") as mock_trans,
        ):
            result = merhist.crawler.fetch_item_detail(handle, item)

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
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
        ):
            result = merhist.crawler.fetch_item_detail(handle, item)

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
            unittest.mock.patch("my_lib.selenium_util.dump_page"),
        ):
            result = merhist.crawler.fetch_item_detail(handle, item)

            assert result.error == "永続的なエラー"

    def test_fetch_item_detail_debug_mode(self, handle):
        """デバッグモードでの動作"""
        handle.debug_mode = True
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com", price=1000)

        with (
            unittest.mock.patch("merhist.crawler.fetch_item_description"),
            unittest.mock.patch("merhist.crawler.fetch_item_transaction"),
            unittest.mock.patch("my_lib.pretty.format", return_value="formatted"),
        ):
            result = merhist.crawler.fetch_item_detail(handle, item)

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
            merhist.crawler.visit_url(handle, "https://example.com", "//div")

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
        h.progress_manager = unittest.mock.MagicMock()
        yield h
        h.finish()

    def test_fetch_sold_item_list_no_items(self, handle):
        """販売アイテムなし"""
        handle.trading.sold_total_count = 0

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 0
        mock_counter.count = 0
        handle.progress_bar = {
            merhist.crawler.STATUS_SOLD_PAGE: mock_counter,
            merhist.crawler.STATUS_SOLD_ITEM: mock_counter,
        }

        with unittest.mock.patch("merhist.crawler.fetch_sold_count") as mock_count:
            mock_count.side_effect = lambda h: setattr(h.trading, "sold_total_count", 0)

            merhist.crawler.fetch_sold_item_list(handle, continue_mode=True)

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
        handle.progress_bar = {
            merhist.crawler.STATUS_SOLD_PAGE: mock_counter,
            merhist.crawler.STATUS_SOLD_ITEM: mock_counter,
        }

        with (
            unittest.mock.patch("merhist.crawler.fetch_sold_count"),
            unittest.mock.patch("merhist.crawler.fetch_sold_item_list_by_page") as mock_fetch_page,
        ):
            merhist.crawler.fetch_sold_item_list(handle, continue_mode=True)

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
                "merhist.crawler.fetch_bought_item_info_list_impl", return_value=[]
            ) as mock_impl,
        ):
            result = merhist.crawler.fetch_bought_item_info_list(handle, continue_mode=True)

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
            unittest.mock.patch("merhist.crawler.fetch_bought_item_info_list_impl", side_effect=mock_impl),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler.fetch_bought_item_info_list(handle, continue_mode=True)

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
            merhist.crawler.fetch_bought_item_info_list(handle, continue_mode=True)


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
        h.progress_manager = unittest.mock.MagicMock()
        yield h
        h.finish()

    def test_fetch_bought_item_list_empty(self, handle):
        """購入履歴なし"""
        mock_counter = unittest.mock.MagicMock()
        handle.progress_bar = {merhist.crawler.STATUS_BOUGHT_ITEM: mock_counter}

        with unittest.mock.patch("merhist.crawler.fetch_bought_item_info_list", return_value=[]):
            merhist.crawler.fetch_bought_item_list(handle, continue_mode=True)

    def test_fetch_bought_item_list_with_items(self, handle):
        """購入履歴あり"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")

        mock_counter = unittest.mock.MagicMock()
        handle.progress_bar = {merhist.crawler.STATUS_BOUGHT_ITEM: mock_counter}

        with (
            unittest.mock.patch("merhist.crawler.fetch_bought_item_info_list", return_value=[item]),
            unittest.mock.patch("merhist.crawler.fetch_item_detail", return_value=item) as mock_detail,
        ):
            merhist.crawler.fetch_bought_item_list(handle, continue_mode=True)

            mock_detail.assert_called_once()
            assert handle.get_bought_checked_count() == 1

    def test_fetch_bought_item_list_cached(self, handle):
        """キャッシュ済みアイテムはスキップ"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")
        # DB に直接アイテムを追加してキャッシュ済み状態をシミュレート
        handle.db.upsert_bought_item(item)

        mock_counter = unittest.mock.MagicMock()
        handle.progress_bar = {merhist.crawler.STATUS_BOUGHT_ITEM: mock_counter}

        with (
            unittest.mock.patch("merhist.crawler.fetch_bought_item_info_list", return_value=[item]),
            unittest.mock.patch("merhist.crawler.fetch_item_detail") as mock_detail,
        ):
            merhist.crawler.fetch_bought_item_list(handle, continue_mode=True)

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
        h.progress_manager = unittest.mock.MagicMock()
        yield h
        h.finish()

    def test_fetch_order_item_list(self, handle):
        """注文履歴取得"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": True, "sold": True}

        with (
            unittest.mock.patch("merhist.crawler.fetch_sold_item_list") as mock_sold,
            unittest.mock.patch("merhist.crawler.fetch_bought_item_list") as mock_bought,
        ):
            merhist.crawler.fetch_order_item_list(handle, continue_mode)

            mock_sold.assert_called_once_with(handle, True)
            mock_bought.assert_called_once_with(handle, True)

    def test_fetch_order_item_list_force_mode(self, handle):
        """強制取得モード"""
        continue_mode: merhist.crawler.ContinueMode = {"bought": False, "sold": False}

        with (
            unittest.mock.patch("merhist.crawler.fetch_sold_item_list") as mock_sold,
            unittest.mock.patch("merhist.crawler.fetch_bought_item_list") as mock_bought,
        ):
            merhist.crawler.fetch_order_item_list(handle, continue_mode)

            mock_sold.assert_called_once_with(handle, False)
            mock_bought.assert_called_once_with(handle, False)


class TestShutdownControl:
    """シャットダウン制御関数のテスト"""

    def test_is_shutdown_requested_initial(self):
        """初期状態では False"""
        merhist.crawler.reset_shutdown_flag()
        assert merhist.crawler.is_shutdown_requested() is False

    def test_reset_shutdown_flag(self):
        """フラグリセット"""
        # 内部フラグを True に設定してからリセット
        merhist.crawler._shutdown_requested = True
        assert merhist.crawler.is_shutdown_requested() is True

        merhist.crawler.reset_shutdown_flag()
        assert merhist.crawler.is_shutdown_requested() is False

    def test_setup_signal_handler(self):
        """シグナルハンドラの設定"""
        import signal

        with unittest.mock.patch("signal.signal") as mock_signal:
            merhist.crawler.setup_signal_handler()

            mock_signal.assert_called_once_with(signal.SIGINT, merhist.crawler._signal_handler)


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
            unittest.mock.patch("merhist.crawler.wait_for_loading"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", side_effect=[True, False]),
        ):
            merhist.crawler.fetch_item_description(handle, item)

            assert item.error == "商品情報ページが見つかりませんでした．"

    def test_fetch_item_description_deleted(self, handle):
        """商品ページが削除されている場合"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        with (
            unittest.mock.patch("my_lib.selenium_util.browser_tab"),
            unittest.mock.patch("merhist.crawler.wait_for_loading"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", side_effect=[False, True]),
        ):
            merhist.crawler.fetch_item_description(handle, item)

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
            unittest.mock.patch("merhist.crawler.wait_for_loading"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),
        ):
            merhist.crawler.fetch_item_description(handle, item)

            assert item.condition == "新品、未使用"


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
            unittest.mock.patch("merhist.crawler.visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=True),
            pytest.raises(merhist.exceptions.PageLoadError),
        ):
            merhist.crawler.fetch_item_transaction_normal(handle, item)

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
            unittest.mock.patch("merhist.crawler.visit_url"),
            unittest.mock.patch("my_lib.selenium_util.xpath_exists", return_value=False),
            pytest.raises(merhist.exceptions.InvalidPageFormatError),
        ):
            merhist.crawler.fetch_item_transaction_normal(handle, item)


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
            merhist.crawler.get_bought_item_info_list(handle, page=1, offset=1, item_list=item_list)

    def test_get_bought_item_info_list_empty(self, handle):
        """空リスト"""
        handle.selenium.driver.find_elements.return_value = []

        item_list: list[merhist.item.BoughtItem] = []
        list_length, is_found_new = merhist.crawler.get_bought_item_info_list(
            handle, page=1, offset=0, item_list=item_list
        )

        assert list_length == 0
        assert is_found_new is False
        assert item_list == []

    def test_get_bought_item_info_list_with_items(self, handle):
        """アイテムがある場合"""
        import merhist.xpath

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

        item_list: list[merhist.item.BoughtItem] = []
        list_length, is_found_new = merhist.crawler.get_bought_item_info_list(
            handle, page=1, offset=0, item_list=item_list, continue_mode=True
        )

        assert list_length == 1
        assert is_found_new is True
        assert len(item_list) == 1
        assert item_list[0].name == "テスト商品"
        assert item_list[0].id == "m12345"

    def test_get_bought_item_info_list_cached_continue_mode(self, handle):
        """continue_mode でキャッシュ済みの場合はスキップ"""
        import merhist.xpath

        # DBにキャッシュを追加
        cached_item = merhist.item.BoughtItem(id="m12345", name="キャッシュ済み")
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

        item_list: list[merhist.item.BoughtItem] = []
        list_length, is_found_new = merhist.crawler.get_bought_item_info_list(
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

        with unittest.mock.patch("merhist.crawler.visit_url"):
            merhist.crawler.fetch_sold_count(handle)

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
        assert merhist.crawler.MERCARI_NORMAL == "mercari.com"

    def test_mercari_shop_constant(self):
        """MERCARI_SHOP 定数"""
        assert merhist.crawler.MERCARI_SHOP == "mercari-shops.com"

    def test_status_constants(self):
        """ステータス定数"""
        assert merhist.crawler.STATUS_SOLD_PAGE == "[収集] 販売ページ"
        assert merhist.crawler.STATUS_SOLD_ITEM == "[収集] 販売商品"
        assert merhist.crawler.STATUS_BOUGHT_ITEM == "[収集] 購入商品"

    def test_retry_constants(self):
        """リトライ定数"""
        assert merhist.crawler.LOGIN_RETRY_COUNT == 2
        assert merhist.crawler.FETCH_RETRY_COUNT == 3


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
            unittest.mock.patch(
                "my_lib.store.mercari.login.execute", side_effect=Exception("認証失敗")
            ),
            pytest.raises(my_lib.store.mercari.exceptions.LoginError, match="メルカリへのログインに失敗しました"),
        ):
            merhist.crawler.execute_login(handle)
