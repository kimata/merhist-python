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
