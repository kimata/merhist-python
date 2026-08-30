#!/usr/bin/env python3
# ruff: noqa: S101
"""
crawler.py のテスト

ブラウザ層は my_lib.browser の Page 抽象を使用する。
Page / Element のモックは conftest の build_page / build_element ヘルパー
（make_page / make_element フィクスチャ）で組み立てる。
"""

import datetime
import pathlib
import unittest.mock

import my_lib.browser
import my_lib.graceful_shutdown
import pytest

import merhist.crawler
import merhist.exceptions
import merhist.handle
import merhist.item
import merhist.xpath


class TestFetchItemDetail:
    """fetch_item_detail のテスト"""

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
            unittest.mock.patch("my_lib.browser.helpers.dump_page"),
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
            unittest.mock.patch("my_lib.browser.helpers.dump_page"),
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
    """wait_for_loading のテスト

    _wait_for_loading は Page を直接受け取り、page.wait_visible を待機に使う。
    """

    def test_wait_for_loading_success(self, make_page):
        """正常に読み込み完了を待機"""
        page = make_page()

        with unittest.mock.patch("time.sleep"):
            merhist.crawler._wait_for_loading(page, "//div", sec=0.1)

            page.wait_visible.assert_called_once()

    def test_wait_for_loading_timeout_retry(self, make_page, make_element):
        """タイムアウト時にリトライ（refresh してから再待機）"""
        page = make_page()
        page.wait_visible.side_effect = [
            my_lib.browser.WaitTimeoutError(),
            make_element(),
        ]

        with unittest.mock.patch("time.sleep"):
            merhist.crawler._wait_for_loading(page, "//div", sec=0.1, retry=True)

            assert page.wait_visible.call_count == 2
            page.refresh.assert_called_once()

    def test_wait_for_loading_timeout_no_retry(self, make_page):
        """リトライなしでタイムアウト時は例外を送出"""
        page = make_page()
        page.wait_visible.side_effect = my_lib.browser.WaitTimeoutError()

        with (
            unittest.mock.patch("time.sleep"),
            pytest.raises(my_lib.browser.WaitTimeoutError),
        ):
            merhist.crawler._wait_for_loading(page, "//div", sec=0.1, retry=False)


class TestVisitUrl:
    """visit_url のテスト"""

    def test_visit_url(self, make_page):
        """URL にアクセスして読み込みを待つ"""
        page = make_page()

        with (
            unittest.mock.patch("time.sleep"),
            unittest.mock.patch("merhist.crawler._wait_for_loading") as mock_wait,
        ):
            merhist.crawler._visit_url(page, "https://example.com", "//div")

            page.goto.assert_called_once_with("https://example.com")
            mock_wait.assert_called_once_with(page, "//div")


class TestExecuteLogin:
    """execute_login のテスト"""

    def test_execute_login(self, handle):
        """ログイン実行（page を第1引数として login.execute を呼ぶ）"""
        with unittest.mock.patch("my_lib.store.mercari.login.execute") as mock_login:
            merhist.crawler.execute_login(handle)

            mock_login.assert_called_once()
            # 第1引数が get_page() の Page であること
            assert mock_login.call_args[0][0] is handle._test_page


