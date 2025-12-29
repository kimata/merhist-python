#!/usr/bin/env python3
# ruff: noqa: S101
"""
Handle クラスのテスト
"""
import datetime
import pathlib
import tempfile
import unittest.mock
import zoneinfo

import pytest

import merhist.config
import merhist.handle
import merhist.item


class TestTradingInfo:
    """TradingInfo のテスト"""

    def test_default_values(self):
        """デフォルト値"""
        info = merhist.handle.TradingInfo()

        assert info.sold_item_list == []
        assert info.sold_item_id_stat == {}
        assert info.sold_total_count == 0
        assert info.sold_checked_count == 0
        assert info.bought_item_list == []
        assert info.bought_item_id_stat == {}
        assert info.bought_total_count == 0
        assert info.bought_checked_count == 0

    def test_last_modified_default(self):
        """last_modified のデフォルト値"""
        info = merhist.handle.TradingInfo()
        assert info.last_modified.year == 1994
        assert info.last_modified.month == 7
        assert info.last_modified.day == 5


class TestHandleItemOperations:
    """Handle のアイテム操作テスト"""

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

    def test_record_sold_item(self, handle):
        """販売アイテムの記録"""
        item = merhist.item.SoldItem(id="m123", name="テスト商品", price=1000)

        handle.record_sold_item(item)

        assert len(handle.trading.sold_item_list) == 1
        assert handle.trading.sold_item_list[0].id == "m123"
        assert handle.trading.sold_item_id_stat["m123"] is True
        assert handle.trading.sold_checked_count == 1

    def test_record_sold_item_duplicate(self, handle):
        """重複アイテムは追加されない"""
        item = merhist.item.SoldItem(id="m123", name="テスト商品", price=1000)

        handle.record_sold_item(item)
        handle.record_sold_item(item)

        assert len(handle.trading.sold_item_list) == 1
        assert handle.trading.sold_checked_count == 1

    def test_get_sold_item_stat_exists(self, handle):
        """存在するアイテムの状態確認"""
        item = merhist.item.SoldItem(id="m123")
        handle.record_sold_item(item)

        assert handle.get_sold_item_stat(item) is True

    def test_get_sold_item_stat_not_exists(self, handle):
        """存在しないアイテムの状態確認"""
        item = merhist.item.SoldItem(id="m999")

        assert handle.get_sold_item_stat(item) is False

    def test_get_sold_item_list_sorted(self, handle):
        """販売アイテムリストが completion_date でソートされる"""
        item1 = merhist.item.SoldItem(
            id="m1", completion_date=datetime.datetime(2025, 1, 20)
        )
        item2 = merhist.item.SoldItem(
            id="m2", completion_date=datetime.datetime(2025, 1, 10)
        )
        item3 = merhist.item.SoldItem(
            id="m3", completion_date=datetime.datetime(2025, 1, 15)
        )

        handle.record_sold_item(item1)
        handle.record_sold_item(item2)
        handle.record_sold_item(item3)

        sorted_list = handle.get_sold_item_list()

        assert sorted_list[0].id == "m2"  # 1/10
        assert sorted_list[1].id == "m3"  # 1/15
        assert sorted_list[2].id == "m1"  # 1/20

    def test_record_bought_item(self, handle):
        """購入アイテムの記録"""
        item = merhist.item.BoughtItem(id="m456", name="購入商品", price=2000)

        handle.record_bought_item(item)

        assert len(handle.trading.bought_item_list) == 1
        assert handle.trading.bought_item_list[0].id == "m456"
        assert handle.trading.bought_item_id_stat["m456"] is True
        assert handle.trading.bought_checked_count == 1

    def test_record_bought_item_duplicate(self, handle):
        """重複アイテムは追加されない"""
        item = merhist.item.BoughtItem(id="m456", name="購入商品", price=2000)

        handle.record_bought_item(item)
        handle.record_bought_item(item)

        assert len(handle.trading.bought_item_list) == 1
        assert handle.trading.bought_checked_count == 1

    def test_get_bought_item_stat_exists(self, handle):
        """存在するアイテムの状態確認"""
        item = merhist.item.BoughtItem(id="m456")
        handle.record_bought_item(item)

        assert handle.get_bought_item_stat(item) is True

    def test_get_bought_item_stat_not_exists(self, handle):
        """存在しないアイテムの状態確認"""
        item = merhist.item.BoughtItem(id="m999")

        assert handle.get_bought_item_stat(item) is False

    def test_get_bought_item_list_sorted(self, handle):
        """購入アイテムリストが purchase_date でソートされる"""
        item1 = merhist.item.BoughtItem(
            id="m1", purchase_date=datetime.datetime(2025, 1, 20)
        )
        item2 = merhist.item.BoughtItem(
            id="m2", purchase_date=datetime.datetime(2025, 1, 10)
        )
        item3 = merhist.item.BoughtItem(
            id="m3", purchase_date=datetime.datetime(2025, 1, 15)
        )

        handle.record_bought_item(item1)
        handle.record_bought_item(item2)
        handle.record_bought_item(item3)

        sorted_list = handle.get_bought_item_list()

        assert sorted_list[0].id == "m2"  # 1/10
        assert sorted_list[1].id == "m3"  # 1/15
        assert sorted_list[2].id == "m1"  # 1/20


