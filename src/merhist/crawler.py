#!/usr/bin/env python3
"""
メルカリから販売履歴や購入履歴を収集します。

Usage:
  crawler.py [-c CONFIG] [-o BOUGHT_ID] [-B] [-S]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -o ORDER_ID       : 商品データを取得します。
  -B                : 購入商品リストを取得します。
  -S                : 販売商品リストを取得します。
"""

import datetime
import logging
import math
import pathlib
import random
import re
import time
import traceback

import merhist.const
import merhist.handle
import my_lib.selenium_util
import my_lib.store.mercari.login
import selenium.webdriver.common.by
import selenium.webdriver.support
import zoneinfo

STATUS_SOLD_ITEM = "[collect] Sold items"
STATUS_SOLD_PAGE = "[collect] Sold pages"
STATUS_BOUGHT_ITEM = "[collect] Bought items"


LOGIN_RETRY_COUNT = 2
FETCH_RETRY_COUNT = 3

MERCARI_NORMAL = "mercari.com"
MERCARI_SHOP = "mercari-shops.com"

TIMEZONE = zoneinfo.ZoneInfo("Asia/Tokyo")


def wait_for_loading(
    handle, xpath='//button[contains(@class, "iconButton") and @aria-label="お知らせ"]', sec=1
):
    driver, wait = merhist.handle.get_selenium_driver(handle)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_all_elements_located(
            (selenium.webdriver.common.by.By.XPATH, xpath)
        )
    )
    time.sleep(sec)


def parse_date(date_text):
    return datetime.datetime.strptime(date_text, "%Y/%m/%d").replace(tzinfo=TIMEZONE)


def parse_datetime(datetime_text, is_japanese=True):
    if is_japanese:
        return datetime.datetime.strptime(datetime_text, "%Y年%m月%d日 %H:%M").replace(tzinfo=TIMEZONE)
    else:
        return datetime.datetime.strptime(datetime_text, "%Y/%m/%d %H:%M").replace(tzinfo=TIMEZONE)


def gen_sell_hist_url(page):
    return merhist.const.SOLD_HIST_URL.format(page=page)


def gen_item_transaction_url(item_info):
    if item_info["shop"] == MERCARI_SHOP:
        return merhist.const.ITEM_SHOP_TRANSACTION_URL.format(id=item_info["id"])
    else:
        return merhist.const.ITEM_NORMAL_TRANSACTION_URL.format(id=item_info["id"])


def gen_item_description_url(item_info):
    if item_info["shop"] == MERCARI_SHOP:
        return merhist.const.ITEM_SHOP_DESCRIPTION_URL.format(id=item_info["id"])
    else:
        return merhist.const.ITEM_NORMAL_DESCRIPTION_URL.format(id=item_info["id"])


def set_item_id_from_order_url(item):
    if re.match(r".*/.*mercari\.com", item["order_url"]):
        item["id"] = re.match(r".*/(m\d+)/?", item["order_url"]).group(1)
        item["shop"] = MERCARI_NORMAL
    elif re.match(r".*.mercari-shops\.com", item["order_url"]):
        item["id"] = re.match(r".*/orders/(\w+)/?", item["order_url"]).group(1)
        item["shop"] = MERCARI_SHOP
    else:
        logging.error("Unexpected URL format: %s", item["order_url"])
        raise Exception("URL の形式が想定と異なります．")  # noqa: TRY002, TRY003, EM101


def visit_url(handle, url, xpath='//div[@class="merNavigationTop"]'):
    driver, wait = merhist.handle.get_selenium_driver(handle)
    driver.get(url)

    wait_for_loading(handle, xpath)


def save_thumbnail(handle, item, thumb_url):
    driver, wait = merhist.handle.get_selenium_driver(handle)

    with my_lib.selenium_util.browser_tab(driver, thumb_url):
        png_data = driver.find_element(selenium.webdriver.common.by.By.XPATH, "//img").screenshot_as_png

        with pathlib.Path(merhist.handle.get_thumb_path(handle, item)).open("wb") as f:
            f.write(png_data)


