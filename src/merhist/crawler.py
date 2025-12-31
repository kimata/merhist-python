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

import warnings

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")

import logging
import math
import pathlib
import random
import re
import time
import traceback
from typing import Any, TypedDict, TypeVar

import merhist.const
import merhist.exceptions
import merhist.handle
import merhist.item
import merhist.parser
import merhist.xpath

T = TypeVar("T", bound=merhist.item.ItemBase)

import my_lib.pretty
import my_lib.selenium_util
import my_lib.store.mercari.exceptions
import my_lib.store.mercari.login
import selenium.common.exceptions
import selenium.webdriver.common.by
import selenium.webdriver.support.expected_conditions
import selenium.webdriver.support.wait

STATUS_SOLD_PAGE: str = "[収集] 販売ページ"
STATUS_SOLD_ITEM: str = "[収集] 販売商品"
STATUS_BOUGHT_ITEM: str = "[収集] 購入商品"


LOGIN_RETRY_COUNT: int = 2
FETCH_RETRY_COUNT: int = 3

MERCARI_NORMAL: str = "mercari.com"
MERCARI_SHOP: str = "mercari-shops.com"


class ContinueMode(TypedDict):
    bought: bool
    sold: bool


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


def wait_for_loading(
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
            wait_for_loading(handle, xpath, sec, retry=False)
        else:
            raise
    time.sleep(sec)


def gen_sell_hist_url(page: int) -> str:
    return merhist.const.SOLD_HIST_URL.format(page=page)


def gen_item_transaction_url(item: merhist.item.ItemBase) -> str:
    if item.shop == MERCARI_SHOP:
        return merhist.const.ITEM_SHOP_TRANSACTION_URL.format(id=item.id)
    else:
        return merhist.const.ITEM_NORMAL_TRANSACTION_URL.format(id=item.id)


def gen_item_description_url(item: merhist.item.ItemBase) -> str:
    if item.shop == MERCARI_SHOP:
        return merhist.const.ITEM_SHOP_DESCRIPTION_URL.format(id=item.id)
    else:
        return merhist.const.ITEM_NORMAL_DESCRIPTION_URL.format(id=item.id)


def set_item_id_from_order_url(item: merhist.item.ItemBase) -> None:
    if match := re.match(r".*/.*mercari\.com.*/(m\d+)/?", item.order_url):
        item.id = match.group(1)
        item.shop = MERCARI_NORMAL
    elif match := re.match(r".*.mercari-shops\.com.*/orders/(\w+)/?", item.order_url):
        item.id = match.group(1)
        item.shop = MERCARI_SHOP
    else:
        logging.error("Unexpected URL format: %s", item.order_url)
        raise merhist.exceptions.InvalidURLFormatError("URL の形式が想定と異なります", item.order_url)


def visit_url(handle: merhist.handle.Handle, url: str, xpath: str = merhist.xpath.NAVIGATION_TOP) -> None:
    driver, _ = handle.get_selenium_driver()
    driver.get(url)

    wait_for_loading(handle, xpath)


def save_thumbnail(handle: merhist.handle.Handle, item: merhist.item.ItemBase, thumb_url: str) -> None:
    driver, _ = handle.get_selenium_driver()

    with my_lib.selenium_util.browser_tab(driver, thumb_url):
        png_data = driver.find_element(selenium.webdriver.common.by.By.XPATH, "//img").screenshot_as_png

        with pathlib.Path(handle.get_thumb_path(item)).open("wb") as f:
            f.write(png_data)


def fetch_item_description(handle: merhist.handle.Handle, item: merhist.item.ItemBase) -> None:
    ROW_DEF_LIST: list[dict[str, str]] = [
        {"title": "カテゴリー", "type": "category", "name": "category"},
        {"title": "商品の状態", "type": "text", "name": "condition"},
        {"title": "配送料の負担", "type": "text", "name": "postage_charge"},
        {"title": "発送元の地域", "type": "text", "name": "seller_region"},
        {"title": "配送の方法", "type": "text", "name": "shipping_method"},
    ]

    driver, _ = handle.get_selenium_driver()

    with my_lib.selenium_util.browser_tab(driver, gen_item_description_url(item)):
        wait_for_loading(handle)

        if my_lib.selenium_util.xpath_exists(driver, merhist.xpath.ITEM_DESC_NOT_FOUND):
            logging.warning("Description page not found: %s", driver.current_url)
            item.error = "商品情報ページが見つかりませんでした．"
            return
        elif my_lib.selenium_util.xpath_exists(driver, merhist.xpath.ITEM_DESC_DELETED):
            logging.warning("Description page has been deleted: %s", driver.current_url)
            item.error = "商品情報ページが削除されています．"
            return

        info_row_xpath = merhist.xpath.ITEM_DESC_INFO_ROW
        for i in range(len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, info_row_xpath))):
            row_xpath = merhist.xpath.nth_element(info_row_xpath, i + 1)

            row_title = driver.find_element(
                selenium.webdriver.common.by.By.XPATH, row_xpath + merhist.xpath.ITEM_DESC_ROW_TITLE
            ).text
            for row_def in ROW_DEF_LIST:
                if row_def["title"] != row_title:
                    continue

                if row_def["type"] == "text":
                    item.set_field(
                        row_def["name"],
                        driver.find_element(
                            selenium.webdriver.common.by.By.XPATH,
                            row_xpath + merhist.xpath.ITEM_DESC_ROW_BODY,
                        ).text,
                    )
                elif row_def["type"] == "category":
                    breadcrumb_list = driver.find_elements(
                        selenium.webdriver.common.by.By.XPATH,
                        row_xpath + merhist.xpath.ITEM_DESC_ROW_BODY_LINKS,
                    )
                    item.set_field(row_def["name"], [x.text for x in breadcrumb_list])