class TestSaveThumbnail:
    """save_thumbnail のテスト

    _save_thumbnail は browser_manager.get_browser().tab(url) の
    context manager 上で画像要素をスクリーンショットする。
    """

    def test_save_thumbnail(self, handle, make_element):
        """サムネイル保存"""
        item = merhist.item.SoldItem(id="m123")

        img = make_element(screenshot=b"fake_png_data")
        handle._test_tab.find.return_value = img

        with unittest.mock.patch("PIL.Image.open"):
            merhist.crawler._save_thumbnail(handle, item, "https://example.com/thumb.jpg")

            handle._test_tab.find.assert_called_once()
            img.screenshot.assert_called_once()

    def test_save_thumbnail_empty_png_data(self, handle, make_element):
        """サムネイル画像データが空の場合"""
        item = merhist.item.SoldItem(id="m123")

        handle._test_tab.find.return_value = make_element(screenshot=b"")

        with pytest.raises(merhist.exceptions.ThumbnailEmptyError):
            merhist.crawler._save_thumbnail(handle, item, "https://example.com/thumb.jpg")

    def test_save_thumbnail_zero_size_file(self, handle, make_element):
        """保存後のファイルサイズが0の場合"""
        item = merhist.item.SoldItem(id="m123")

        handle._test_tab.find.return_value = make_element(screenshot=b"fake_png_data")

        with (
            unittest.mock.patch.object(
                pathlib.Path,
                "stat",
                side_effect=lambda *a, **k: unittest.mock.MagicMock(st_size=0),
            ),
            pytest.raises(merhist.exceptions.ThumbnailSizeError),
        ):
            merhist.crawler._save_thumbnail(handle, item, "https://example.com/thumb.jpg")

    def test_save_thumbnail_corrupted_image(self, handle, make_element):
        """画像が破損している場合"""
        item = merhist.item.SoldItem(id="m123")

        handle._test_tab.find.return_value = make_element(screenshot=b"fake_png_data")

        with (
            unittest.mock.patch("PIL.Image.open") as mock_image_open,
            pytest.raises(merhist.exceptions.ThumbnailCorruptError),
        ):
            # verify() で例外を発生させる
            mock_img = unittest.mock.MagicMock()
            mock_img.verify.side_effect = Exception("Invalid image")
            mock_img.__enter__ = unittest.mock.MagicMock(return_value=mock_img)
            mock_img.__exit__ = unittest.mock.MagicMock(return_value=False)
            mock_image_open.return_value = mock_img

            merhist.crawler._save_thumbnail(handle, item, "https://example.com/thumb.jpg")


class TestFetchItemTransaction:
    """fetch_item_transaction のテスト"""

    def test_fetch_item_transaction_normal(self, handle):
        """通常アイテムのトランザクション取得"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        with unittest.mock.patch("merhist.crawler._fetch_item_transaction_normal") as mock_normal:
            merhist.crawler._fetch_item_transaction(handle, item)

            mock_normal.assert_called_once_with(handle, item)

    def test_fetch_item_transaction_shop(self, handle):
        """Shops アイテムのトランザクション取得"""
        item = merhist.item.BoughtItem(id="abc123", shop="mercari-shops.com")

        with unittest.mock.patch("merhist.crawler._fetch_item_transaction_shop") as mock_shop:
            merhist.crawler._fetch_item_transaction(handle, item)

            mock_shop.assert_called_once_with(handle, item)


class TestFetchSoldItemList:
    """fetch_sold_item_list のテスト"""

    def test_fetch_sold_item_list_no_items(self, handle):
        """販売アイテムなし"""
        handle.trading.sold_total_count = 0

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 0
        mock_counter.count = 0
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)

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
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)

        with (
            unittest.mock.patch("merhist.crawler._fetch_sold_count"),
            unittest.mock.patch("merhist.crawler._fetch_sold_item_list_by_page") as mock_fetch_page,
        ):
            merhist.crawler._fetch_sold_item_list(handle, continue_mode=True)

            # 全てキャッシュ済みなのでページ取得は呼ばれない
            mock_fetch_page.assert_not_called()


class TestFetchBoughtItemInfoList:
    """fetch_bought_item_info_list のテスト"""

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

    def test_fetch_bought_item_list_empty(self, handle):
        """購入履歴なし"""
        mock_counter = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)

        with unittest.mock.patch("merhist.crawler._fetch_bought_item_info_list", return_value=[]):
            merhist.crawler._fetch_bought_item_list(handle, continue_mode=True)

    def test_fetch_bought_item_list_with_items(self, handle):
        """購入履歴あり"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")

        mock_counter = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)

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
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)

        with (
            unittest.mock.patch("merhist.crawler._fetch_bought_item_info_list", return_value=[item]),
            unittest.mock.patch("merhist.crawler._fetch_item_detail") as mock_detail,
        ):
            merhist.crawler._fetch_bought_item_list(handle, continue_mode=True)

            # キャッシュ済みなので詳細取得は呼ばれない
            mock_detail.assert_not_called()