def fetch_item_description(handle, item_info):
    INFO_ROW_XPATH = (
        '//div[contains(@class, "merHeading") and div[h2[contains(text(), "商品の情報")]]]'
        '/following-sibling::div//div[contains(@class, "merDisplayRow")]'
    )
    ROW_DEF_LIST = [
        {"title": "カテゴリー", "type": "category", "name": "category"},
        {"title": "商品の状態", "type": "text", "name": "condition"},
        {"title": "配送料の負担", "type": "text", "name": "postage_charge"},
        {"title": "発送元の地域", "type": "text", "name": "seller_region"},
        {"title": "配送の方法", "type": "text", "name": "shipping_method"},
    ]

    driver, wait = merhist.handle.get_selenium_driver(handle)

    with my_lib.selenium_util.browser_tab(driver, gen_item_description_url(item_info)):
        wait_for_loading(handle)

        item = {
            "category": [],
            "condition": "",
            "postage_charge": "",
            "seller_region": "",
            "shipping_method": "",
        }

        if my_lib.selenium_util.xpath_exists(
            driver,
            (
                '//div[contains(@class, "merEmptyState")]'
                '//div[contains(@class, "titleContainer")]'
                '/p[contains(text(), "見つかりません")]'
            ),
        ):
            logging.warning("Description page not found: %s", driver.current_url)
            item["error"] = "商品情報ページが見つかりませんでした．"
            return item
        elif my_lib.selenium_util.xpath_exists(
            driver,
            (
                '//div[contains(@class, "merEmptyState")]//div[contains(@class, "titleContainer")]'
                '/p[contains(text(), "削除されました")]'
            ),
        ):
            logging.warning("Description page has been deleted: %s", driver.current_url)
            item["error"] = "商品情報ページが削除されています．"
            return item

        for i in range(len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, INFO_ROW_XPATH))):
            row_xpath = f"({INFO_ROW_XPATH})[{i + 1}]"

            row_title = driver.find_element(
                selenium.webdriver.common.by.By.XPATH, row_xpath + '//div[contains(@class, "title")]'
            ).text
            for row_def in ROW_DEF_LIST:
                if row_def["title"] != row_title:
                    continue

                if row_def["type"] == "text":
                    item[row_def["name"]] = driver.find_element(
                        selenium.webdriver.common.by.By.XPATH, row_xpath + '//div[contains(@class, "body")]'
                    ).text
                elif row_def["type"] == "category":
                    breadcrumb_list = driver.find_elements(
                        selenium.webdriver.common.by.By.XPATH,
                        row_xpath
                        + '//div[contains(@class, "body")]//span[contains(@class, "merTextLink")]/a',
                    )
                    item[row_def["name"]] = [x.text for x in breadcrumb_list]
        return item


def fetch_item_transaction_normal(handle, item_info):
    INFO_ROW_XPATH = (
        '//div[contains(@data-testid, "transaction:information-for-")]'
        '//div[contains(@class, "merDisplayRow")]'
    )
    ROW_DEF_LIST = [
        {"title": "購入日時", "type": "datetime", "name": "purchase_date"},
        {"title": "商品代金", "type": "price", "name": "price"},
        {"title": "送料", "type": "postage", "name": "postage"},
    ]
    driver, wait = merhist.handle.get_selenium_driver(handle)

    visit_url(
        handle,
        gen_item_transaction_url(item_info),
        '//div[contains(@data-testid, "transaction")]//div[contains(@class, "merListItem")][1]',
    )

    if my_lib.selenium_util.xpath_exists(
        driver,
        (
            '//div[contains(@class, "merEmptyState")]'
            '//div[contains(@class, "titleContainer")]'
            '/p[contains(text(), "ページの読み込みに失敗")]'
        ),
    ):
        logging.warning("Failed to load page: %s", driver.current_url)
        raise Exception("ページの読み込みに失敗しました")  # noqa: TRY002, EM101

    item = {}
    for i in range(len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, INFO_ROW_XPATH))):
        row_xpath = f"({INFO_ROW_XPATH})[{i + 1}]"

        row_title = driver.find_element(
            selenium.webdriver.common.by.By.XPATH, row_xpath + '//div[contains(@class, "title")]'
        ).text
        for row_def in ROW_DEF_LIST:
            if row_def["title"] != row_title:
                continue

            if row_def["type"] == "price":
                item[row_def["name"]] = int(
                    driver.find_element(
                        selenium.webdriver.common.by.By.XPATH,
                        row_xpath + '//div[contains(@class, "body")]//span[contains(@class, "number")]',
                    ).text.replace(",", "")
                )
            elif row_def["type"] == "datetime":
                item[row_def["name"]] = parse_datetime(
                    driver.find_element(
                        selenium.webdriver.common.by.By.XPATH, row_xpath + '//div[contains(@class, "body")]'
                    ).text
                )

    thumb_url = driver.find_element(
        selenium.webdriver.common.by.By.XPATH, '//div[contains(@class, "merItemThumbnail")]//picture/img'
    ).get_attribute("src")

    save_thumbnail(handle, item_info, thumb_url)

    if "purchase_date" not in item:
        logging.error("Unexpected page format: %s", gen_item_transaction_url(item_info))
        raise Exception("ページの形式が想定と異なります．")  # noqa: TRY002, EM101

    return item