def fetch_item_transaction_normal(handle: merhist.handle.Handle, item: merhist.item.ItemBase) -> None:
    ROW_DEF_LIST: list[dict[str, str]] = [
        {"title": "購入日時", "type": "datetime", "name": "purchase_date"},
        {"title": "商品代金", "type": "price", "name": "price"},
        {"title": "配送料", "type": "price", "name": "postage"},
    ]

    driver, _ = handle.get_selenium_driver()

    visit_url(handle, gen_item_transaction_url(item), merhist.xpath.TRANSACTION_INFO_ROW)

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
        for row_def in ROW_DEF_LIST:
            if row_def["title"] != row_title:
                continue

            if row_def["type"] == "datetime":
                item.set_field(
                    row_def["name"],
                    merhist.parser.parse_datetime(
                        driver.find_element(
                            selenium.webdriver.common.by.By.XPATH,
                            row_xpath + merhist.xpath.TRANSACTION_ROW_BODY_SPAN,
                        ).text
                    ),
                )
                has_purchase_date = True
            elif row_def["type"] == "price":
                if not hasattr(item, row_def["name"]):
                    continue
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
                    row_def["name"],
                    merhist.parser.parse_price_with_shipping(body_text, number_text),
                )

    thumb_url = driver.find_element(
        selenium.webdriver.common.by.By.XPATH,
        merhist.xpath.TRANSACTION_THUMBNAIL,
    ).get_attribute("src")

    if thumb_url is not None:
        save_thumbnail(handle, item, thumb_url)

    if not has_purchase_date:
        logging.error("Unexpected page format: %s", gen_item_transaction_url(item))
        raise merhist.exceptions.InvalidPageFormatError(
            "ページの形式が想定と異なります", gen_item_transaction_url(item)
        )


def fetch_item_transaction_shop(handle: merhist.handle.Handle, item: merhist.item.BoughtItem) -> None:
    driver, _ = handle.get_selenium_driver()

    visit_url(handle, gen_item_transaction_url(item), merhist.xpath.SHOP_TRANSACTION_PHOTO_NAME)

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
        save_thumbnail(handle, item, thumb_url)