class TestHandleNormalize:
    """Handle.normalize のテスト"""

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

    def test_normalize_removes_duplicates_bought(self, handle):
        """購入アイテムの重複が削除される"""
        item1 = merhist.item.BoughtItem(id="m1", name="商品1")
        item2 = merhist.item.BoughtItem(id="m1", name="商品1更新")  # 同じID
        item3 = merhist.item.BoughtItem(id="m2", name="商品2")

        handle.trading.bought_item_list = [item1, item2, item3]
        handle.trading.bought_checked_count = 3

        handle.normalize()

        assert len(handle.trading.bought_item_list) == 2
        assert handle.trading.bought_checked_count == 2
        ids = [item.id for item in handle.trading.bought_item_list]
        assert "m1" in ids
        assert "m2" in ids

    def test_normalize_removes_duplicates_sold(self, handle):
        """販売アイテムの重複が削除される"""
        item1 = merhist.item.SoldItem(id="s1", name="商品1", price=100)
        item2 = merhist.item.SoldItem(id="s1", name="商品1更新", price=100)  # 同じID
        item3 = merhist.item.SoldItem(id="s2", name="商品2", price=200)

        handle.trading.sold_item_list = [item1, item2, item3]
        handle.trading.sold_checked_count = 3

        handle.normalize()

        assert len(handle.trading.sold_item_list) == 2
        assert handle.trading.sold_checked_count == 2
        ids = [item.id for item in handle.trading.sold_item_list]
        assert "s1" in ids
        assert "s2" in ids

    def test_normalize_empty_lists(self, handle):
        """空リストの正規化"""
        handle.normalize()

        assert handle.trading.bought_item_list == []
        assert handle.trading.sold_item_list == []
        assert handle.trading.bought_checked_count == 0
        assert handle.trading.sold_checked_count == 0


class TestHandleThumbPath:
    """Handle.get_thumb_path のテスト"""

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

    def test_get_thumb_path(self, handle, tmp_path):
        """サムネイルパス取得"""
        item = merhist.item.SoldItem(id="m12345")

        path = handle.get_thumb_path(item)

        assert path == tmp_path / "thumb" / "m12345.png"

    def test_get_thumb_path_shop_item(self, handle, tmp_path):
        """Shopsアイテムのサムネイルパス"""
        item = merhist.item.BoughtItem(id="abc123xyz")

        path = handle.get_thumb_path(item)

        assert path == tmp_path / "thumb" / "abc123xyz.png"