def fetch_item_transaction_shop(handle, item_info):
    INFO_XPATH = (
        '//h2[contains(@class, "chakra-heading") and contains(text(), "取引情報")]/following-sibling::ul'
    )

    driver, wait = merhist.handle.get_selenium_driver(handle)

    visit_url(handle, gen_item_transaction_url(item_info), '//div[@data-testid="photo-name"]')

    item = {}
    item["price"] = int(
        driver.find_element(
            selenium.webdriver.common.by.By.XPATH,
            INFO_XPATH
            + '//p[@data-testid="select-payment-method"]/ancestor::li[1]//p[contains(text(),"￥")]',
        )
        .text.replace("￥", "")
        .replace(",", "")
    )

    thumb_url = driver.find_element(
        selenium.webdriver.common.by.By.XPATH, INFO_XPATH + '//img[@alt="shop-image"]'
    ).get_attribute("src")
    save_thumbnail(handle, item_info, thumb_url)

    return item


def fetch_item_transaction(handle, item_info):
    if item_info["shop"] == MERCARI_SHOP:
        return fetch_item_transaction_shop(handle, item_info)
    else:
        return fetch_item_transaction_normal(handle, item_info)


def fetch_item_detail(handle, item_info):
    error_message = ""
    for i in range(FETCH_RETRY_COUNT):
        if i != 0:
            logging.info("Retry %s", gen_item_transaction_url(item_info))
            time.sleep(5 * i)

        try:
            item = item_info.copy()
            item["count"] = 1
            item["url"] = gen_item_description_url(item_info)
            item |= fetch_item_description(handle, item_info)
            item |= fetch_item_transaction(handle, item_info)

            logging.info(
                "%s %s %s円",
                item["purchase_date"].strftime("%Y年%m月%d日"),
                item["name"],
                f"{item['price']:,}",
            )

            return item
        except Exception as e:
            logging.warning(str(e))
            error_message = str(e)
            error_detail = traceback.format_exc()

        logging.warning("Failed to fetch %s", gen_item_transaction_url(item_info))

    logging.error(error_detail)
    logging.error("Give up to fetch %s", gen_item_transaction_url(item_info))

    item["error"] = error_message

    return item