def fetch_item_transaction(handle: merhist.handle.Handle, item: merhist.item.ItemBase) -> None:
    if item.shop == MERCARI_SHOP:
        assert isinstance(item, merhist.item.BoughtItem)
        fetch_item_transaction_shop(handle, item)
    else:
        fetch_item_transaction_normal(handle, item)


def fetch_item_detail(handle: merhist.handle.Handle, item: T, debug_mode: bool) -> T:
    error_message = ""
    error_detail = ""

    for i in range(FETCH_RETRY_COUNT):
        if i != 0:
            logging.info("Retry %s", gen_item_transaction_url(item))
            time.sleep(5 * i)

        try:
            item.count = 1
            item.url = gen_item_description_url(item)
            fetch_item_description(handle, item)
            fetch_item_transaction(handle, item)

            if debug_mode:
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
                int(random.random() * 100),  # noqa: S311
                handle.config.debug_dir_path,
            )

        logging.warning("Failed to fetch %s", gen_item_transaction_url(item))

    logging.error(error_detail)
    logging.error("Give up to fetch %s", gen_item_transaction_url(item))

    item.error = error_message

    return item


def fetch_sold_item_list_by_page(
    handle: merhist.handle.Handle, page: int, continue_mode: bool, debug_mode: bool
) -> bool:
    COL_DEF_LIST: list[dict[str, Any]] = [
        {"index": 1, "type": "text", "name": "name", "link": {"name": "order_url"}},
        {"index": 2, "type": "price", "name": "price"},
        {"index": 3, "type": "price", "name": "commission"},
        {"index": 4, "type": "price", "name": "postage"},
        {"index": 6, "type": "rate", "name": "commission_rate"},
        {"index": 7, "type": "price", "name": "profit"},
        {"index": 9, "type": "date", "name": "completion_date"},
    ]
    driver, _ = handle.get_selenium_driver()

    total_page = math.ceil(handle.trading.sold_total_count / merhist.const.SOLD_ITEM_PER_PAGE)

    handle.set_status(f"販売履歴を解析しています... {page}/{total_page} ページ")

    visit_url(handle, gen_sell_hist_url(page), merhist.xpath.SOLD_PAGING)

    logging.info("Check sell history page %d/%d", page, total_page)

    item_list: list[merhist.item.SoldItem] = []
    item_list_xpath = merhist.xpath.SOLD_LIST_ITEM
    for i in range(len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, item_list_xpath))):
        item_xpath = f"{item_list_xpath}[{i + 1}]"

        item = merhist.item.SoldItem()
        for col_def in COL_DEF_LIST:
            col_xpath = merhist.xpath.sold_item_column(item_xpath, col_def["index"])
            if col_def["type"] == "text":
                link_elem = driver.find_element(
                    selenium.webdriver.common.by.By.XPATH,
                    col_xpath + merhist.xpath.SOLD_ITEM_LINK,
                )
                item.set_field(col_def["name"], link_elem.text)
                if "link" in col_def:
                    item.set_field(col_def["link"]["name"], link_elem.get_attribute("href"))
            elif col_def["type"] == "price":
                price_text = driver.find_element(
                    selenium.webdriver.common.by.By.XPATH,
                    col_xpath + merhist.xpath.SOLD_ITEM_PRICE_NUMBER,
                ).text
                item.set_field(col_def["name"], merhist.parser.parse_price(price_text))
            elif col_def["type"] == "rate":
                rate_text = driver.find_element(
                    selenium.webdriver.common.by.By.XPATH,
                    col_xpath,
                ).text
                item.set_field(col_def["name"], merhist.parser.parse_rate(rate_text))
            elif col_def["type"] == "date":
                item.set_field(
                    col_def["name"],
                    merhist.parser.parse_date(
                        driver.find_element(
                            selenium.webdriver.common.by.By.XPATH,
                            col_xpath,
                        ).text
                    ),
                )

        set_item_id_from_order_url(item)

        item_list.append(item)

        if debug_mode:
            break

    is_found_new = False
    is_first_fetch = True
    for item in item_list:
        if not continue_mode or not handle.get_sold_item_stat(item):
            # 強制取得モードまたは未キャッシュの場合は取得
            fetch_item_detail(handle, item, debug_mode)

            if item.error and is_first_fetch:
                # 最初のfetchが失敗した場合は収集を停止
                logging.error("最初のアイテム取得に失敗したため、収集を停止します")
                raise merhist.exceptions.HistoryFetchError(item.error)

            is_first_fetch = False
            handle.record_sold_item(item)

            handle.progress_bar[STATUS_SOLD_ITEM].update()
            is_found_new = True

            handle.store_trading_info()
        else:
            logging.info("%s %s円 [cached]", item.name, f"{item.price:,}")

    time.sleep(1)

    return is_found_new


