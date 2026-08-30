#!/usr/bin/env python3
# ruff: noqa: S101
"""
共通テストフィクスチャ

テスト全体で使用する共通のフィクスチャとヘルパーを定義します。
"""

import datetime
import logging
import unittest.mock

import pytest

import merhist.config
import merhist.handle

# === ブラウザ (my_lib.browser) モックヘルパー ===
#
# プロダクションコードは Selenium の (driver, wait) タプルから
# my_lib.browser の Page 抽象へ移行済み。テストでは以下のヘルパーで
# Page / Element のモックを組み立てる。
#
# - Page / Element の要素検索（find / find_all）は Locator を受け取る。
#   XPath 文字列は locator.value に入るため、xpath ごとに返り値を出し
#   分けたい場合は build_element / build_page の find/find_all に
#   「値の部分文字列 -> 返り値」のマッピングか、値を受け取る関数を渡す。


def _locator_dispatch(spec, default):
    """Locator を受け取る side_effect を生成する。

    spec:
      - None            : 常に default を返す
      - callable(value) : locator.value を渡して結果を得る
      - dict / seq      : (部分文字列, 返り値) のマッピング（最初に一致したもの）
    """
    if spec is None:
        return lambda *a, **k: default
    if callable(spec):
        return lambda locator, *a, **k: spec(locator.value)

    pairs = list(spec.items()) if isinstance(spec, dict) else list(spec)

    def _side_effect(locator, *a, **k):
        for substr, result in pairs:
            if substr in locator.value:
                return result
        return default

    return _side_effect


def build_element(*, text="", attrs=None, screenshot=b"\x89PNG\r\n", find=None, find_all=None, href=None):
    """my_lib.browser.Element のモックを生成する。"""
    element = unittest.mock.MagicMock(name="element")
    element.text = text

    attr_map = dict(attrs or {})
    if href is not None:
        attr_map.setdefault("href", href)
    element.attr = unittest.mock.MagicMock(side_effect=lambda name: attr_map.get(name))

    element.screenshot = unittest.mock.MagicMock(return_value=screenshot)
    element.click = unittest.mock.MagicMock()
    _set_finders(element, find, find_all)
    return element


def _set_finders(mock, find, find_all):
    """find / find_all をモックに設定する。

    spec が None のときは return_value を使い（テスト側で return_value を
    上書きできる）、spec があるときは side_effect を使う。
    """
    if find is None:
        mock.find = unittest.mock.MagicMock(return_value=None)
    else:
        mock.find = unittest.mock.MagicMock(side_effect=_locator_dispatch(find, None))
    if find_all is None:
        mock.find_all = unittest.mock.MagicMock(return_value=[])
    else:
        mock.find_all = unittest.mock.MagicMock(side_effect=_locator_dispatch(find_all, []))


def build_page(
    *,
    url="https://jp.mercari.com/",
    title="",
    content="<html></html>",
    find=None,
    find_all=None,
    exists=False,
):
    """my_lib.browser.Page のモックを生成する。"""
    page = unittest.mock.MagicMock(name="page")
    page.url = url
    page.title = title
    page.content = content

    _set_finders(page, find, find_all)

    if callable(exists):
        page.exists = unittest.mock.MagicMock(side_effect=lambda locator, *a, **k: exists(locator.value))
    else:
        page.exists = unittest.mock.MagicMock(return_value=exists)

    page.wait_visible = unittest.mock.MagicMock(return_value=build_element())
    page.wait_clickable = unittest.mock.MagicMock(return_value=build_element())
    page.wait_absent = unittest.mock.MagicMock(return_value=None)
    page.wait_text = unittest.mock.MagicMock(return_value=None)
    page.wait_until = unittest.mock.MagicMock(return_value=None)
    page.goto = unittest.mock.MagicMock()
    page.refresh = unittest.mock.MagicMock()
    page.screenshot = unittest.mock.MagicMock(return_value=b"\x89PNG")
    return page


def attach_browser(handle, *, page=None, tab=None):
    """Handle にブラウザモックを取り付ける。

    - handle.get_page() が page モックを返すようにする。
    - handle.browser_manager.get_browser().tab(url) が
      context manager として tab モックを yield するようにする。

    テストからは handle._test_page / handle._test_tab で参照できる。
    """
    if page is None:
        page = build_page()
    if tab is None:
        tab = build_page()

    handle.get_page = unittest.mock.MagicMock(return_value=page)

    browser_manager = unittest.mock.MagicMock(name="browser_manager")
    tab_cm = browser_manager.get_browser.return_value.tab.return_value
    tab_cm.__enter__.return_value = tab
    tab_cm.__exit__.return_value = False
    handle._browser_manager = browser_manager

    handle._test_page = page
    handle._test_tab = tab
    handle._test_browser_manager = browser_manager
    return page, tab


@pytest.fixture
def make_element():
    """Element モック生成関数を返すフィクスチャ。"""
    return build_element