def fetch_sell_item_list_by_page(handle, page):
    ITEM_XPATH = (
        '(//div[contains(@class, "merTable")]/div[contains(@class, "merTableRowGroup")])[2]'
        '//div[contains(@class, "merTableRow")]'
    )
    COL_DEF_LIST = [
        {"index": 1, "type": "text", "name": "name", "link": {"name": "order_url"}},
        {"index": 2, "type": "price", "name": "price"},
        {"index": 3, "type": "price", "name": "commission"},
        {"index": 4, "type": "price", "name": "postage"},
        {"index": 6, "type": "rate", "name": "commission_rate"},
        {"index": 7, "type": "price", "name": "profit"},
        {"index": 9, "type": "date", "name": "completion_date"},
    ]
    driver, wait = merhist.handle.get_selenium_driver(handle)

    total_page = math.ceil(merhist.handle.get_sold_total_count(handle) / merhist.const.SOLD_ITEM_PER_PAGE)

    merhist.handle.set_status(handle, f"販売履歴を解析しています... {page}/{total_page} ページ")

    visit_url(handle, gen_sell_hist_url(page), merhist.const.SOLD_HIST_PAGING_XPATH)

    logging.info("Check sell history page %d/%d", page, total_page)

    item_list = []
    for i in range(len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, ITEM_XPATH))):
        item_xpath = f"{ITEM_XPATH}[{i + 1}]"

        item = {"count": 1}
        for col_def in COL_DEF_LIST:
            if col_def["type"] == "text":
                item[col_def["name"]] = driver.find_element(
                    selenium.webdriver.common.by.By.XPATH,
                    (
                        f'({item_xpath}//div[contains(@class, "merTableCell")])'
                        f'[{col_def["index"]}]//span[contains(@class, "merTextLink")]//a'
                    ),
                ).text
                if "link" in col_def:
                    item[col_def["link"]["name"]] = driver.find_element(
                        selenium.webdriver.common.by.By.XPATH,
                        (
                            f'({item_xpath}//div[contains(@class, "merTableCell")])'
                            f'[{col_def["index"]}]//span[contains(@class, "merTextLink")]//a'
                        ),
                    ).get_attribute("href")
            elif col_def["type"] == "price":
                item[col_def["name"]] = int(
                    driver.find_element(
                        selenium.webdriver.common.by.By.XPATH,
                        (
                            f'({item_xpath}//div[contains(@class, "merTableCell")])'
                            f'[{col_def["index"]}]//span[contains(@class, "merPrice")]'
                            f'/span[contains(@class, "number")]'
                        ),
                    ).text.replace(",", "")
                )
            elif col_def["type"] == "rate":
                item[col_def["name"]] = int(
                    driver.find_element(
                        selenium.webdriver.common.by.By.XPATH,
                        "("
                        + item_xpath
                        + "//div[contains(@class, 'merTableCell')])[{index}]".format(index=col_def["index"]),
                    ).text.replace("%", "")
                )
            elif col_def["type"] == "date":
                item[col_def["name"]] = parse_date(
                    driver.find_element(
                        selenium.webdriver.common.by.By.XPATH,
                        "("
                        + item_xpath
                        + "//div[contains(@class, 'merTableCell')])[{index}]".format(index=col_def["index"]),
                    ).text.replace("%", "")
                )

        set_item_id_from_order_url(item)

        item_list.append(item)

    is_found_new = False
    for item_info in item_list:
        if not merhist.handle.get_sold_item_stat(handle, item_info):
            merhist.handle.record_sold_item(handle, fetch_item_detail(handle, item_info))

            merhist.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).update()
            is_found_new = True

            merhist.handle.store_trading_info(handle)
        else:
            logging.info("%s %s円 [cached]", item_info["name"], f"{item_info['price']:,}")

    time.sleep(1)

    return is_found_new


def fetch_sold_count(handle):
    driver, wait = merhist.handle.get_selenium_driver(handle)

    merhist.handle.set_status(handle, "販売件数を取得しています...")

    logging.info(gen_sell_hist_url(0))

    visit_url(handle, gen_sell_hist_url(0), merhist.const.SOLD_HIST_PAGING_XPATH)

    paging_text = driver.find_element(
        selenium.webdriver.common.by.By.XPATH, merhist.const.SOLD_HIST_PAGING_XPATH
    ).text
    sold_count = int(re.match(r".*全(\d+)件", paging_text).group(1))

    logging.info("Total sold items: %s", f"{sold_count:,}")

    merhist.handle.set_sold_total_count(handle, sold_count)