def fetch_sold_count(handle: merhist.handle.Handle) -> None:
    driver, _ = handle.get_selenium_driver()

    handle.set_status("🔍 販売件数を取得しています...")

    logging.info(gen_sell_hist_url(0))

    visit_url(handle, gen_sell_hist_url(0), merhist.xpath.SOLD_PAGING)

    paging_text = driver.find_element(selenium.webdriver.common.by.By.XPATH, merhist.xpath.SOLD_PAGING).text
    sold_count = merhist.parser.parse_sold_count(paging_text)

    logging.info("Total sold items: %s", f"{sold_count:,}")

    handle.trading.sold_total_count = sold_count


def fetch_sold_item_list(
    handle: merhist.handle.Handle, continue_mode: bool = True, debug_mode: bool = False
) -> None:
    handle.set_status("📥 販売履歴の収集を開始します...")

    fetch_sold_count(handle)

    total_page = math.ceil(handle.trading.sold_total_count / merhist.const.SOLD_ITEM_PER_PAGE)

    handle.set_progress_bar(STATUS_SOLD_PAGE, total_page)
    handle.set_progress_bar(STATUS_SOLD_ITEM, handle.trading.sold_total_count)
    handle.progress_bar[STATUS_SOLD_ITEM].update(handle.get_sold_checked_count())

    page = 1
    while True:
        if continue_mode and handle.get_sold_checked_count() >= handle.trading.sold_total_count:
            if page == 1:
                logging.info("No new items")
            break

        is_found_new = fetch_sold_item_list_by_page(handle, page, continue_mode, debug_mode)

        if continue_mode and (not is_found_new):
            logging.info("Leaving as it seems there are no more new items...")
            break
        handle.progress_bar[STATUS_SOLD_PAGE].update()

        if page == total_page:
            break

        if debug_mode:
            break

        page += 1

    # NOTE: ここまできた時には全て完了しているはずなので，強制的にプログレスバーを完了に持っていく
    handle.progress_bar[STATUS_SOLD_ITEM].update(
        handle.progress_bar[STATUS_SOLD_ITEM].total - handle.progress_bar[STATUS_SOLD_ITEM].count
    )

    handle.progress_bar[STATUS_SOLD_PAGE].update(
        handle.progress_bar[STATUS_SOLD_PAGE].total - handle.progress_bar[STATUS_SOLD_PAGE].count
    )

    handle.store_trading_info()

    handle.set_status("✅ 販売履歴の収集が完了しました")


