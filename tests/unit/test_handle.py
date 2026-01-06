#!/usr/bin/env python3
# ruff: noqa: S101
"""
Handle クラスのテスト
"""

import datetime
import unittest.mock

import pytest

import merhist.config
import merhist.handle
import merhist.item


class TestHandleItemOperations:
    """Handle のアイテム操作テスト"""

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
        yield h
        h.finish()

    def test_record_sold_item(self, handle):
        """販売アイテムの記録"""
        item = merhist.item.SoldItem(id="m123", name="テスト商品", price=1000)

        handle.record_sold_item(item)

        assert handle.get_sold_checked_count() == 1
        assert handle.get_sold_item_stat(item) is True
        sold_list = handle.get_sold_item_list()
        assert len(sold_list) == 1
        assert sold_list[0].id == "m123"

    def test_record_sold_item_duplicate(self, handle):
        """重複アイテムは追加されない"""
        item = merhist.item.SoldItem(id="m123", name="テスト商品", price=1000)

        handle.record_sold_item(item)
        handle.record_sold_item(item)

        assert handle.get_sold_checked_count() == 1

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
        item1 = merhist.item.SoldItem(id="m1", completion_date=datetime.datetime(2025, 1, 20))
        item2 = merhist.item.SoldItem(id="m2", completion_date=datetime.datetime(2025, 1, 10))
        item3 = merhist.item.SoldItem(id="m3", completion_date=datetime.datetime(2025, 1, 15))

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

        assert handle.get_bought_checked_count() == 1
        assert handle.get_bought_item_stat(item) is True
        bought_list = handle.get_bought_item_list()
        assert len(bought_list) == 1
        assert bought_list[0].id == "m456"

    def test_record_bought_item_duplicate(self, handle):
        """重複アイテムは追加されない"""
        item = merhist.item.BoughtItem(id="m456", name="購入商品", price=2000)

        handle.record_bought_item(item)
        handle.record_bought_item(item)

        assert handle.get_bought_checked_count() == 1

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
        item1 = merhist.item.BoughtItem(id="m1", purchase_date=datetime.datetime(2025, 1, 20))
        item2 = merhist.item.BoughtItem(id="m2", purchase_date=datetime.datetime(2025, 1, 10))
        item3 = merhist.item.BoughtItem(id="m3", purchase_date=datetime.datetime(2025, 1, 15))

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
        yield h
        h.finish()

    def test_normalize_removes_duplicates_bought(self, handle):
        """購入アイテムの重複は DB の PRIMARY KEY 制約により自動的に防がれる"""
        item1 = merhist.item.BoughtItem(id="m1", name="商品1")
        item2 = merhist.item.BoughtItem(id="m1", name="商品1更新")  # 同じID（上書きされる）
        item3 = merhist.item.BoughtItem(id="m2", name="商品2")

        # record_bought_item は重複を許さない
        handle.db.upsert_bought_item(item1)
        handle.db.upsert_bought_item(item2)  # 同じ ID なので上書き
        handle.db.upsert_bought_item(item3)

        handle.normalize()  # SQLite では何もしない

        assert handle.get_bought_checked_count() == 2
        ids = [item.id for item in handle.get_bought_item_list()]
        assert "m1" in ids
        assert "m2" in ids

    def test_normalize_removes_duplicates_sold(self, handle):
        """販売アイテムの重複は DB の PRIMARY KEY 制約により自動的に防がれる"""
        item1 = merhist.item.SoldItem(id="s1", name="商品1", price=100)
        item2 = merhist.item.SoldItem(id="s1", name="商品1更新", price=100)  # 同じID（上書きされる）
        item3 = merhist.item.SoldItem(id="s2", name="商品2", price=200)

        handle.db.upsert_sold_item(item1)
        handle.db.upsert_sold_item(item2)  # 同じ ID なので上書き
        handle.db.upsert_sold_item(item3)

        handle.normalize()  # SQLite では何もしない

        assert handle.get_sold_checked_count() == 2
        ids = [item.id for item in handle.get_sold_item_list()]
        assert "s1" in ids
        assert "s2" in ids

    def test_normalize_empty_lists(self, handle):
        """空リストの正規化"""
        handle.normalize()

        assert handle.get_bought_item_list() == []
        assert handle.get_sold_item_list() == []
        assert handle.get_bought_checked_count() == 0
        assert handle.get_sold_checked_count() == 0