class TestFetchOrderItemList:
    """fetch_order_item_list のテスト"""

    def test_fetch_order_item_list(self, handle):
        """注文履歴取得"""
        continue_mode = merhist.crawler.ContinueMode(bought=True, sold=True)

        with (
            unittest.mock.patch("merhist.crawler._fetch_sold_item_list") as mock_sold,
            unittest.mock.patch("merhist.crawler._fetch_bought_item_list") as mock_bought,
        ):
            merhist.crawler.fetch_order_item_list(handle, continue_mode)

            mock_sold.assert_called_once_with(handle, True)
            mock_bought.assert_called_once_with(handle, True)

    def test_fetch_order_item_list_force_mode(self, handle):
        """強制取得モード"""
        continue_mode = merhist.crawler.ContinueMode(bought=False, sold=False)

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
    """fetch_item_description のテスト

    _fetch_item_description は browser_manager.get_browser().tab(url) の
    context manager (tab = Page) 上で要素を探索する。
    """

    def test_fetch_item_description_not_found(self, handle):
        """商品ページが見つからない場合"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        # 1回目の exists (NOT_FOUND) が True
        handle._test_tab.exists.side_effect = [True, False]

        with unittest.mock.patch("merhist.crawler._wait_for_loading"):
            merhist.crawler._fetch_item_description(handle, item)

            assert item.error == "商品情報ページが見つかりませんでした"

    def test_fetch_item_description_deleted(self, handle):
        """商品ページが削除されている場合"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        # 2回目の exists (DELETED) が True
        handle._test_tab.exists.side_effect = [False, True]

        with unittest.mock.patch("merhist.crawler._wait_for_loading"):
            merhist.crawler._fetch_item_description(handle, item)

            assert item.error == "商品情報ページが削除されています"

    def test_fetch_item_description_success(self, handle, make_element, by_value):
        """正常に商品説明を取得"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        tab = handle._test_tab
        tab.exists.return_value = False

        # 情報行 1 行
        def find_all_by_value(value):
            if merhist.xpath.ITEM_DESC_INFO_ROW in value:
                return [unittest.mock.MagicMock()]
            return []

        def find_by_value(value):
            if "title" in value:
                return make_element(text="商品の状態")
            if "body" in value:
                return make_element(text="新品、未使用")
            return None

        tab.find_all.side_effect = by_value(find_all_by_value)
        tab.find.side_effect = by_value(find_by_value)

        with unittest.mock.patch("merhist.crawler._wait_for_loading"):
            merhist.crawler._fetch_item_description(handle, item)

            assert item.condition == "新品、未使用"

    def test_fetch_item_description_category(self, handle, make_element, by_value):
        """カテゴリー情報を取得"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        tab = handle._test_tab
        tab.exists.return_value = False

        breadcrumb1 = make_element(text="家電")
        breadcrumb2 = make_element(text="スマートフォン")

        def find_all_by_value(value):
            # カテゴリーのパンくずリンク（body 配下の //a）
            if "//a" in value:
                return [breadcrumb1, breadcrumb2]
            if merhist.xpath.ITEM_DESC_INFO_ROW in value:
                return [unittest.mock.MagicMock()]
            return []

        def find_by_value(value):
            if "title" in value:
                return make_element(text="カテゴリー")
            return make_element(text="")

        tab.find_all.side_effect = by_value(find_all_by_value)
        tab.find.side_effect = by_value(find_by_value)

        with unittest.mock.patch("merhist.crawler._wait_for_loading"):
            merhist.crawler._fetch_item_description(handle, item)

            assert item.category == ["家電", "スマートフォン"]