def get_bought_item_info_list(
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

        set_item_id_from_order_url(item)

        if not handle.get_bought_item_stat(item):
            item_list.append(item)
            is_found_new = True
        elif not continue_mode:
            # 強制取得モードの場合はキャッシュ済みでもリストに追加
            item_list.append(item)

    logging.info("Found %d new items in page %s", len(item_list) - prev_length, f"{page:,}")

    return (list_length, is_found_new)


def fetch_bought_item_info_list_impl(
    handle: merhist.handle.Handle, continue_mode: bool, debug_mode: bool
) -> list[merhist.item.BoughtItem]:
    driver, wait = handle.get_selenium_driver()

    handle.set_status("🔍 購入履歴の件数を確認しています...")

    visit_url(handle, merhist.const.BOUGHT_HIST_URL, merhist.xpath.BOUGHT_LIST)

    item_list: list[merhist.item.BoughtItem] = []
    page = 1
    offset = 0
    while True:
        offset, is_found_new = get_bought_item_info_list(handle, page, offset, item_list, continue_mode)
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

        if debug_mode:
            break

        time.sleep(3)

    return item_list


def fetch_bought_item_info_list(
    handle: merhist.handle.Handle, continue_mode: bool, debug_mode: bool
) -> list[merhist.item.BoughtItem]:
    driver, _ = handle.get_selenium_driver()

    handle.set_status("🔍 購入履歴の件数を確認しています...")

    for i in range(FETCH_RETRY_COUNT):
        if i != 0:
            logging.info("Retry %s", driver.current_url)
            time.sleep(5)

        try:
            return fetch_bought_item_info_list_impl(handle, continue_mode, debug_mode)
        except Exception:
            if i == FETCH_RETRY_COUNT - 1:
                logging.error("Give up to fetch %s", driver.current_url)
                raise
            else:
                logging.exception("Failed to fetch %s", driver.current_url)

    return []  # NOTE: ここには来ない


def fetch_bought_item_list(
    handle: merhist.handle.Handle, continue_mode: bool = True, debug_mode: bool = False
) -> None:
    driver, _ = handle.get_selenium_driver()

    handle.set_status("📥 購入履歴の収集を開始します...")

    item_list = fetch_bought_item_info_list(handle, continue_mode, debug_mode)

    handle.set_status("🔍 購入履歴の詳細情報を収集しています...")

    handle.set_progress_bar(STATUS_BOUGHT_ITEM, len(item_list))

    is_first_fetch = True
    for item in item_list:
        if not continue_mode or not handle.get_bought_item_stat(item):
            # 強制取得モードまたは未キャッシュの場合は取得
            fetch_item_detail(handle, item, debug_mode)

            if item.error and is_first_fetch:
                # 最初のfetchが失敗した場合は収集を停止
                logging.error("最初のアイテム取得に失敗したため、収集を停止します")
                raise merhist.exceptions.HistoryFetchError(item.error)

            is_first_fetch = False
            handle.record_bought_item(item)
            handle.progress_bar[STATUS_BOUGHT_ITEM].update()
        else:
            logging.info("%s [cached]", item.name)

        handle.store_trading_info()

        if debug_mode:
            break

    handle.set_status("✅ 購入履歴の収集が完了しました")


def fetch_order_item_list(
    handle: merhist.handle.Handle, continue_mode: ContinueMode, debug_mode: bool = False
) -> None:
    handle.set_status("🤖 巡回ロボットの準備をしています...")
    driver, _ = handle.get_selenium_driver()

    handle.set_status("📥 注文履歴の収集を開始します...")

    fetch_sold_item_list(handle, continue_mode["sold"], debug_mode)
    fetch_bought_item_list(handle, continue_mode["bought"], debug_mode)

    handle.set_status("✅ 注文履歴の収集が完了しました")


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    import merhist.config

    assert __doc__ is not None
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
    handle = merhist.handle.Handle(config)

    driver, _ = handle.get_selenium_driver()

    try:
        execute_login(handle)

        if order_id is not None:
            item = merhist.item.SoldItem(id=order_id)
            if order_id.startswith("m"):
                item.shop = MERCARI_NORMAL
            else:
                item.shop = MERCARI_SHOP

            fetch_item_transaction(handle, item)
            logging.info(item.to_dict())
        elif bought_list or force_bought:
            fetch_bought_item_list(handle, continue_mode=not force_bought, debug_mode=debug_mode)
        elif sold_list or force_sold:
            fetch_sold_item_list(handle, continue_mode=not force_sold, debug_mode=debug_mode)
        else:
            logging.warning("No command found to execute")

    except Exception:
        logging.exception("Failed to fetch data")
        driver, _ = handle.get_selenium_driver()
        my_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),  # noqa: S311
            handle.config.debug_dir_path,
        )
    finally:
        handle.finish()