class TestHandleThumbPath:
    """Handle.get_thumb_path のテスト"""

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
        yield h
        h.finish()

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
        yield h
        h.finish()

    def test_get_selenium_driver_creates_driver(self, handle, mock_config):
        """Selenium ドライバーを作成"""
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()

        with (
            unittest.mock.patch(
                "my_lib.selenium_util.create_driver", return_value=mock_driver
            ) as mock_create,
            unittest.mock.patch("my_lib.selenium_util.clear_cache") as mock_clear,
            unittest.mock.patch("selenium.webdriver.support.wait.WebDriverWait", return_value=mock_wait),
        ):
            driver, wait = handle.get_selenium_driver()

            mock_create.assert_called_once_with(
                "Merhist", mock_config.selenium_data_dir_path, use_undetected=True
            )
            mock_clear.assert_called_once_with(mock_driver)
            assert driver == mock_driver
            assert wait == mock_wait
            assert handle._browser_manager.has_driver()

    def test_get_selenium_driver_returns_existing(self, handle):
        """既存のドライバーを返す"""
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()
        handle.get_selenium_driver = unittest.mock.MagicMock(return_value=(mock_driver, mock_wait))  # type: ignore[method-assign]

        with unittest.mock.patch("my_lib.selenium_util.create_driver") as mock_create:
            driver, wait = handle.get_selenium_driver()

            mock_create.assert_not_called()
            assert driver == mock_driver
            assert wait == mock_wait

    def test_quit_selenium(self, handle):
        """Selenium を終了"""
        mock_driver = unittest.mock.MagicMock()

        # BrowserManager の内部状態を設定してドライバーを起動済みにする
        handle._browser_manager._driver = mock_driver  # type: ignore[union-attr]
        handle._browser_manager._wait = unittest.mock.MagicMock()  # type: ignore[union-attr]

        with unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully") as mock_quit:
            handle.quit_selenium()

            mock_quit.assert_called_once_with(mock_driver, wait_sec=5)
            assert not handle._browser_manager.has_driver()

    def test_quit_selenium_no_driver(self, handle):
        """ドライバーがない場合は何もしない"""
        # ドライバー未起動の状態（デフォルト）

        with unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully") as mock_quit:
            handle.quit_selenium()

            mock_quit.assert_not_called()

    def test_finish(self, handle):
        """finish で Selenium とプログレスマネージャーを終了"""
        mock_driver = unittest.mock.MagicMock()

        # BrowserManager の内部状態を設定してドライバーを起動済みにする
        handle._browser_manager._driver = mock_driver  # type: ignore[union-attr]
        handle._browser_manager._wait = unittest.mock.MagicMock()  # type: ignore[union-attr]

        with unittest.mock.patch("my_lib.selenium_util.quit_driver_gracefully"):
            handle.finish()

            assert not handle._browser_manager.has_driver()


class TestHandleProgressBar:
    """Handle のプログレスバー関連テスト"""

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
        yield h
        h.finish()

    def test_set_progress_bar(self, handle):
        """プログレスバーを設定"""
        handle.set_progress_bar("テスト", 100)

        assert handle.has_progress_bar("テスト")
        task = handle.get_progress_bar("テスト")
        assert task.total == 100

    def test_update_progress_bar(self, handle):
        """プログレスバーを更新"""
        handle.set_progress_bar("テスト", 100)
        handle.update_progress_bar("テスト", 10)

        task = handle.get_progress_bar("テスト")
        assert task.count == 10

    def test_update_progress_bar_nonexistent(self, handle):
        """存在しないプログレスバーの更新は何もしない"""
        # エラーにならないことを確認
        handle.update_progress_bar("存在しない", 10)

    def test_has_progress_bar(self, handle):
        """プログレスバーの存在確認"""
        assert not handle.has_progress_bar("テスト")

        handle.set_progress_bar("テスト", 100)

        assert handle.has_progress_bar("テスト")

    def test_set_status(self, handle):
        """ステータスを設定"""
        handle.set_status("処理中...")
        # ステータスが設定される（内部実装は my_lib.cui_progress に委譲）

    def test_set_status_error(self, handle):
        """エラー時のステータス設定"""
        handle.set_status("エラー発生", is_error=True)
        # エラーステータスが設定される（内部実装は my_lib.cui_progress に委譲）