class TestFetchItemTransactionNormal:
    """fetch_item_transaction_normal のテスト"""

    def test_fetch_item_transaction_normal_page_error(self, handle):
        """ページエラーの場合"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")
        handle._test_page.url = "https://example.com/error"
        handle._test_page.exists.return_value = True

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            pytest.raises(merhist.exceptions.PageLoadError),
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

    def test_fetch_item_transaction_normal_no_purchase_date(self, handle, make_element):
        """購入日時がない場合"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        page = handle._test_page
        page.exists.return_value = False
        # 情報行なし
        page.find_all.return_value = []
        # サムネイル要素（src なし）
        page.find.return_value = make_element(attrs={"src": None})

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            pytest.raises(merhist.exceptions.InvalidPageFormatError),
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

    def test_fetch_item_transaction_normal_success(self, handle, make_element, by_value):
        """正常に取引情報を取得"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        page = handle._test_page
        page.exists.return_value = False

        thumb = make_element(attrs={"src": None})
        title = make_element(text="購入日時")
        body_span = make_element(text="2024年1月15日 10:30")

        def find_all_by_value(value):
            if merhist.xpath.TRANSACTION_INFO_ROW in value:
                return [unittest.mock.MagicMock()]
            return []

        def find_by_value(value):
            if "img" in value:
                return thumb
            if "title" in value:
                return title
            if "span" in value:
                return body_span
            return thumb

        page.find_all.side_effect = by_value(find_all_by_value)
        page.find.side_effect = by_value(find_by_value)

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.parser.parse_datetime", return_value="2024-01-15 10:30:00"),
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

            assert item.purchase_date == "2024-01-15 10:30:00"

    def test_fetch_item_transaction_normal_with_thumbnail(self, handle, make_element, by_value):
        """サムネイル付きで取引情報を取得"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        page = handle._test_page
        page.exists.return_value = False

        thumb = make_element(attrs={"src": "https://example.com/thumb.jpg"})
        title = make_element(text="購入日時")
        body_span = make_element(text="2024年1月15日 10:30")

        def find_all_by_value(value):
            if merhist.xpath.TRANSACTION_INFO_ROW in value:
                return [unittest.mock.MagicMock()]
            return []

        def find_by_value(value):
            if "img" in value:
                return thumb
            if "title" in value:
                return title
            if "span" in value:
                return body_span
            return thumb

        page.find_all.side_effect = by_value(find_all_by_value)
        page.find.side_effect = by_value(find_by_value)

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.parser.parse_datetime", return_value="2024-01-15 10:30:00"),
            unittest.mock.patch("merhist.crawler._save_thumbnail") as mock_save,
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

            assert item.purchase_date == "2024-01-15 10:30:00"
            mock_save.assert_called_once()


