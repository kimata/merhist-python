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
            unittest.mock.patch("my_lib.selenium_util.create_driver", return_value=mock_driver) as mock_create,
            unittest.mock.patch("my_lib.selenium_util.clear_cache") as mock_clear,
            unittest.mock.patch("selenium.webdriver.support.wait.WebDriverWait", return_value=mock_wait),
        ):
            driver, wait = handle.get_selenium_driver()

            mock_create.assert_called_once_with(
                "Merhist", mock_config.selenium_data_dir_path, use_subprocess=False
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

    @pytest.fixture
    def handle_tty(self, mock_config):
        """TTY環境をシミュレートした Handle インスタンス"""
        with unittest.mock.patch(
            "rich.console.Console.is_terminal", new_callable=lambda: property(lambda self: True)
        ):
            h = merhist.handle.Handle(config=mock_config)
            yield h
            h.finish()

    def test_set_progress_bar(self, handle_tty):
        """プログレスバーを設定（TTY環境）"""
        handle_tty.set_progress_bar("テスト", 100)

        assert "テスト" in handle_tty.progress_bar
        assert handle_tty.progress_bar["テスト"].total == 100

        handle_tty.finish()

    def test_set_status_creates_new(self, handle):
        """ステータスを設定"""
        handle.set_status("処理中...")

        assert handle._status_text == "処理中..."
        assert handle._status_is_error is False

        handle.finish()

    def test_set_status_updates_existing(self, handle):
        """ステータスを更新"""
        handle.set_status("処理中...")
        handle.set_status("更新中...")

        assert handle._status_text == "更新中..."

        handle.finish()

    def test_set_status_error(self, handle):
        """エラー時のフラグ設定"""
        handle.set_status("エラー発生", is_error=True)

        assert handle._status_text == "エラー発生"
        assert handle._status_is_error is True

        handle.finish()


class TestRichStyleValidation:
    """rich のスタイル文字列が有効かを検証するテスト"""

    def test_status_bar_styles_are_valid(self):
        """set_status で使用するスタイル文字列が rich で有効か検証"""
        import rich.style

        # 通常時のスタイル（水色背景・黒文字）
        normal_style = merhist.handle.STATUS_STYLE_NORMAL
        # エラー時のスタイル（赤背景・白文字）
        error_style = merhist.handle.STATUS_STYLE_ERROR

        for style_str in [normal_style, error_style]:
            # スタイルが正しくパースされることを確認
            style = rich.style.Style.parse(style_str)
            assert style is not None, f"Invalid style: {style_str}"


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


class TestHandleProgressTask:
    """ProgressTask クラスのテスト"""

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

    def test_progress_task_properties(self, handle):
        """ProgressTask のプロパティ"""
        import rich.progress

        task = merhist.handle.ProgressTask(handle, rich.progress.TaskID(1), total=100)

        assert task.total == 100
        assert task.count == 0

    def test_progress_task_update(self, handle):
        """ProgressTask.update でカウントが進む"""
        import rich.progress

        task = merhist.handle.ProgressTask(handle, rich.progress.TaskID(1), total=100)

        task.update(10)
        assert task.count == 10

        task.update(5)
        assert task.count == 15


class TestHandleProgressBarNonTty:
    """非TTY環境でのプログレスバーテスト"""

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

    def test_set_progress_bar_non_tty(self, handle):
        """非TTY環境でもプログレスバーが作成される（ダミー）"""
        handle.set_progress_bar("テスト", 100)

        assert "テスト" in handle.progress_bar
        assert handle.progress_bar["テスト"].total == 100

    def test_update_progress_bar_non_tty(self, handle):
        """非TTY環境でもupdate_progress_barが動作"""
        handle.set_progress_bar("テスト", 100)

        handle.update_progress_bar("テスト", 10)

        assert handle.progress_bar["テスト"].count == 10

    def test_update_progress_bar_nonexistent(self, handle):
        """存在しないプログレスバーの更新は何もしない"""
        # エラーにならないことを確認
        handle.update_progress_bar("存在しない", 10)


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

    def test_pause_live_no_live(self, handle):
        """Live がない場合の pause_live は何もしない"""
        handle._live = None
        handle.pause_live()  # エラーにならない

    def test_resume_live_no_live(self, handle):
        """Live がない場合の resume_live は何もしない"""
        handle._live = None
        handle.resume_live()  # エラーにならない

    def test_refresh_display_no_live(self, handle):
        """Live がない場合の _refresh_display は何もしない"""
        handle._live = None
        handle._refresh_display()  # エラーにならない


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


class TestDisplayRenderable:
    """_DisplayRenderable クラスのテスト"""

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

    def test_rich_method(self, mock_config):
        """__rich__ メソッドが _create_display を呼び出す"""
        handle = merhist.handle.Handle(config=mock_config)
        renderable = merhist.handle._DisplayRenderable(handle)

        with unittest.mock.patch.object(handle, "_create_display", return_value="test") as mock_create:
            result = renderable.__rich__()
            mock_create.assert_called_once()
            assert result == "test"

        handle.finish()


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


class TestSeleniumInfo:
    """SeleniumInfo データクラスのテスト"""

    def test_creation(self):
        """インスタンス作成"""
        mock_driver = unittest.mock.MagicMock()
        mock_wait = unittest.mock.MagicMock()

        info = merhist.handle.SeleniumInfo(driver=mock_driver, wait=mock_wait)

        assert info.driver == mock_driver
        assert info.wait == mock_wait


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
            unittest.mock.patch("my_lib.selenium_util.delete_profile") as mock_delete,
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
            unittest.mock.patch("my_lib.selenium_util.delete_profile") as mock_delete,
            pytest.raises(my_lib.selenium_util.SeleniumError),
        ):
            handle.get_selenium_driver()
            mock_delete.assert_not_called()

        handle.finish()