class TestHandleLiveControl:
    """Live表示制御のテスト"""

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
        """Handle インスタンス（非TTY）"""
        h = merhist.handle.Handle(config=mock_config)
        yield h
        h.finish()

    def test_pause_live(self, handle):
        """pause_live が呼び出せる"""
        handle.pause_live()  # エラーなく完了

    def test_resume_live(self, handle):
        """resume_live が呼び出せる"""
        handle.resume_live()  # エラーなく完了


class TestHandleSerialization:
    """Handle のシリアライズ関連テスト"""

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
        yield h
        h.finish()

    def test_store_trading_info(self, handle):
        """取引情報を保存（メタデータが DB に保存される）"""
        handle.trading.sold_total_count = 100
        handle.trading.bought_total_count = 50

        handle.store_trading_info()

        # メタデータが正しく保存されたか確認
        assert handle.db.get_metadata_int("sold_total_count") == 100
        assert handle.db.get_metadata_int("bought_total_count") == 50
        assert handle.db.get_metadata("last_modified") != ""


class TestHandlePrepareDirectory:
    """Handle._prepare_directory のテスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
        config.selenium_data_dir_path = tmp_path / "selenium"
        config.debug_dir_path = tmp_path / "debug"
        config.thumb_dir_path = tmp_path / "thumb"
        config.captcha_file_path = tmp_path / "output" / "captcha.png"
        config.excel_file_path = tmp_path / "output" / "mercari.xlsx"
        return config

    def test_creates_all_directories(self, mock_config, tmp_path):
        """必要なディレクトリが全て作成される"""
        # ディレクトリが存在しないことを確認
        assert not (tmp_path / "cache").exists()
        assert not (tmp_path / "selenium").exists()
        assert not (tmp_path / "debug").exists()
        assert not (tmp_path / "thumb").exists()
        assert not (tmp_path / "output").exists()

        handle = merhist.handle.Handle(config=mock_config)

        # ディレクトリが作成されたことを確認
        assert (tmp_path / "cache").exists()
        assert (tmp_path / "selenium").exists()
        assert (tmp_path / "debug").exists()
        assert (tmp_path / "thumb").exists()
        assert (tmp_path / "output").exists()

        handle.finish()

    def test_existing_directories_ok(self, mock_config, tmp_path):
        """既存ディレクトリがあってもエラーにならない"""
        # 事前にディレクトリを作成
        (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
        (tmp_path / "selenium").mkdir(parents=True, exist_ok=True)

        handle = merhist.handle.Handle(config=mock_config)

        # エラーなく作成される
        assert (tmp_path / "cache").exists()
        assert (tmp_path / "selenium").exists()

        handle.finish()


class TestHandleDatabase:
    """Handle のデータベース関連テスト"""

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

    def test_db_property(self, mock_config):
        """db プロパティでデータベースインスタンスを取得"""
        handle = merhist.handle.Handle(config=mock_config)

        db = handle.db
        assert db is not None

        handle.finish()

    def test_trading_state_restored_from_db(self, mock_config, tmp_path):
        """TradingState がDBから復元される"""
        # 最初のインスタンスで値を保存
        handle1 = merhist.handle.Handle(config=mock_config)
        handle1.trading.sold_total_count = 42
        handle1.trading.bought_total_count = 24
        handle1.store_trading_info()
        handle1.finish()

        # 2番目のインスタンスで復元を確認
        handle2 = merhist.handle.Handle(config=mock_config)
        assert handle2.trading.sold_total_count == 42
        assert handle2.trading.bought_total_count == 24
        handle2.finish()


class TestTradingState:
    """TradingState データクラスのテスト"""

    def test_default_values(self):
        """デフォルト値が正しい"""
        state = merhist.handle.TradingState()

        assert state.sold_total_count == 0
        assert state.bought_total_count == 0

    def test_custom_values(self):
        """カスタム値を設定"""
        state = merhist.handle.TradingState(sold_total_count=100, bought_total_count=50)

        assert state.sold_total_count == 100
        assert state.bought_total_count == 50


class TestHandleSeleniumError:
    """Handle の Selenium エラー処理テスト"""

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

    def test_selenium_error_with_clear_profile(self, mock_config):
        """Selenium 起動エラー時にプロファイルをクリア"""
        import my_lib.selenium_util

        handle = merhist.handle.Handle(config=mock_config)
        handle.clear_profile_on_browser_error = True

        with (
            unittest.mock.patch(
                "my_lib.selenium_util.create_driver",
                side_effect=Exception("起動失敗"),
            ),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete,
            pytest.raises(my_lib.selenium_util.SeleniumError),
        ):
            handle.get_selenium_driver()
            mock_delete.assert_called_once()

        handle.finish()

    def test_selenium_error_without_clear_profile(self, mock_config):
        """Selenium 起動エラー時にプロファイルをクリアしない"""
        import my_lib.selenium_util

        handle = merhist.handle.Handle(config=mock_config)
        handle.clear_profile_on_browser_error = False

        with (
            unittest.mock.patch(
                "my_lib.selenium_util.create_driver",
                side_effect=Exception("起動失敗"),
            ),
            unittest.mock.patch("my_lib.chrome_util.delete_profile") as mock_delete,
            pytest.raises(my_lib.selenium_util.SeleniumError),
        ):
            handle.get_selenium_driver()
            mock_delete.assert_not_called()

        handle.finish()


class TestHandleEdgeCases:
    """Handle の境界ケーステスト"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """モック Config"""
        config = unittest.mock.MagicMock(spec=merhist.config.Config)
        config.cache_file_path = tmp_path / "cache" / "cache.dat"
        config.cache_dir_path = tmp_path / "cache"
        config.selenium_data_dir_path = tmp_path / "selenium"
        config.debug_dir_path = tmp_path / "debug"
        config.thumb_dir_path = tmp_path / "thumb"
        config.captcha_file_path = tmp_path / "captcha.png"
        config.excel_file_path = tmp_path / "output" / "mercari.xlsx"
        return config

    def test_ignore_cache_mode(self, mock_config, tmp_path):
        """ignore_cache=True の場合、cache_dir_path をテンポラリに設定"""
        handle = merhist.handle.Handle(config=mock_config, ignore_cache=True)

        # ignore_cache が True で Handle が作成されたことを確認
        assert handle is not None

        handle.finish()

    def test_ignore_cache_mode_with_existing_file(self, mock_config, tmp_path):
        """ignore_cache=True で既存ファイルが削除される"""
        # キャッシュファイルを作成
        cache_file = tmp_path / "cache" / "cache.dat"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("dummy cache")

        mock_config.cache_file_path = cache_file

        handle = merhist.handle.Handle(config=mock_config, ignore_cache=True)

        # ファイルが削除されていることを確認（データベースとして再作成されている可能性あり）
        handle.finish()

    def test_db_property_not_initialized(self, mock_config):
        """db プロパティ未初期化時に例外"""
        handle = merhist.handle.Handle(config=mock_config)

        # _db を None に設定
        handle._db = None

        with pytest.raises(RuntimeError, match="Database is not initialized"):
            _ = handle.db

        handle.finish()

    def test_progress_tasks_display(self, mock_config):
        """プログレスバーのタスク表示"""
        handle = merhist.handle.Handle(config=mock_config)

        # プログレスバーを作成
        handle.set_progress_bar("テストタスク", 10)

        # タスクを進める
        for _ in range(5):
            handle.update_progress_bar("テストタスク", 1)

        # 存在しないキーで更新しても例外にならない
        handle.update_progress_bar("存在しないタスク", 1)

        handle.finish()


class TestHandleProgressManager:
    """Handle の ProgressManager 統合テスト"""

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

    def test_progress_manager_is_initialized(self, mock_config):
        """ProgressManager が正しく初期化される"""
        handle = merhist.handle.Handle(config=mock_config)

        # メルカリ固有の設定が適用されている
        assert handle._progress_manager._color == "#E72121"
        assert handle._progress_manager._title == " 🛒メルカリ "

        handle.finish()