class TestGetBoughtItemInfoList:
    """get_bought_item_info_list のテスト"""

    def test_get_bought_item_info_list_offset_error(self, handle):
        """オフセットがリスト長より大きい場合"""
        handle._test_page.find_all.return_value = []  # 0件

        item_list: list[merhist.item.BoughtItem] = []

        with pytest.raises(merhist.exceptions.HistoryFetchError, match="読み込みが正常にできていません"):
            merhist.crawler._get_bought_item_info_list(handle, page=1, offset=1, item_list=item_list)

    def test_get_bought_item_info_list_empty(self, handle):
        """空リスト"""
        handle._test_page.find_all.return_value = []

        item_list: list[merhist.item.BoughtItem] = []
        list_length, is_found_new = merhist.crawler._get_bought_item_info_list(
            handle, page=1, offset=0, item_list=item_list
        )

        assert list_length == 0
        assert is_found_new is False
        assert item_list == []

    def test_get_bought_item_info_list_with_items(self, handle, make_element, by_value):
        """アイテムがある場合"""
        page = handle._test_page
        page.find_all.return_value = [unittest.mock.MagicMock()]

        name = make_element(text="テスト商品")
        link = make_element(href="https://jp.mercari.com/transaction/m12345")
        dt = make_element(text="2025/01/15 10:30")

        def find_by_value(value):
            if merhist.xpath.BOUGHT_ITEM_LABEL in value:
                return name
            elif merhist.xpath.BOUGHT_ITEM_DATETIME in value:
                return dt
            elif merhist.xpath.BOUGHT_ITEM_LINK in value:
                return link
            return name

        page.find.side_effect = by_value(find_by_value)

        item_list: list[merhist.item.BoughtItem] = []
        list_length, is_found_new = merhist.crawler._get_bought_item_info_list(
            handle, page=1, offset=0, item_list=item_list, continue_mode=True
        )

        assert list_length == 1
        assert is_found_new is True
        assert len(item_list) == 1
        assert item_list[0].name == "テスト商品"
        assert item_list[0].id == "m12345"

    def test_get_bought_item_info_list_cached_continue_mode(self, handle, make_element, by_value):
        """continue_mode でキャッシュ済みの場合はスキップ"""
        # DB にキャッシュを追加
        cached_item = merhist.item.BoughtItem(id="m12345", name="キャッシュ済み")
        handle.db.upsert_bought_item(cached_item)

        page = handle._test_page
        page.find_all.return_value = [unittest.mock.MagicMock()]

        name = make_element(text="テスト商品")
        link = make_element(href="https://jp.mercari.com/transaction/m12345")
        dt = make_element(text="2025/01/15 10:30")

        def find_by_value(value):
            if merhist.xpath.BOUGHT_ITEM_LABEL in value:
                return name
            elif merhist.xpath.BOUGHT_ITEM_DATETIME in value:
                return dt
            elif merhist.xpath.BOUGHT_ITEM_LINK in value:
                return link
            return name

        page.find.side_effect = by_value(find_by_value)

        item_list: list[merhist.item.BoughtItem] = []
        list_length, is_found_new = merhist.crawler._get_bought_item_info_list(
            handle, page=1, offset=0, item_list=item_list, continue_mode=True
        )

        # キャッシュ済みなので is_found_new は False、リストにも追加されない
        assert list_length == 1
        assert is_found_new is False
        assert len(item_list) == 0


class TestFetchSoldCount:
    """fetch_sold_count のテスト"""

    def test_fetch_sold_count(self, handle, make_element):
        """販売件数取得"""
        # parse_sold_count が期待するフォーマット
        handle._test_page.find.return_value = make_element(text="1～20/全42件")

        with unittest.mock.patch("merhist.crawler._visit_url"):
            merhist.crawler._fetch_sold_count(handle)

            assert handle.trading.sold_total_count == 42


class TestContinueModeDataclass:
    """ContinueMode dataclass のテスト"""

    def test_continue_mode_creation(self):
        """ContinueMode の作成"""
        mode = merhist.crawler.ContinueMode(bought=True, sold=False)

        assert mode.bought is True
        assert mode.sold is False


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

    def test_fetch_item_transaction_shop_success(self, handle, make_element, by_value):
        """メルカリショップ取引の取得成功"""
        item = merhist.item.BoughtItem(id="abc123", shop="mercari-shops.com")

        page = handle._test_page

        price_elem = make_element(text="￥1,500")
        thumb_elem = make_element(attrs={"src": "https://example.com/shop-thumb.jpg"})

        def find_by_value(value):
            if merhist.xpath.SHOP_TRANSACTION_THUMBNAIL in value:
                return thumb_elem
            if merhist.xpath.SHOP_TRANSACTION_PRICE in value:
                return price_elem
            return price_elem

        page.find.side_effect = by_value(find_by_value)

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.crawler._save_thumbnail") as mock_save,
        ):
            merhist.crawler._fetch_item_transaction_shop(handle, item)

            assert item.price == 1500
            mock_save.assert_called_once()

    def test_fetch_item_transaction_shop_no_thumbnail(self, handle, make_element, by_value):
        """サムネイルなしのメルカリショップ取引"""
        item = merhist.item.BoughtItem(id="abc123", shop="mercari-shops.com")

        page = handle._test_page

        price_elem = make_element(text="￥2,000")
        thumb_elem = make_element(attrs={"src": None})  # サムネイルなし

        def find_by_value(value):
            if merhist.xpath.SHOP_TRANSACTION_THUMBNAIL in value:
                return thumb_elem
            if merhist.xpath.SHOP_TRANSACTION_PRICE in value:
                return price_elem
            return price_elem

        page.find.side_effect = by_value(find_by_value)

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.crawler._save_thumbnail") as mock_save,
        ):
            merhist.crawler._fetch_item_transaction_shop(handle, item)

            assert item.price == 2000
            mock_save.assert_not_called()