@pytest.fixture
def make_page():
    """Page モック生成関数を返すフィクスチャ。"""
    return build_page


@pytest.fixture
def browser_mocks():
    """Handle にブラウザモックを取り付ける関数を返すフィクスチャ。"""
    return attach_browser


@pytest.fixture
def by_value():
    """値ベースの関数を Locator ベースの side_effect に変換するヘルパー。

    使用例::

        def find_by_value(value):
            if merhist.xpath.SOLD_ITEM_LINK in value:
                return link_element
            return None

        page.find.side_effect = by_value(find_by_value)
    """

    def _wrap(fn):
        def _side_effect(locator, *a, **k):
            return fn(locator.value)

        return _side_effect

    return _wrap


@pytest.fixture
def mock_config(tmp_path):
    """共通のモック Config（全パスを tmp_path 配下に割り当てる）。"""
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
def handle(mock_config):
    """ブラウザモックを取り付けた Handle インスタンス。"""
    h = merhist.handle.Handle(config=mock_config)
    attach_browser(h)
    yield h
    h.finish()


# === 環境モック ===
@pytest.fixture(scope="session", autouse=True)
def env_mock():
    """テスト環境用の環境変数モック"""
    with unittest.mock.patch.dict(
        "os.environ",
        {
            "TEST": "true",
            "NO_COLORED_LOGS": "true",
        },
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session", autouse=True)
def slack_mock():
    """Slack API のモック"""
    with (
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.chat_postMessage",
            return_value={"ok": True, "ts": "1234567890.123456"},
        ),
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.files_upload_v2",
            return_value={"ok": True, "files": [{"id": "test_file_id"}]},
        ),
        unittest.mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.files_getUploadURLExternal",
            return_value={"ok": True, "upload_url": "https://example.com"},
        ) as fixture,
    ):
        yield fixture


@pytest.fixture(autouse=True)
def _clear():
    """各テスト前にステートをクリア"""
    import my_lib.notify.slack

    my_lib.notify.slack._interval_clear()
    my_lib.notify.slack._hist_clear()


# === アイテムフィクスチャ ===
@pytest.fixture
def sold_item():
    """SoldItem フィクスチャ"""
    from merhist.item import SoldItem

    return SoldItem(
        id="m12345678901",
        name="テスト商品",
        order_url="https://jp.mercari.com/transaction/m12345678901",
        url="https://jp.mercari.com/item/m12345678901",
        shop="mercari.com",
        count=1,
        category=["本・雑誌・漫画", "漫画", "少年漫画"],
        condition="目立った傷や汚れなし",
        postage_charge="送料込み",
        seller_region="東京都",
        shipping_method="らくらくメルカリ便",
        purchase_date=datetime.datetime(2025, 1, 15, 10, 30),
        price=1500,
        commission=150,
        postage=0,
        commission_rate=10,
        profit=1350,
        completion_date=datetime.datetime(2025, 1, 18, 14, 0),
    )


@pytest.fixture
def bought_item():
    """BoughtItem フィクスチャ"""
    from merhist.item import BoughtItem

    return BoughtItem(
        id="m98765432101",
        name="購入テスト商品",
        order_url="https://jp.mercari.com/transaction/m98765432101",
        url="https://jp.mercari.com/item/m98765432101",
        shop="mercari.com",
        count=1,
        category=["家電・スマホ・カメラ", "スマートフォン本体"],
        condition="新品、未使用",
        postage_charge="送料込み",
        seller_region="大阪府",
        shipping_method="ゆうゆうメルカリ便",
        purchase_date=datetime.datetime(2025, 1, 20, 15, 45),
        price=25000,
    )


@pytest.fixture
def shop_item():
    """メルカリShops アイテムフィクスチャ"""
    from merhist.item import BoughtItem

    return BoughtItem(
        id="abc123xyz",
        name="ショップ商品",
        order_url="https://mercari-shops.com/orders/abc123xyz",
        url="https://jp.mercari.com/shops/product/abc123xyz",
        shop="mercari-shops.com",
        count=1,
        category=["ファッション", "メンズ"],
        purchase_date=datetime.datetime(2025, 1, 25, 9, 0),
        price=3000,
    )


# === Slack 通知検証 ===
@pytest.fixture
def slack_checker():
    """Slack 通知検証ヘルパーを返す"""
    import my_lib.notify.slack

    class SlackChecker:
        def assert_notified(self, message, index=-1):
            notify_hist = my_lib.notify.slack._hist_get(is_thread_local=False)
            assert len(notify_hist) != 0, "通知がされていません。"
            assert notify_hist[index].find(message) != -1, f"「{message}」が通知されていません。"

        def assert_not_notified(self):
            notify_hist = my_lib.notify.slack._hist_get(is_thread_local=False)
            assert notify_hist == [], "通知がされています。"

    return SlackChecker()


# === ロギング設定 ===
logging.getLogger("selenium.webdriver.remote").setLevel(logging.WARNING)
logging.getLogger("selenium.webdriver.common").setLevel(logging.DEBUG)
