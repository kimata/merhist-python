#!/usr/bin/env python3
"""
メルカリから販売履歴や購入履歴を収集します。

Usage:
  crawler.py [-c CONFIG] [-o BOUGHT_ID] [-B] [-S] [--fB] [--fS] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -o ORDER_ID       : 商品データを取得します。
  -B                : 購入商品リストを取得します。
  -S                : 販売商品リストを取得します。
  --fB              : 購入履歴を強制的に再取得します。
  --fS              : 販売履歴を強制的に再取得します。
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import math
import pathlib
import re
import time
import traceback
import warnings
from dataclasses import dataclass
from typing import TypeVar

import my_lib.graceful_shutdown
import my_lib.pretty
import my_lib.selenium_util
import my_lib.store.mercari.exceptions
import my_lib.store.mercari.login
import PIL.Image
import selenium.common.exceptions
import selenium.webdriver.common.by
import selenium.webdriver.support.expected_conditions
import selenium.webdriver.support.wait

import merhist.const
import merhist.exceptions
import merhist.handle
import merhist.item
import merhist.parser
import merhist.xpath

# pydub の ffmpeg 警告を抑制（speechrecognition 経由で使用）
warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")

_T = TypeVar("_T", bound=merhist.item.ItemBase)

_STATUS_SOLD_PAGE: str = "[収集] 販売ページ"
_STATUS_SOLD_ITEM: str = "[収集] 販売商品"
_STATUS_BOUGHT_ITEM: str = "[収集] 購入商品"


# Graceful shutdown 用のエイリアス（my_lib.graceful_shutdown を使用）
def is_shutdown_requested() -> bool:
    """シャットダウンがリクエストされているかを返す"""
    return my_lib.graceful_shutdown.is_shutdown_requested()


_FETCH_RETRY_COUNT: int = 3

# 待機時間（秒）
_RETRY_WAIT_BASE: int = 5  # リトライ時の基本待機時間（i倍される）
_PAGE_TRANSITION_WAIT: int = 1  # ページ遷移後の待機時間
_MORE_LOAD_WAIT: int = 3  # 「もっと読み込む」後の待機時間

_MERCARI_NORMAL: str = "mercari.com"
_MERCARI_SHOP: str = "mercari-shops.com"


@dataclass(frozen=True)
class ContinueMode:
    bought: bool
    sold: bool


@dataclass(frozen=True)
class _DescriptionRowDef:
    """行定義（商品説明ページ用）"""

    title: str
    type: str  # "text", "category"
    name: str


@dataclass(frozen=True)
class _TransactionRowDef:
    """行定義（取引ページ用）"""

    title: str
    type: str  # "datetime", "price"
    name: str


@dataclass(frozen=True)
class _SoldColDef:
    """列定義（販売一覧ページ用）"""

    index: int
    type: str  # "text", "price", "rate", "date"
    name: str
    link_name: str | None = None


def execute_login(handle: merhist.handle.Handle) -> None:
    handle.set_status("🔑 メルカリにログインします...")

    driver, wait = handle.get_selenium_driver()

    try:
        my_lib.store.mercari.login.execute(
            driver,
            wait,
            handle.config.login.mercari,
            handle.config.login.line,
            handle.config.slack,
            handle.config.debug_dir_path,
        )
    except Exception as e:
        raise my_lib.store.mercari.exceptions.LoginError(f"メルカリへのログインに失敗しました: {e}") from e


def _wait_for_loading(
    handle: merhist.handle.Handle,
    xpath: str = merhist.xpath.NOTIFICATION_BUTTON,
    sec: float = 1,
    retry: bool = True,
) -> None:
    driver, wait = handle.get_selenium_driver()

    try:
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_all_elements_located(
                (selenium.webdriver.common.by.By.XPATH, xpath)
            )
        )
    except selenium.common.exceptions.TimeoutException:
        if retry:
            logging.warning("Timeout waiting for element, retrying: %s", xpath)
            driver.refresh()
            _wait_for_loading(handle, xpath, sec, retry=False)
        else:
            raise
    time.sleep(sec)


def _gen_sell_hist_url(page: int) -> str:
    return merhist.const.SOLD_HIST_URL.format(page=page)


def gen_item_transaction_url(item: merhist.item.ItemBase) -> str:
    if item.shop == _MERCARI_SHOP:
        return merhist.const.ITEM_SHOP_TRANSACTION_URL.format(id=item.id)
    else:
        return merhist.const.ITEM_NORMAL_TRANSACTION_URL.format(id=item.id)


def _gen_item_description_url(item: merhist.item.ItemBase) -> str:
    if item.shop == _MERCARI_SHOP:
        return merhist.const.ITEM_SHOP_DESCRIPTION_URL.format(id=item.id)
    else:
        return merhist.const.ITEM_NORMAL_DESCRIPTION_URL.format(id=item.id)


def _set_item_id_from_order_url(item: merhist.item.ItemBase) -> None:
    if match := re.match(r".*/.*mercari\.com.*/(m\d+)/?", item.order_url):
        item.id = match.group(1)
        item.shop = _MERCARI_NORMAL
    elif match := re.match(r".*.mercari-shops\.com.*/orders/(\w+)/?", item.order_url):
        item.id = match.group(1)
        item.shop = _MERCARI_SHOP
    else:
        logging.error("Unexpected URL format: %s", item.order_url)
        raise merhist.exceptions.InvalidURLFormatError("URL の形式が想定と異なります", item.order_url)


def _visit_url(handle: merhist.handle.Handle, url: str, xpath: str = merhist.xpath.NAVIGATION_TOP) -> None:
    driver, _ = handle.get_selenium_driver()
    driver.get(url)

    _wait_for_loading(handle, xpath)


def _save_thumbnail(handle: merhist.handle.Handle, item: merhist.item.ItemBase, thumb_url: str) -> None:
    driver, _ = handle.get_selenium_driver()

    thumb_path = pathlib.Path(handle.get_thumb_path(item))

    with my_lib.selenium_util.browser_tab(driver, thumb_url):
        png_data = driver.find_element(selenium.webdriver.common.by.By.XPATH, "//img").screenshot_as_png

        if not png_data:
            raise merhist.exceptions.ThumbnailEmptyError("サムネイル画像データが空です", path=str(thumb_path))

        with thumb_path.open("wb") as f:
            f.write(png_data)

        if thumb_path.stat().st_size == 0:
            thumb_path.unlink()
            raise merhist.exceptions.ThumbnailSizeError("サムネイル画像のサイズが0です", path=str(thumb_path))

        try:
            with PIL.Image.open(thumb_path) as img:
                img.verify()
        except Exception as e:
            thumb_path.unlink()
            raise merhist.exceptions.ThumbnailCorruptError(
                "サムネイル画像が破損しています", path=str(thumb_path)
            ) from e


def _fetch_item_description(handle: merhist.handle.Handle, item: merhist.item.ItemBase) -> None:
    row_def_list = [
        _DescriptionRowDef(title="カテゴリー", type="category", name="category"),
        _DescriptionRowDef(title="商品の状態", type="text", name="condition"),
        _DescriptionRowDef(title="配送料の負担", type="text", name="postage_charge"),
        _DescriptionRowDef(title="発送元の地域", type="text", name="seller_region"),
        _DescriptionRowDef(title="配送の方法", type="text", name="shipping_method"),
    ]

    driver, _ = handle.get_selenium_driver()

    with my_lib.selenium_util.browser_tab(driver, _gen_item_description_url(item)):
        _wait_for_loading(handle)

        if my_lib.selenium_util.xpath_exists(driver, merhist.xpath.ITEM_DESC_NOT_FOUND):
            logging.warning("Description page not found: %s", driver.current_url)
            item.error = "商品情報ページが見つかりませんでした"
            return
        elif my_lib.selenium_util.xpath_exists(driver, merhist.xpath.ITEM_DESC_DELETED):
            logging.warning("Description page has been deleted: %s", driver.current_url)
            item.error = "商品情報ページが削除されています"
            return

        info_row_xpath = merhist.xpath.ITEM_DESC_INFO_ROW
        for i in range(len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, info_row_xpath))):
            row_xpath = merhist.xpath.nth_element(info_row_xpath, i + 1)

            row_title = driver.find_element(
                selenium.webdriver.common.by.By.XPATH, row_xpath + merhist.xpath.ITEM_DESC_ROW_TITLE
            ).text
            for row_def in row_def_list:
                if row_def.title != row_title:
                    continue

                if row_def.type == "text":
                    item.set_field(
                        row_def.name,
                        driver.find_element(
                            selenium.webdriver.common.by.By.XPATH,
                            row_xpath + merhist.xpath.ITEM_DESC_ROW_BODY,
                        ).text,
                    )
                elif row_def.type == "category":
                    breadcrumb_list = driver.find_elements(
                        selenium.webdriver.common.by.By.XPATH,
                        row_xpath + merhist.xpath.ITEM_DESC_ROW_BODY_LINKS,
                    )
                    item.set_field(row_def.name, [x.text for x in breadcrumb_list])


def _fetch_item_transaction_normal(handle: merhist.handle.Handle, item: merhist.item.ItemBase) -> None:
    row_def_list = [
        _TransactionRowDef(title="購入日時", type="datetime", name="purchase_date"),
        _TransactionRowDef(title="商品代金", type="price", name="price"),
        _TransactionRowDef(title="配送料", type="price", name="postage"),
    ]

    driver, _ = handle.get_selenium_driver()

    _visit_url(handle, gen_item_transaction_url(item), merhist.xpath.TRANSACTION_INFO_ROW)

    if my_lib.selenium_util.xpath_exists(driver, merhist.xpath.TRANSACTION_PAGE_ERROR):
        logging.warning("Failed to load page: %s", driver.current_url)
        raise merhist.exceptions.PageLoadError("ページの読み込みに失敗しました", driver.current_url)

    info_row_xpath = merhist.xpath.TRANSACTION_INFO_ROW
    has_purchase_date = False
    for i in range(len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, info_row_xpath))):
        row_xpath = merhist.xpath.nth_element(info_row_xpath, i + 1)

        row_title = driver.find_element(
            selenium.webdriver.common.by.By.XPATH, row_xpath + merhist.xpath.TRANSACTION_ROW_TITLE
        ).text
        for row_def in row_def_list:
            if row_def.title != row_title:
                continue

            if row_def.type == "datetime":
                item.set_field(
                    row_def.name,
                    merhist.parser.parse_datetime(
                        driver.find_element(
                            selenium.webdriver.common.by.By.XPATH,
                            row_xpath + merhist.xpath.TRANSACTION_ROW_BODY_SPAN,
                        ).text
                    ),
                )
                has_purchase_date = True
            elif row_def.type == "price":
                if not hasattr(item, row_def.name):
                    continue  # pragma: no cover  # 現状全アイテムに price フィールドがあるため
                body_elem = driver.find_element(
                    selenium.webdriver.common.by.By.XPATH,
                    row_xpath + merhist.xpath.TRANSACTION_ROW_BODY,
                )
                body_text = body_elem.text
                number_text = None
                if "送料込み" not in body_text:
                    number_text = body_elem.find_element(
                        selenium.webdriver.common.by.By.XPATH,
                        merhist.xpath.TRANSACTION_ROW_NUMBER,
                    ).text
                item.set_field(
                    row_def.name,
                    merhist.parser.parse_price_with_shipping(body_text, number_text),
                )

    thumb_url = driver.find_element(
        selenium.webdriver.common.by.By.XPATH,
        merhist.xpath.TRANSACTION_THUMBNAIL,
    ).get_attribute("src")

    if thumb_url is not None:
        _save_thumbnail(handle, item, thumb_url)

    if not has_purchase_date:
        logging.error("Unexpected page format: %s", gen_item_transaction_url(item))
        raise merhist.exceptions.InvalidPageFormatError(
            "ページの形式が想定と異なります", gen_item_transaction_url(item)
        )


def _fetch_item_transaction_shop(handle: merhist.handle.Handle, item: merhist.item.BoughtItem) -> None:
    driver, _ = handle.get_selenium_driver()

    _visit_url(handle, gen_item_transaction_url(item), merhist.xpath.SHOP_TRANSACTION_PHOTO_NAME)

    info_xpath = merhist.xpath.SHOP_TRANSACTION_INFO
    item.price = int(
        driver.find_element(
            selenium.webdriver.common.by.By.XPATH,
            info_xpath + merhist.xpath.SHOP_TRANSACTION_PRICE,
        )
        .text.replace("￥", "")
        .replace(",", "")
    )

    thumb_url = driver.find_element(
        selenium.webdriver.common.by.By.XPATH, info_xpath + merhist.xpath.SHOP_TRANSACTION_THUMBNAIL
    ).get_attribute("src")
    if thumb_url is not None:
        _save_thumbnail(handle, item, thumb_url)


def _fetch_item_transaction(handle: merhist.handle.Handle, item: merhist.item.ItemBase) -> None:
    if item.shop == _MERCARI_SHOP:
        assert isinstance(item, merhist.item.BoughtItem)  # noqa: S101
        _fetch_item_transaction_shop(handle, item)
    else:
        _fetch_item_transaction_normal(handle, item)


def _fetch_item_detail(handle: merhist.handle.Handle, item: _T) -> _T:
    error_message = ""
    error_detail = ""

    for i in range(_FETCH_RETRY_COUNT):
        if i != 0:
            logging.info("Retry %s", gen_item_transaction_url(item))
            time.sleep(_RETRY_WAIT_BASE * i)

        try:
            item.count = 1
            item.url = _gen_item_description_url(item)
            _fetch_item_description(handle, item)
            _fetch_item_transaction(handle, item)

            if handle.debug_mode:
                logging.debug(my_lib.pretty.format(item.to_dict()))
            else:
                price = getattr(item, "price", 0)
                logging.info(
                    "%s %s %s円",
                    item.purchase_date.strftime("%Y年%m月%d日") if item.purchase_date else "不明",
                    item.name,
                    f"{price:,}",
                )

            return item
        except Exception as e:
            error_message = str(e)
            logging.warning("%s: %s", type(e).__name__, error_message.rstrip())
            error_detail = traceback.format_exc()
            driver, _ = handle.get_selenium_driver()
            my_lib.selenium_util.dump_page(
                driver,
                merhist.const.gen_debug_dump_id(),
                handle.config.debug_dir_path,
            )

        logging.warning("Failed to fetch %s", gen_item_transaction_url(item))

    logging.error(error_detail)
    logging.error("Give up to fetch %s", gen_item_transaction_url(item))

    item.error = error_message

    return item


def _fetch_sold_item_list_by_page(handle: merhist.handle.Handle, page: int, continue_mode: bool) -> bool:
    col_def_list = [
        _SoldColDef(index=1, type="text", name="name", link_name="order_url"),
        _SoldColDef(index=2, type="price", name="price"),
        _SoldColDef(index=3, type="price", name="commission"),
        _SoldColDef(index=4, type="price", name="postage"),
        _SoldColDef(index=6, type="rate", name="commission_rate"),
        _SoldColDef(index=7, type="price", name="profit"),
        _SoldColDef(index=9, type="date", name="completion_date"),
    ]
    driver, _ = handle.get_selenium_driver()

    total_page = math.ceil(handle.trading.sold_total_count / merhist.const.SOLD_ITEM_PER_PAGE)

    handle.set_status(f"販売履歴を解析しています... {page}/{total_page} ページ")

    _visit_url(handle, _gen_sell_hist_url(page), merhist.xpath.SOLD_PAGING)

    logging.info("Check sell history page %d/%d", page, total_page)

    item_list: list[merhist.item.SoldItem] = []
    item_list_xpath = merhist.xpath.SOLD_LIST_ITEM
    for i in range(len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, item_list_xpath))):
        item_xpath = f"{item_list_xpath}[{i + 1}]"

        item = merhist.item.SoldItem()
        for col_def in col_def_list:
            col_xpath = merhist.xpath.sold_item_column(item_xpath, col_def.index)
            if col_def.type == "text":
                link_elem = driver.find_element(
                    selenium.webdriver.common.by.By.XPATH,
                    col_xpath + merhist.xpath.SOLD_ITEM_LINK,
                )
                item.set_field(col_def.name, link_elem.text)
                if col_def.link_name is not None:
                    item.set_field(col_def.link_name, link_elem.get_attribute("href"))
            elif col_def.type == "price":
                price_text = driver.find_element(
                    selenium.webdriver.common.by.By.XPATH,
                    col_xpath + merhist.xpath.SOLD_ITEM_PRICE_NUMBER,
                ).text
                item.set_field(col_def.name, merhist.parser.parse_price(price_text))
            elif col_def.type == "rate":
                rate_text = driver.find_element(
                    selenium.webdriver.common.by.By.XPATH,
                    col_xpath,
                ).text
                item.set_field(col_def.name, merhist.parser.parse_rate(rate_text))
            elif col_def.type == "date":
                item.set_field(
                    col_def.name,
                    merhist.parser.parse_date(
                        driver.find_element(
                            selenium.webdriver.common.by.By.XPATH,
                            col_xpath,
                        ).text
                    ),
                )

        _set_item_id_from_order_url(item)

        item_list.append(item)

        if handle.debug_mode:
            break

    is_found_new = False
    is_first_fetch = True
    for item in item_list:
        if not continue_mode or not handle.get_sold_item_stat(item):
            # 強制取得モードまたは未キャッシュの場合は取得
            _fetch_item_detail(handle, item)

            if item.error and is_first_fetch:
                # 最初のfetchが失敗した場合は収集を停止
                logging.error("最初のアイテム取得に失敗したため、収集を停止します")
                raise merhist.exceptions.HistoryFetchError(item.error)

            is_first_fetch = False
            handle.record_sold_item(item)
            is_found_new = True

            handle.store_trading_info()
        else:
            logging.info("%s %s円 [cached]", item.name, f"{item.price:,}")

        # キャッシュ済みでも「確認した」としてプログレスを更新
        handle.get_progress_bar(_STATUS_SOLD_ITEM).update()

    time.sleep(_PAGE_TRANSITION_WAIT)

    return is_found_new


def _fetch_sold_count(handle: merhist.handle.Handle) -> None:
    driver, _ = handle.get_selenium_driver()

    handle.set_status("🔍 販売件数を取得しています...")

    logging.info(_gen_sell_hist_url(0))

    _visit_url(handle, _gen_sell_hist_url(0), merhist.xpath.SOLD_PAGING)

    paging_text = driver.find_element(selenium.webdriver.common.by.By.XPATH, merhist.xpath.SOLD_PAGING).text
    sold_count = merhist.parser.parse_sold_count(paging_text)

    logging.info("Total sold items: %s", f"{sold_count:,}")

    handle.trading.sold_total_count = sold_count


def _fetch_sold_item_list(handle: merhist.handle.Handle, continue_mode: bool = True) -> None:
    handle.set_status("📥 販売履歴の収集を開始します...")

    _fetch_sold_count(handle)

    total_page = math.ceil(handle.trading.sold_total_count / merhist.const.SOLD_ITEM_PER_PAGE)

    handle.set_progress_bar(_STATUS_SOLD_PAGE, total_page)
    handle.set_progress_bar(_STATUS_SOLD_ITEM, handle.trading.sold_total_count)
    # NOTE: 各アイテムを確認するたびに update するため、初期 update は不要

    page = 1
    while True:
        # シャットダウンリクエストがあれば終了
        if is_shutdown_requested():
            logging.info("シャットダウンリクエストにより処理を中断します")
            break

        if continue_mode and handle.get_sold_checked_count() >= handle.trading.sold_total_count:
            if page == 1:
                logging.info("No new items")
            break

        is_found_new = _fetch_sold_item_list_by_page(handle, page, continue_mode)

        if continue_mode and (not is_found_new):
            logging.info("Leaving as it seems there are no more new items...")
            break
        handle.get_progress_bar(_STATUS_SOLD_PAGE).update()

        if page == total_page:
            break

        if handle.debug_mode:
            break

        page += 1

    # NOTE: continue_mode で早期終了した場合、残りのページのアイテムはキャッシュ済みと見なし、
    # プログレスバーを完了に持っていく（スキップされたページのアイテムは未カウントのため）
    if not is_shutdown_requested():
        sold_item_bar = handle.get_progress_bar(_STATUS_SOLD_ITEM)
        sold_item_bar.update(sold_item_bar.total - sold_item_bar.count)

        sold_page_bar = handle.get_progress_bar(_STATUS_SOLD_PAGE)
        sold_page_bar.update(sold_page_bar.total - sold_page_bar.count)

    handle.store_trading_info()

    if not is_shutdown_requested():
        handle.set_status("✅ 販売履歴の収集が完了しました")


def _get_bought_item_info_list(
    handle: merhist.handle.Handle,
    page: int,
    offset: int,
    item_list: list[merhist.item.BoughtItem],
    continue_mode: bool = True,
) -> tuple[int, bool]:
    driver, _ = handle.get_selenium_driver()

    item_list_xpath = merhist.xpath.BOUGHT_LIST_ITEM
    list_length = len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, item_list_xpath))
    prev_length = len(item_list)

    if list_length < offset:
        raise merhist.exceptions.HistoryFetchError("購入履歴の読み込みが正常にできていません")

    logging.info("There are %d items in page %s", list_length - offset, f"{page:,}")

    is_found_new = False
    for i in range(offset, list_length):
        item = merhist.item.BoughtItem()
        item_xpath = merhist.xpath.nth_element(item_list_xpath, i + 1)

        item.name = driver.find_element(
            selenium.webdriver.common.by.By.XPATH, item_xpath + merhist.xpath.BOUGHT_ITEM_LABEL
        ).text
        item.order_url = (
            driver.find_element(
                selenium.webdriver.common.by.By.XPATH, item_xpath + merhist.xpath.BOUGHT_ITEM_LINK
            ).get_attribute("href")
            or ""
        )

        # 日時テキストを取得（例: "2025/12/05 21:44"）
        datetime_text = driver.find_element(
            selenium.webdriver.common.by.By.XPATH,
            item_xpath + merhist.xpath.BOUGHT_ITEM_DATETIME,
        ).text

        item.purchase_date = merhist.parser.parse_datetime(datetime_text, False)

        _set_item_id_from_order_url(item)

        if not handle.get_bought_item_stat(item):
            item_list.append(item)
            is_found_new = True
        elif not continue_mode:
            # 強制取得モードの場合はキャッシュ済みでもリストに追加
            item_list.append(item)

    logging.info("Found %d new items in page %s", len(item_list) - prev_length, f"{page:,}")

    return (list_length, is_found_new)


def _fetch_bought_item_info_list_impl(
    handle: merhist.handle.Handle, continue_mode: bool
) -> list[merhist.item.BoughtItem]:
    driver, wait = handle.get_selenium_driver()

    _visit_url(handle, merhist.const.BOUGHT_HIST_URL, merhist.xpath.BOUGHT_LIST)

    item_list: list[merhist.item.BoughtItem] = []
    page = 1
    offset = 0
    while True:
        offset, is_found_new = _get_bought_item_info_list(handle, page, offset, item_list, continue_mode)
        page += 1

        if continue_mode and (not is_found_new):
            logging.info("Leaving as it seems there are no more new items...")
            break

        if not my_lib.selenium_util.xpath_exists(driver, merhist.xpath.BOUGHT_MORE_BUTTON):
            logging.info("Detected end of list")
            break

        logging.info("Load next items")

        my_lib.selenium_util.click_xpath(driver, merhist.xpath.BOUGHT_MORE_BUTTON)
        wait.until(
            selenium.webdriver.support.expected_conditions.invisibility_of_element_located(
                (selenium.webdriver.common.by.By.XPATH, merhist.xpath.LOADING_ICON)
            )
        )

        if handle.debug_mode:
            break

        time.sleep(_MORE_LOAD_WAIT)

    return item_list


def _fetch_bought_item_info_list(
    handle: merhist.handle.Handle, continue_mode: bool
) -> list[merhist.item.BoughtItem]:
    driver, _ = handle.get_selenium_driver()

    handle.set_status("🔍 購入履歴の件数を確認しています...")

    for i in range(_FETCH_RETRY_COUNT):
        if i != 0:
            logging.info("Retry %s", driver.current_url)
            time.sleep(_RETRY_WAIT_BASE)

        try:
            return _fetch_bought_item_info_list_impl(handle, continue_mode)
        except Exception:
            if i == _FETCH_RETRY_COUNT - 1:
                logging.error("Give up to fetch %s", driver.current_url)
                raise
            else:
                logging.exception("Failed to fetch %s", driver.current_url)

    return []  # pragma: no cover  # NOTE: ここには来ない


def _fetch_bought_item_list(handle: merhist.handle.Handle, continue_mode: bool = True) -> None:
    driver, _ = handle.get_selenium_driver()

    handle.set_status("📥 購入履歴の収集を開始します...")

    item_list = _fetch_bought_item_info_list(handle, continue_mode)

    handle.set_status("🔍 購入履歴の詳細情報を収集しています...")

    handle.set_progress_bar(_STATUS_BOUGHT_ITEM, len(item_list))

    is_first_fetch = True
    for item in item_list:
        # シャットダウンリクエストがあれば終了
        if is_shutdown_requested():
            logging.info("シャットダウンリクエストにより処理を中断します")
            break

        if not continue_mode or not handle.get_bought_item_stat(item):
            # 強制取得モードまたは未キャッシュの場合は取得
            _fetch_item_detail(handle, item)

            if item.error and is_first_fetch:
                # 最初のfetchが失敗した場合は収集を停止
                logging.error("最初のアイテム取得に失敗したため、収集を停止します")
                raise merhist.exceptions.HistoryFetchError(item.error)

            is_first_fetch = False
            handle.record_bought_item(item)
        else:
            logging.info("%s [cached]", item.name)

        # キャッシュ済みでも「確認した」としてプログレスを更新
        handle.get_progress_bar(_STATUS_BOUGHT_ITEM).update()

        handle.store_trading_info()

        if handle.debug_mode:
            break

    if not is_shutdown_requested():
        handle.set_status("✅ 購入履歴の収集が完了しました")


def fetch_order_item_list(handle: merhist.handle.Handle, continue_mode: ContinueMode) -> None:
    handle.set_status("🤖 巡回ロボットの準備をしています...")
    handle.get_selenium_driver()  # ドライバを初期化

    # シグナルハンドラを設定
    my_lib.graceful_shutdown.set_live_display(handle)
    my_lib.graceful_shutdown.setup_signal_handler()
    my_lib.graceful_shutdown.reset_shutdown_flag()

    handle.set_status("📥 注文履歴の収集を開始します...")

    _fetch_sold_item_list(handle, continue_mode.sold)
    if not is_shutdown_requested():
        _fetch_bought_item_list(handle, continue_mode.bought)

    if is_shutdown_requested():
        handle.set_status("🛑 注文履歴の収集を中断しました")
    else:
        handle.set_status("✅ 注文履歴の収集が完了しました")


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    import merhist.config

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    order_id = args["-o"]
    bought_list = args["-B"]
    sold_list = args["-S"]
    force_bought = args["--fB"]
    force_sold = args["--fS"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = merhist.config.Config.load(my_lib.config.load(config_file))
    handle = merhist.handle.Handle(config, debug_mode=debug_mode)

    handle.get_selenium_driver()  # ドライバを初期化

    try:
        execute_login(handle)

        if order_id is not None:
            item = merhist.item.SoldItem(id=order_id)
            if order_id.startswith("m"):
                item.shop = _MERCARI_NORMAL
            else:
                item.shop = _MERCARI_SHOP

            _fetch_item_transaction(handle, item)
            logging.info(item.to_dict())
        elif bought_list or force_bought:
            _fetch_bought_item_list(handle, continue_mode=not force_bought)
        elif sold_list or force_sold:
            _fetch_sold_item_list(handle, continue_mode=not force_sold)
        else:
            logging.warning("No command found to execute")

    except Exception:
        logging.exception("Failed to fetch data")
        driver, _ = handle.get_selenium_driver()
        my_lib.selenium_util.dump_page(
            driver,
            merhist.const.gen_debug_dump_id(),
            handle.config.debug_dir_path,
        )
    finally:
        handle.finish()