class TestFetchItemTransactionNormalPriceParsing:
    """価格パース処理（送料あり/なし）のテスト"""

    def test_fetch_item_transaction_normal_price_with_shipping(self, handle, make_element, by_value):
        """送料込みの価格パース"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        page = handle._test_page
        page.exists.return_value = False

        title = make_element()
        body_span = make_element(text="2024年1月15日 10:30")
        body = make_element(text="1,000円（送料込み）")
        thumb = make_element(attrs={"src": None})

        title_calls = [0]

        def find_all_by_value(value):
            if merhist.xpath.TRANSACTION_INFO_ROW in value:
                return [unittest.mock.MagicMock(), unittest.mock.MagicMock()]
            return []

        def find_by_value(value):
            if "img" in value:
                return thumb
            if "title" in value:
                title_calls[0] += 1
                title.text = "購入日時" if title_calls[0] == 1 else "商品代金"
                return title
            if "span" in value:
                return body_span
            if "body" in value:
                return body
            return thumb

        page.find_all.side_effect = by_value(find_all_by_value)
        page.find.side_effect = by_value(find_by_value)

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.parser.parse_datetime", return_value="2024-01-15 10:30:00"),
            unittest.mock.patch("merhist.parser.parse_price_with_shipping", return_value=1000),
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

            assert item.purchase_date is not None

    def test_fetch_item_transaction_normal_price_separate_shipping(self, handle, make_element, by_value):
        """送料別の価格パース（number_text が渡される）"""
        item = merhist.item.BoughtItem(id="m123", shop="mercari.com")

        page = handle._test_page
        page.exists.return_value = False

        title = make_element()
        body_span = make_element(text="2024年1月15日 10:30")
        number = make_element(text="1,000")
        # body の子要素から number を取得（body.find(ROW_NUMBER)）
        body = make_element(text="1,000円", find=[(merhist.xpath.TRANSACTION_ROW_NUMBER, number)])
        thumb = make_element(attrs={"src": None})

        title_calls = [0]

        def find_all_by_value(value):
            if merhist.xpath.TRANSACTION_INFO_ROW in value:
                return [unittest.mock.MagicMock(), unittest.mock.MagicMock()]
            return []

        def find_by_value(value):
            if "img" in value:
                return thumb
            if "title" in value:
                title_calls[0] += 1
                title.text = "購入日時" if title_calls[0] == 1 else "商品代金"
                return title
            if "span" in value:
                return body_span
            if "body" in value:
                return body
            return thumb

        page.find_all.side_effect = by_value(find_all_by_value)
        page.find.side_effect = by_value(find_by_value)

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("merhist.parser.parse_datetime", return_value="2024-01-15 10:30:00"),
            unittest.mock.patch("merhist.parser.parse_price_with_shipping", return_value=1000) as mock_parse,
        ):
            merhist.crawler._fetch_item_transaction_normal(handle, item)

            assert item.purchase_date is not None
            # 送料別なので number_text ("1,000") が渡される
            mock_parse.assert_called_with("1,000円", "1,000")


class TestFetchSoldItemListByPage:
    """_fetch_sold_item_list_by_page のテスト"""

    @pytest.fixture
    def handle(self, mock_config, browser_mocks):
        """Handle インスタンス（プログレスバーをモック）"""
        h = merhist.handle.Handle(config=mock_config)
        browser_mocks(h)
        h.get_progress_bar = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock())  # type: ignore[method-assign]
        h.trading.sold_total_count = 10
        yield h
        h.finish()

    def test_fetch_sold_item_list_by_page_empty(self, handle):
        """空のページ"""
        handle._test_page.find_all.return_value = []

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler._fetch_sold_item_list_by_page(handle, page=1, continue_mode=True)

            assert result is False

    def _configure_page(self, handle, make_element, by_value, rows):
        """販売一覧の行要素・カラム要素を設定する。"""
        page = handle._test_page
        page.find_all.return_value = rows

        link = make_element(text="テスト商品", href="https://jp.mercari.com/transaction/m12345")
        price = make_element(text="1,000")
        other = make_element(text="2025/01/15")

        def find_by_value(value):
            if merhist.xpath.SOLD_ITEM_LINK in value:
                return link
            if merhist.xpath.SOLD_ITEM_PRICE_NUMBER in value:
                return price
            return other

        page.find.side_effect = by_value(find_by_value)

    def test_fetch_sold_item_list_by_page_with_items(self, handle, make_element, by_value):
        """アイテムありのページ"""
        self._configure_page(handle, make_element, by_value, [unittest.mock.MagicMock()])

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

    def test_fetch_sold_item_list_by_page_cached(self, handle, make_element, by_value):
        """キャッシュ済みアイテム"""
        # DB にキャッシュを追加
        cached_item = merhist.item.SoldItem(id="m12345", name="キャッシュ済み", price=1000)
        handle.db.upsert_sold_item(cached_item)

        self._configure_page(handle, make_element, by_value, [unittest.mock.MagicMock()])

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

    def test_fetch_sold_item_list_by_page_first_fetch_error(self, handle, make_element, by_value):
        """最初のアイテム取得失敗でエラー"""
        self._configure_page(handle, make_element, by_value, [unittest.mock.MagicMock()])

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

    def test_fetch_sold_item_list_by_page_debug_mode(self, handle, make_element, by_value):
        """デバッグモードでは1件のみ処理"""
        handle.debug_mode = True

        self._configure_page(
            handle, make_element, by_value, [unittest.mock.MagicMock(), unittest.mock.MagicMock()]
        )

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

    def test_fetch_sold_item_list_shutdown_requested(self, handle):
        """シャットダウンリクエスト時の処理"""
        handle.trading.sold_total_count = 10

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 10
        mock_counter.count = 0
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)
        with (
            unittest.mock.patch("merhist.crawler._fetch_sold_count"),
            unittest.mock.patch("merhist.crawler.is_shutdown_requested", return_value=True),
            unittest.mock.patch("merhist.crawler._fetch_sold_item_list_by_page") as mock_fetch,
        ):
            merhist.crawler._fetch_sold_item_list(handle, continue_mode=True)

            # シャットダウン時はページ取得が行われない
            mock_fetch.assert_not_called()

    def test_fetch_sold_item_list_pages_with_no_new_items(self, handle):
        """新しいアイテムがない場合の早期終了"""
        handle.trading.sold_total_count = 40  # 2ページ分

        mock_counter = unittest.mock.MagicMock()
        mock_counter.total = 2
        mock_counter.count = 0
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)
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
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)
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
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)
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

    def _configure_item_page(self, handle, make_element, by_value):
        """購入履歴 1 件分の要素を設定する。"""
        page = handle._test_page
        page.find_all.return_value = [unittest.mock.MagicMock()]

        name = make_element(text="テスト商品")
        link = make_element(href="https://jp.mercari.com/transaction/m12345")
        dt = make_element(text="2025/01/15 10:30")

        def find_by_value(value):
            if merhist.xpath.BOUGHT_ITEM_LABEL in value:
                return name
            elif merhist.xpath.BOUGHT_ITEM_DATETIME in value:
                return dt
            elif merhist.xpath.BOUGHT_ITEM_LINK in value:
                return link
            return name

        page.find.side_effect = by_value(find_by_value)

    def test_fetch_bought_item_info_list_impl_empty(self, handle):
        """空の購入履歴"""
        handle._test_page.find_all.return_value = []
        handle._test_page.exists.return_value = False

        with unittest.mock.patch("merhist.crawler._visit_url"):
            result = merhist.crawler._fetch_bought_item_info_list_impl(handle, continue_mode=True)

            assert result == []

    def test_fetch_bought_item_info_list_impl_end_of_list(self, handle, make_element, by_value):
        """リスト終端（もっと見るボタンなし）"""
        self._configure_item_page(handle, make_element, by_value)
        handle._test_page.exists.return_value = False  # ボタンなし

        with unittest.mock.patch("merhist.crawler._visit_url"):
            result = merhist.crawler._fetch_bought_item_info_list_impl(handle, continue_mode=False)

            # ボタンがないので "Detected end of list" で終了
            assert len(result) == 1

    def test_fetch_bought_item_info_list_impl_with_more_button(self, handle, make_element, by_value):
        """もっと見るボタンがある場合"""
        self._configure_item_page(handle, make_element, by_value)
        handle._test_page.exists.return_value = True  # ボタンあり

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler._fetch_bought_item_info_list_impl(handle, continue_mode=True)

            # ボタンをクリックして次ページを読み込む
            handle._test_page.wait_clickable.assert_called()
            handle._test_page.wait_absent.assert_called()
            assert len(result) >= 1

    def test_fetch_bought_item_info_list_impl_debug_mode(self, handle, make_element, by_value):
        """デバッグモードでの動作"""
        handle.debug_mode = True
        self._configure_item_page(handle, make_element, by_value)
        handle._test_page.exists.return_value = True  # ボタンあり

        with (
            unittest.mock.patch("merhist.crawler._visit_url"),
            unittest.mock.patch("time.sleep"),
        ):
            result = merhist.crawler._fetch_bought_item_info_list_impl(handle, continue_mode=True)

            # デバッグモードなので早期終了
            assert len(result) >= 1


class TestFetchBoughtItemListBranches:
    """_fetch_bought_item_list の分岐テスト"""

    def test_fetch_bought_item_list_shutdown_requested(self, handle):
        """シャットダウンリクエスト時"""
        item = merhist.item.BoughtItem(id="m123", name="テスト商品", shop="mercari.com")

        mock_counter = unittest.mock.MagicMock()
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)
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
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)

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
        handle.get_progress_bar = unittest.mock.MagicMock(return_value=mock_counter)
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

    def test_fetch_order_item_list_shutdown_after_sold(self, handle):
        """販売履歴取得後のシャットダウン"""
        continue_mode = merhist.crawler.ContinueMode(bought=True, sold=True)

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

    def test_get_bought_item_info_list_force_mode_adds_cached(self, handle, make_element, by_value):
        """強制モードではキャッシュ済みもリストに追加"""
        # DB にキャッシュを追加
        cached_item = merhist.item.BoughtItem(id="m12345", name="キャッシュ済み")
        handle.db.upsert_bought_item(cached_item)

        page = handle._test_page
        page.find_all.return_value = [unittest.mock.MagicMock()]

        name = make_element(text="テスト商品")
        link = make_element(href="https://jp.mercari.com/transaction/m12345")
        dt = make_element(text="2025/01/15 10:30")

        def find_by_value(value):
            if merhist.xpath.BOUGHT_ITEM_LABEL in value:
                return name
            elif merhist.xpath.BOUGHT_ITEM_DATETIME in value:
                return dt
            elif merhist.xpath.BOUGHT_ITEM_LINK in value:
                return link
            return name

        page.find.side_effect = by_value(find_by_value)

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