def fetch_sold_item_list(handle, is_continue_mode=True):
    merhist.handle.set_status(handle, "販売履歴の収集を開始します...")

    fetch_sold_count(handle)

    total_page = math.ceil(merhist.handle.get_sold_total_count(handle) / merhist.const.SOLD_ITEM_PER_PAGE)

    merhist.handle.set_progress_bar(handle, STATUS_SOLD_PAGE, total_page)
    merhist.handle.set_progress_bar(handle, STATUS_SOLD_ITEM, merhist.handle.get_sold_total_count(handle))
    merhist.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).update(
        merhist.handle.get_sold_checked_count(handle)
    )

    page = 1
    while True:
        if merhist.handle.get_sold_checked_count(handle) >= merhist.handle.get_sold_total_count(handle):
            if page == 1:
                logging.info("No new items")
            break

        is_found_new = fetch_sell_item_list_by_page(handle, page)

        if is_continue_mode and (not is_found_new):
            logging.info("Leaving as it seems there are no more new items...")
            break
        merhist.handle.get_progress_bar(handle, STATUS_SOLD_PAGE).update()

        if page == total_page:
            break

        page += 1

    # NOTE: ここまできた時には全て完了しているはずなので，強制的にプログレスバーを完了に持っていく
    merhist.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).update(
        merhist.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).total
        - merhist.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).count
    )
    merhist.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).update()

    merhist.handle.get_progress_bar(handle, STATUS_SOLD_PAGE).update(
        merhist.handle.get_progress_bar(handle, STATUS_SOLD_PAGE).total
        - merhist.handle.get_progress_bar(handle, STATUS_SOLD_PAGE).count
    )
    merhist.handle.get_progress_bar(handle, STATUS_SOLD_PAGE).update()

    merhist.handle.set_sold_checked_count(handle, merhist.handle.get_sold_total_count(handle))
    merhist.handle.store_trading_info(handle)

    merhist.handle.set_status(handle, "販売履歴の収集が完了しました．")


def get_bought_item_info_list(handle, page, offset, item_info_list):
    ITEM_XPATH = merhist.const.BOUGHT_HIST_ITEM_XPATH + '/div[contains(@class, "content")]'

    driver, wait = merhist.handle.get_selenium_driver(handle)

    list_length = len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, ITEM_XPATH))
    prev_length = len(item_info_list)

    if list_length < offset:
        raise Exception("購入履歴の読み込みが正常にできていません．")  # noqa: EM101, TRY002

    logging.info("There are %d items in page %s", list_length - offset, f"{page:,}")

    is_found_new = False
    for i in range(offset, list_length):
        item_info = {}
        item_xpath = f"({ITEM_XPATH})[{i + 1}]"

        item_info["name"] = driver.find_element(
            selenium.webdriver.common.by.By.XPATH, item_xpath + '//span[contains(@class, "itemLabel")]'
        ).text
        item_info["order_url"] = driver.find_element(
            selenium.webdriver.common.by.By.XPATH, item_xpath + "//a"
        ).get_attribute("href")

        item_info["purchase_date"] = parse_datetime(
            driver.find_element(
                selenium.webdriver.common.by.By.XPATH,
                item_xpath + '//div[contains(@class, "metaContainer")]//span[contains(@class, "iconText")]',
            ).text,
            False,
        )

        set_item_id_from_order_url(item_info)

        if not merhist.handle.get_bought_item_stat(handle, item_info):
            item_info_list.append(item_info)
            is_found_new = True

    logging.info("Found %d new items in page %s", len(item_info_list) - prev_length, f"{page:,}")

    return (list_length, is_found_new)


def fetch_bought_item_info_list_impl(handle, is_continue_mode):
    MORE_BUTTON_XPATH = '//div[contains(@class, "merButton")]/button[contains(text(), "もっと見る")]'

    driver, wait = merhist.handle.get_selenium_driver(handle)

    merhist.handle.set_status(handle, "購入履歴の件数を確認しています...")

    visit_url(handle, merhist.const.BOUGHT_HIST_URL, merhist.const.BOUGHT_HIST_ITEM_XPATH)

    item_info_list = []
    page = 1
    offset = 0
    while True:
        offset, is_found_new = get_bought_item_info_list(handle, page, offset, item_info_list)
        page += 1

        if is_continue_mode and (not is_found_new):
            logging.info("Leaving as it seems there are no more new items...")
            break

        if not my_lib.selenium_util.xpath_exists(driver, MORE_BUTTON_XPATH):
            logging.info("Detected end of list")
            break

        logging.info("Load next items")

        my_lib.selenium_util.click_xpath(driver, MORE_BUTTON_XPATH)
        wait.until(
            selenium.webdriver.support.expected_conditions.invisibility_of_element_located(
                (selenium.webdriver.common.by.By.XPATH, merhist.const.LOADING_BUTTON_XPATH)
            )
        )

    return item_info_list