class TestHandleSelenium:
    """Handle の Selenium 関連テスト"""

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

    def test_get_selenium_driver_creates_driver(self, handle, mock_config):
        """Selenium ドライバーを作成"""
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()

        with (
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver) as mock_create,
            unittest.mock.patch("my_lib.selenium_util.clear_cache") as mock_clear,
            unittest.mock.patch("selenium.webdriver.support.wait.WebDriverWait", return_value=mock_wait),
        ):
            driver, wait = handle.get_selenium_driver()

            mock_create.assert_called_once_with(
                "Merhist", mock_config.selenium_data_dir_path, clean_profile=True
            )
            mock_clear.assert_called_once_with(mock_driver)
            assert driver == mock_driver
            assert wait == mock_wait
            assert handle.selenium is not None

    def test_get_selenium_driver_returns_existing(self, handle):
        """既存のドライバーを返す"""
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()
        handle.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)

        with unittest.mock.patch("my_lib.selenium_util.create_driver") as mock_create:
            driver, wait = handle.get_selenium_driver()

            mock_create.assert_not_called()
            assert driver == mock_driver
            assert wait == mock_wait

    def test_quit_selenium(self, handle):
        """Selenium を終了"""
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()
        handle.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)

        with unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully") as mock_quit:
            handle.quit_selenium()

            mock_quit.assert_called_once_with(mock_driver, wait_sec=5)
            assert handle.selenium is None

    def test_quit_selenium_no_driver(self, handle):
        """ドライバーがない場合は何もしない"""
        handle.selenium = None

        with unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully") as mock_quit:
            handle.quit_selenium()

            mock_quit.assert_not_called()

    def test_finish(self, handle):
        """finish で Selenium とプログレスマネージャーを終了"""
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()
        handle.selenium = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)

        with unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"):
            handle.finish()

            assert handle.selenium is None


class TestHandleProgressBar:
    """Handle のプログレスバー関連テスト"""

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
            h.progress_manager = unittest.mock.MagicMock()
            return h

    def test_set_progress_bar(self, handle):
        """プログレスバーを設定"""
        mock_counter = unittest.mock.MagicMock()
        handle.progress_manager.counter.return_value = mock_counter

        handle.set_progress_bar("テスト", 100)

        handle.progress_manager.counter.assert_called_once()
        assert handle.progress_bar["テスト"] == mock_counter

    def test_set_status_creates_new(self, handle):
        """ステータスバーを新規作成"""
        mock_status = unittest.mock.MagicMock()
        handle.progress_manager.status_bar.return_value = mock_status
        handle.status = None

        handle.set_status("処理中...")

        handle.progress_manager.status_bar.assert_called_once()
        assert handle.status == mock_status

    def test_set_status_updates_existing(self, handle):
        """既存のステータスバーを更新"""
        mock_status = unittest.mock.MagicMock()
        handle.status = mock_status

        handle.set_status("更新中...")

        mock_status.update.assert_called_once()

    def test_set_status_error(self, handle):
        """エラー時の色設定"""
        mock_status = unittest.mock.MagicMock()
        handle.progress_manager.status_bar.return_value = mock_status
        handle.status = None

        handle.set_status("エラー発生", is_error=True)

        call_kwargs = handle.progress_manager.status_bar.call_args.kwargs
        assert "red" in call_kwargs["color"]


class TestEnlightenColorValidation:
    """enlighten の色文字列が有効かを検証するテスト"""

    def test_status_bar_colors_are_valid(self):
        """set_status で使用する色文字列が blessed で解決可能か検証

        enlighten の色検証は TTY 環境でのみ動作するため、
        blessed の formatter を直接使用して検証する。
        """
        import blessed

        term = blessed.Terminal(force_styling=True)

        # 通常時の色（水色背景・黒文字）
        normal_color = "bold_black_on_bright_cyan"
        # エラー時の色（赤背景・白文字）
        error_color = "bold_bright_white_on_red"

        for color in [normal_color, error_color]:
            # formatter が有効な色を返すことを確認
            result = term.formatter(color)
            assert result, f"Invalid color: {color}"


class TestHandleSerialization:
    """Handle のシリアライズ関連テスト"""

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

    def test_store_trading_info(self, handle, mock_config):
        """取引情報を保存"""
        with unittest.mock.patch("my_lib.serializer.store") as mock_store:
            handle.store_trading_info()

            mock_store.assert_called_once_with(mock_config.cache_file_path, handle.trading)
            assert handle.trading.last_modified.year >= 2025