def fetch_bought_item_info_list(handle, is_continue_mode):
    driver, wait = merhist.handle.get_selenium_driver(handle)

    merhist.handle.set_status(handle, "購入履歴の件数を確認しています...")

    for i in range(FETCH_RETRY_COUNT):
        if i != 0:
            logging.info("Retry %s", driver.current_url)
            time.sleep(5)

        try:
            return fetch_bought_item_info_list_impl(handle, is_continue_mode)
        except Exception:
            my_lib.selenium_util.dump_page(
                driver,
                int(random.random() * 100),  # noqa: S311
                merhist.handle.get_debug_dir_path(handle),
            )

            logging.exception("Failed to fetch %s", driver.current_url)

    logging.error("Give up to fetch %s", driver.current_url)

    return []


def fetch_bought_item_list(handle, is_continue_mode=True):
    driver, wait = merhist.handle.get_selenium_driver(handle)

    merhist.handle.set_status(handle, "購入履歴の収集を開始します...")

    item_info_list = fetch_bought_item_info_list(handle, is_continue_mode)

    merhist.handle.set_status(handle, "購入履歴の詳細情報を収集しています...")

    merhist.handle.set_progress_bar(handle, STATUS_BOUGHT_ITEM, len(item_info_list))

    for item_info in item_info_list:
        if not merhist.handle.get_bought_item_stat(handle, item_info):
            merhist.handle.record_bought_item(handle, fetch_item_detail(handle, item_info))
            merhist.handle.get_progress_bar(handle, STATUS_BOUGHT_ITEM).update()
        else:
            logging.info("%s %s円 [cached]", item_info["name"], f"{item_info["price"]:,}")

        merhist.handle.store_trading_info(handle)

    merhist.handle.get_progress_bar(handle, STATUS_BOUGHT_ITEM).update()

    merhist.handle.set_status(handle, "購入履歴の収集が完了しました．")


def fetch_order_item_list(handle, is_continue_mode=True):
    merhist.handle.set_status(handle, "巡回ロボットの準備をします...")
    driver, wait = merhist.handle.get_selenium_driver(handle)

    merhist.handle.set_status(handle, "注文履歴の収集を開始します...")

    try:
        merhist.crawler.fetch_sold_item_list(handle, is_continue_mode)
        merhist.crawler.fetch_bought_item_list(handle, is_continue_mode)
    except:
        my_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),  # noqa: S311
            merhist.handle.get_debug_dir_path(handle),
        )
        raise

    merhist.handle.set_status(handle, "注文履歴の収集が完了しました．")


def execute_login(handle):
    driver, wait = merhist.handle.get_selenium_driver(handle)

    my_lib.store.mercari.login.execute(
        driver,
        wait,
        merhist.handle.get_line_user(handle),
        merhist.handle.get_line_pass(handle),
        merhist.handle.get_slack_config(handle),
        merhist.handle.get_debug_dir_path(handle),
    )


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config_file = args["-c"]
    order_id = args["-o"]
    bought_list = args["-B"]
    sold_list = args["-S"]

    config = my_lib.config.load(config_file)
    handle = merhist.handle.create(config)

    driver, wait = merhist.handle.get_selenium_driver(handle)

    try:
        execute_login(handle)

        if order_id is not None:
            item_info = {"id": order_id}
            if order_id.startswith("m"):
                item_info["shop"] = MERCARI_NORMAL
            else:
                item_info["shop"] = MERCARI_SHOP

            item = fetch_item_transaction(handle, item_info)
            logging.info(item)
        elif bought_list:
            fetch_bought_item_list(handle)
        elif sold_list:
            fetch_sold_item_list(handle, False)
        else:
            logging.warning("No command found to execute")

    except Exception:
        logging.exception("Failed to fetch data")
        driver, wait = merhist.handle.get_selenium_driver(handle)
        my_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),  # noqa: S311
            merhist.handle.get_debug_dir_path(handle),
        )
