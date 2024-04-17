#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
メルカリから販売履歴や購入履歴を収集します．

Usage:
  crawler.py [-c CONFIG]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
"""

import logging
import random
import re
import datetime
import time
import traceback
import math

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

import mercari.const
import mercari.handle

import local_lib.captcha
import local_lib.selenium_util

STATUS_SOLD_ITEM = "[collect] Sold items"
STATUS_SOLD_PAGE = "[collect] Sold pages"
STATUS_BOUGHT_ITEM = "[collect] Bought items"


LOGIN_RETRY_COUNT = 2
FETCH_RETRY_COUNT = 3

LOGIN_URL = "https://jp.mercari.com"
ITEM_LIST_XPATH = '//div[@data-testid="listed-item-list"]//div[contains(@class, "merListItem")]'

MERCARI_NORMAL = "mercari.com"
MERCARI_SHOP = "mercari-shops.com"


def wait_for_loading(handle, xpath='//div[@class="merNavigationTop"]', sec=2):
    driver, wait = mercari.handle.get_selenium_driver(handle)

    wait.until(EC.visibility_of_all_elements_located((By.XPATH, xpath)))
    time.sleep(sec)


def parse_date(date_text):
    return datetime.datetime.strptime(date_text, "%Y/%m/%d")


def parse_datetime(datetime_text, is_japanese=True):
    if is_japanese:
        return datetime.datetime.strptime(datetime_text, "%Y年%m月%d日 %H:%M")
    else:
        return datetime.datetime.strptime(datetime_text, "%Y/%m/%d %H:%M")


def gen_sell_hist_url(page):
    return mercari.const.SELL_HIST_URL.format(page=page)


def gen_item_transaction_url(item_info):
    if item_info["shop"] == MERCARI_SHOP:
        return mercari.const.ITEM_SHOP_TRANSACTION_URL.format(id=item_info["id"])
    else:
        return mercari.const.ITEM_NORMAL_TRANSACTION_URL.format(id=item_info["id"])


def gen_item_description_url(item_info):
    if item_info["shop"] == MERCARI_SHOP:
        return mercari.const.ITEM_SHOP_DESCRIPTION_URL.format(id=item_info["id"])
    else:
        return mercari.const.ITEM_NORMAL_DESCRIPTION_URL.format(id=item_info["id"])


def set_item_id_from_url(item):
    if re.match(r".*/.*mercari\.com", item["url"]):
        item["id"] = re.match(r".*/(m\d+)/?", item["url"]).group(1)
        item["shop"] = MERCARI_NORMAL
    elif re.match(r".*.mercari-shops\.com", item["url"]):
        item["id"] = re.match(r".*/orders/(\w+)/?", item["url"]).group(1)
        item["shop"] = MERCARI_SHOP
    else:
        logging.error("Unexpected URL format: {url}".format(url=item["url"]))
        raise Exception("URL の形式が想定と異なります．")


def visit_url(handle, url, xpath='//div[@class="merNavigationTop"]'):
    driver, wait = mercari.handle.get_selenium_driver(handle)
    driver.get(url)

    wait_for_loading(handle, xpath)


def save_thumbnail(handle, item, thumb_url):
    driver, wait = mercari.handle.get_selenium_driver(handle)

    with local_lib.selenium_util.browser_tab(driver, thumb_url):
        png_data = driver.find_element(By.XPATH, "//img").screenshot_as_png

        with open(mercari.handle.get_thumb_path(handle, item), "wb") as f:
            f.write(png_data)


def fetch_item_description(handle, item_info):
    INFO_ROW_XPATH = (
        '//div[contains(@class, "merHeading") and '
        + 'div[h2[contains(text(), "商品の情報")]]]/following-sibling::div//div[contains(@class, "merDisplayRow")]'
    )
    ROW_DEF_LIST = [
        {"title": "カテゴリー", "type": "category", "name": "category"},
        {"title": "商品の状態", "type": "text", "name": "condition"},
        {"title": "配送料の負担", "type": "text", "name": "postage_charge"},
        {"title": "発送元の地域", "type": "text", "name": "seller_region"},
        {"title": "配送の方法", "type": "text", "name": "shipping_method"},
    ]

    driver, wait = mercari.handle.get_selenium_driver(handle)

    with local_lib.selenium_util.browser_tab(driver, gen_item_description_url(item_info)):
        wait_for_loading(handle)

        item = {
            "category": [],
            "condition": "",
            "postage_charge": "",
            "seller_region": "",
            "shipping_method": "",
        }

        if local_lib.selenium_util.xpath_exists(
            driver,
            '//div[contains(@class, "merEmptyState")]//div[contains(@class, "titleContainer")]'
            + '/p[contains(text(), "見つかりません")]',
        ):
            logging.warning("Description page not found: {url}".format(url=driver.current_url))
            item["error"] = "商品情報ページが見つかりませんでした．"
            return item
        elif local_lib.selenium_util.xpath_exists(
            driver,
            '//div[contains(@class, "merEmptyState")]//div[contains(@class, "titleContainer")]/'
            + 'p[contains(text(), "削除されました")]',
        ):
            logging.warning("Description page has been deleted: {url}".format(url=driver.current_url))
            item["error"] = "商品情報ページが削除されています．"
            return item

        for i in range(len(driver.find_elements(By.XPATH, INFO_ROW_XPATH))):
            row_xpath = "(" + INFO_ROW_XPATH + ")[{index}]".format(index=i + 1)

            row_title = driver.find_element(By.XPATH, row_xpath + '//div[contains(@class, "title")]').text
            for row_def in ROW_DEF_LIST:
                if row_def["title"] != row_title:
                    continue

                if row_def["type"] == "text":
                    item[row_def["name"]] = driver.find_element(
                        By.XPATH, row_xpath + '//div[contains(@class, "body")]'
                    ).text
                elif row_def["type"] == "category":
                    breadcrumb_list = driver.find_elements(
                        By.XPATH,
                        row_xpath
                        + '//div[contains(@class, "body")]//span[contains(@class, "merTextLink")]/a',
                    )
                    item[row_def["name"]] = list(map(lambda x: x.text, breadcrumb_list))
        return item


def fetch_item_normal_transaction(handle, item_info):
    INFO_ROW_XPATH = '//div[contains(@data-testid, "transaction:information-for-")]//div[contains(@class, "merDisplayRow")]'
    ROW_DEF_LIST = [
        {"title": "購入日時", "type": "datetime", "name": "purchase_date"},
        {"title": "商品代金", "type": "price", "name": "price"},
        {"title": "送料", "type": "postage", "name": "postage"},
    ]
    driver, wait = mercari.handle.get_selenium_driver(handle)

    visit_url(handle, gen_item_transaction_url(item_info))

    if local_lib.selenium_util.xpath_exists(
        driver,
        '//div[contains(@class, "merEmptyState")]//div[contains(@class, "titleContainer")]/p[contains(text(), "ページの読み込みに失敗")]',
    ):
        logging.warning("Failed to load page: {url}".format(url=driver.current_url))
        raise Exception("ページの読み込みに失敗しました")

    item = {}
    for i in range(len(driver.find_elements(By.XPATH, INFO_ROW_XPATH))):
        row_xpath = "(" + INFO_ROW_XPATH + ")[{index}]".format(index=i + 1)

        row_title = driver.find_element(By.XPATH, row_xpath + '//div[contains(@class, "title")]').text
        for row_def in ROW_DEF_LIST:
            if row_def["title"] != row_title:
                continue

            if row_def["type"] == "price":
                item[row_def["name"]] = int(
                    driver.find_element(
                        By.XPATH,
                        row_xpath + '//div[contains(@class, "body")]//span[contains(@class, "number")]',
                    ).text.replace(",", "")
                )
            elif row_def["type"] == "datetime":
                item[row_def["name"]] = parse_datetime(
                    driver.find_element(By.XPATH, row_xpath + '//div[contains(@class, "body")]').text
                )

    thumb_url = driver.find_element(
        By.XPATH, '//div[contains(@class, "merItemThumbnail")]//picture/img'
    ).get_attribute("src")

    save_thumbnail(handle, item_info, thumb_url)

    if "purchase_date" not in item:
        logging.error("Unexpected page format: {url}".format(url=gen_item_transaction_url(item_info)))
        raise Exception("ページの形式が想定と異なります．")

    return item


def fetch_item_shop_transaction(handle, item_info):
    INFO_XPATH = (
        '//h2[contains(@class, "chakra-heading") and contains(text(), "取引情報")]/following-sibling::ul/li[1]'
    )

    driver, wait = mercari.handle.get_selenium_driver(handle)

    visit_url(handle, gen_item_transaction_url(item_info), '//header[contains(@class, "chakra-stack")]')

    item = {}
    item["price"] = int(
        driver.find_element(By.XPATH, INFO_XPATH + '//p[contains(@class, "chakra-text")][last()]')
        .text.replace("￥", "")
        .replace(",", "")
    )

    thumb_url = driver.find_element(By.XPATH, INFO_XPATH + '//img[@alt="shop-image"]').get_attribute("src")
    save_thumbnail(handle, item_info, thumb_url)

    return item


def fetch_item_detail(handle, item_info):
    error_message = ""
    for i in range(FETCH_RETRY_COUNT):
        if i != 0:
            logging.info("Retry {url}".format(url=gen_item_transaction_url(item_info)))
            time.sleep(5 * i)

        try:
            item = item_info.copy()
            item |= fetch_item_description(handle, item_info)

            if item_info["shop"] == MERCARI_SHOP:
                item |= fetch_item_shop_transaction(handle, item_info)
            else:
                item |= fetch_item_normal_transaction(handle, item_info)

            logging.info(
                "{date} {name} {price:,}円".format(
                    date=item["purchase_date"].strftime("%Y年%m月%d日"), name=item["name"], price=item["price"]
                )
            )

            return item
        except Exception as e:
            logging.warning(str(e))
            error_message = str(e)
            error_detail = traceback.format_exc()
            pass

        logging.warning("Failed to fetch {url}".format(url=gen_item_transaction_url(item_info)))

    logging.error(error_detail)
    logging.error("Give up to fetch {url}".format(url=gen_item_transaction_url(item_info)))

    item["error"] = error_message

    return item


def fetch_sell_item_list_by_page(handle, page, retry=0):
    ITEM_XPATH = '(//div[contains(@class, "merTable")]/div[contains(@class, "merTableRowGroup")])[2]//div[contains(@class, "merTableRow")]'
    COL_DEF_LIST = [
        {"index": 1, "type": "text", "name": "name", "link": {"name": "url"}},
        {"index": 2, "type": "price", "name": "price"},
        {"index": 3, "type": "price", "name": "commission"},
        {"index": 4, "type": "price", "name": "postage"},
        {"index": 6, "type": "rate", "name": "commission_rate"},
        {"index": 7, "type": "price", "name": "profit"},
        {"index": 9, "type": "date", "name": "completion_date"},
    ]
    driver, wait = mercari.handle.get_selenium_driver(handle)

    total_page = math.ceil(mercari.handle.get_sold_total_count(handle) / mercari.const.SOLD_ITEM_PER_PAGE)

    mercari.handle.set_status(
        handle,
        "販売履歴を解析しています... {page}/{total_page} ページ".format(page=page, total_page=total_page),
    )

    visit_url(handle, gen_sell_hist_url(page))
    keep_logged_on(handle)

    logging.info("Check sell history page {page}/{total_page}".format(page=page, total_page=total_page))

    item_list = []
    for i in range(len(driver.find_elements(By.XPATH, ITEM_XPATH))):
        item_xpath = ITEM_XPATH + "[{index}]".format(index=i + 1)

        item = {}
        for col_def in COL_DEF_LIST:
            if col_def["type"] == "text":
                item[col_def["name"]] = driver.find_element(
                    By.XPATH,
                    "("
                    + item_xpath
                    + "//div[contains(@class, 'merTableCell')])[{index}]//span[contains(@class, 'merTextLink')]".format(
                        index=col_def["index"]
                    ),
                ).text
                if "link" in col_def:
                    item[col_def["link"]["name"]] = driver.find_element(
                        By.XPATH,
                        "("
                        + item_xpath
                        + "//div[contains(@class, 'merTableCell')])[{index}]//span[contains(@class, 'merTextLink')]//a".format(
                            index=col_def["index"]
                        ),
                    ).get_attribute("href")
            elif col_def["type"] == "price":
                item[col_def["name"]] = int(
                    driver.find_element(
                        By.XPATH,
                        "("
                        + item_xpath
                        + "//div[contains(@class, 'merTableCell')])[{index}]//span[contains(@class, 'merPrice')]/span[contains(@class, 'number')]".format(
                            index=col_def["index"]
                        ),
                    ).text.replace(",", "")
                )
            elif col_def["type"] == "rate":
                item[col_def["name"]] = int(
                    driver.find_element(
                        By.XPATH,
                        "("
                        + item_xpath
                        + "//div[contains(@class, 'merTableCell')])[{index}]".format(index=col_def["index"]),
                    ).text.replace("%", "")
                )
            elif col_def["type"] == "date":
                item[col_def["name"]] = parse_date(
                    driver.find_element(
                        By.XPATH,
                        "("
                        + item_xpath
                        + "//div[contains(@class, 'merTableCell')])[{index}]".format(index=col_def["index"]),
                    ).text.replace("%", "")
                )

        set_item_id_from_url(item)

        item_list.append(item)

    is_found_new = False
    for item_info in item_list:
        if not mercari.handle.get_sold_item_stat(handle, item_info):
            mercari.handle.record_sold_item(handle, fetch_item_detail(handle, item_info))

            mercari.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).update()
            is_found_new = True

            mercari.handle.store_trading_info(handle)
        else:
            logging.info(
                "{name} {price:,}円 [cached]".format(name=item_info["name"], price=item_info["price"])
            )

    time.sleep(1)

    return is_found_new


def fetch_sold_count(handle):
    driver, wait = mercari.handle.get_selenium_driver(handle)

    mercari.handle.set_status(handle, "販売件数を取得しています...")

    visit_url(handle, gen_sell_hist_url(0))
    keep_logged_on(handle)

    paging_text = driver.find_element(
        By.XPATH,
        '//div[contains(@class, "merTabPanel")]/following-sibling::p[contains(@class, "merText")]',
    ).text
    sold_count = int(re.match(r".*全(\d+)件", paging_text).group(1))

    logging.info("Total sold items: {count:,}".format(count=sold_count))

    mercari.handle.set_sold_total_count(handle, sold_count)


def fetch_sold_item_list(handle, is_continue_mode=True):
    mercari.handle.set_status(handle, "販売履歴の収集を開始します...")

    fetch_sold_count(handle)

    total_page = math.ceil(mercari.handle.get_sold_total_count(handle) / mercari.const.SOLD_ITEM_PER_PAGE)

    mercari.handle.set_progress_bar(handle, STATUS_SOLD_PAGE, total_page)
    mercari.handle.set_progress_bar(handle, STATUS_SOLD_ITEM, mercari.handle.get_sold_total_count(handle))
    mercari.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).update(
        mercari.handle.get_sold_checked_count(handle)
    )

    page = 1
    while True:
        if mercari.handle.get_sold_checked_count(handle) >= mercari.handle.get_sold_total_count(handle):
            if page == 1:
                logging.info("No new items")
            break

        is_found_new = fetch_sell_item_list_by_page(handle, page)

        if is_continue_mode and (not is_found_new):
            logging.info("Leaving as it seems there are no more new items...")
            break
        mercari.handle.get_progress_bar(handle, STATUS_SOLD_PAGE).update()

        if page == total_page:
            break

        page += 1

    # NOTE: ここまできた時には全て完了しているはずなので，強制的にプログレスバーを完了に持っていく
    mercari.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).update(
        mercari.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).total
        - mercari.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).count
    )
    mercari.handle.get_progress_bar(handle, STATUS_SOLD_ITEM).update()

    mercari.handle.get_progress_bar(handle, STATUS_SOLD_PAGE).update(
        mercari.handle.get_progress_bar(handle, STATUS_SOLD_PAGE).total
        - mercari.handle.get_progress_bar(handle, STATUS_SOLD_PAGE).count
    )
    mercari.handle.get_progress_bar(handle, STATUS_SOLD_PAGE).update()

    mercari.handle.set_sold_checked_count(handle, mercari.handle.get_sold_total_count(handle))
    mercari.handle.store_trading_info(handle)

    mercari.handle.set_status(handle, "販売履歴の収集が完了しました．")


def get_bought_item_info_list(handle, page, offset, item_info_list):
    ITEM_XPATH = '//div[@id="my-page-main-content"]//div[contains(@class, "merListItem")]/div[contains(@class, "content")]'

    driver, wait = mercari.handle.get_selenium_driver(handle)

    list_length = len(driver.find_elements(By.XPATH, ITEM_XPATH))
    prev_length = len(item_info_list)

    if list_length < offset:
        raise Exception("購入履歴の読み込みが正常にできていません．")

    logging.info(
        "There are {item_count} items in page {page:,}".format(item_count=list_length - offset, page=page)
    )

    is_found_new = False
    for i in range(offset, list_length):
        item_info = {}
        item_xpath = "(" + ITEM_XPATH + ")[{index}]".format(index=i + 1)

        item_info["name"] = driver.find_element(
            By.XPATH, item_xpath + '//span[contains(@class, "itemLabel")]'
        ).text
        item_info["url"] = driver.find_element(By.XPATH, item_xpath + "//a").get_attribute("href")

        item_info["purchase_date"] = parse_datetime(
            driver.find_element(
                By.XPATH,
                item_xpath + '//div[contains(@class, "metaContainer")]//span[contains(@class, "iconText")]',
            ).text,
            False,
        )

        set_item_id_from_url(item_info)

        if not mercari.handle.get_bought_item_stat(handle, item_info):
            item_info_list.append(item_info)
            is_found_new = True

    logging.info(
        "Found {item_count} new items in page {page:,}".format(
            item_count=len(item_info_list) - prev_length, page=page
        )
    )

    return (list_length, is_found_new)


def fetch_bought_item_info_list_impl(handle, is_continue_mode):
    MORE_BUTTON_XPATH = '//div[contains(@class, "merButton")]/button[contains(text(), "もっと見る")]'

    driver, wait = mercari.handle.get_selenium_driver(handle)

    mercari.handle.set_status(handle, "購入履歴の件数を確認しています...")

    visit_url(handle, mercari.const.BOUGHT_HIST_URL)
    keep_logged_on(handle)

    item_info_list = []
    page = 1
    offset = 0
    while True:
        offset, is_found_new = get_bought_item_info_list(handle, page, offset, item_info_list)
        page += 1

        if is_continue_mode and (not is_found_new):
            logging.info("Leaving as it seems there are no more new items...")
            break

        if not local_lib.selenium_util.xpath_exists(driver, MORE_BUTTON_XPATH):
            logging.info("Detected end of list")
            break

        logging.info("Load next items")

        local_lib.selenium_util.click_xpath(driver, MORE_BUTTON_XPATH)

        time.sleep(5)

    return item_info_list


def fetch_bought_item_info_list(handle, is_continue_mode):
    driver, wait = mercari.handle.get_selenium_driver(handle)

    mercari.handle.set_status(handle, "購入履歴の件数を確認しています...")

    for i in range(FETCH_RETRY_COUNT):
        if i != 0:
            logging.info("Retry {url}".format(url=driver.current_url))
            time.sleep(5)

        try:
            return fetch_bought_item_info_list_impl(handle, is_continue_mode)
        except Exception as e:
            logging.warning(str(e))
            error_detail = traceback.format_exc()
            pass

    logging.error(error_detail)
    logging.error("Give up to fetch {url}".format(url=driver.current_url))

    return []


def fetch_bought_item_list(handle, is_continue_mode=True):
    driver, wait = mercari.handle.get_selenium_driver(handle)

    mercari.handle.set_status(handle, "購入履歴の収集を開始します...")

    item_info_list = fetch_bought_item_info_list(handle, is_continue_mode)

    mercari.handle.set_status(handle, "購入履歴の詳細情報を収集しています...")

    mercari.handle.set_progress_bar(handle, STATUS_BOUGHT_ITEM, len(item_info_list))

    for item_info in item_info_list:
        if not mercari.handle.get_bought_item_stat(handle, item_info):
            mercari.handle.record_bought_item(handle, fetch_item_detail(handle, item_info))
            mercari.handle.get_progress_bar(handle, STATUS_BOUGHT_ITEM).update()
        else:
            logging.info(
                "{name} {price:,}円 [cached]".format(name=item_info["name"], price=item_info["price"])
            )

        mercari.handle.store_trading_info(handle)

    mercari.handle.get_progress_bar(handle, STATUS_BOUGHT_ITEM).update()

    mercari.handle.set_status(handle, "購入履歴の収集が完了しました．")


def execute_login(handle):
    driver, wait = mercari.handle.get_selenium_driver(handle)

    local_lib.selenium_util.click_xpath(driver, '//button[contains(text(), "はじめる")]')
    time.sleep(1)

    local_lib.selenium_util.click_xpath(
        driver,
        '//button[contains(text(), "ログイン")]',
        wait,
    )

    wait.until(EC.presence_of_element_located((By.XPATH, '//h1[contains(text(), "ログイン")]')))

    driver.find_element(By.XPATH, '//input[@name="emailOrPhone"]').send_keys(
        mercari.handle.get_login_user(handle)
    )
    driver.find_element(By.XPATH, '//input[@name="password"]').send_keys(
        mercari.handle.get_login_pass(handle)
    )

    local_lib.selenium_util.click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    time.sleep(2)
    if len(driver.find_elements(By.XPATH, '//div[@id="recaptchaV2"]')) != 0:
        logging.warning("画像認証が要求されました．")
        local_lib.captcha.resolve_mp3(driver, wait)
        logging.warning("画像認証を突破しました．")
        local_lib.selenium_util.click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    wait.until(EC.presence_of_element_located((By.XPATH, '//h1[contains(text(), "電話番号の確認")]')))

    logging.info("認証番号の対応を行います．")
    code = input("SMS で送られてきた認証番号を入力してください: ")

    driver.find_element(By.XPATH, '//input[@name="code"]').send_keys(code)
    local_lib.selenium_util.click_xpath(driver, '//button[contains(text(), "認証して完了する")]', wait)

    time.sleep(5)

    # NOTE: 稀に正しく表示されないことがあるので，リロードしておく
    driver.refresh()


def keep_logged_on(handle):
    driver, wait = mercari.handle.get_selenium_driver(handle)

    wait_for_loading(handle)

    if local_lib.selenium_util.xpath_exists(driver, '//div[contains(@class, "account-button-content")]'):
        return

    logging.info("Try to login")

    for i in range(LOGIN_RETRY_COUNT):
        if i != 0:
            logging.info("Retry to login")

        execute_login(handle)

        wait_for_loading(handle)

        if local_lib.selenium_util.xpath_exists(driver, '//div[contains(@class, "account-button-content")]'):
            return

        logging.warning("Failed to login")
        local_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), mercari.handle.get_debug_dir_path(handle)
        )

    logging.error("Give up to login")
    raise Exception("ログインに失敗しました．")


if __name__ == "__main__":
    from docopt import docopt

    import local_lib.logger
    import local_lib.config

    args = docopt(__doc__)

    local_lib.logger.init("test", level=logging.INFO)

    config = local_lib.config.load(args["-c"])
    handle = mercari.handle.create(config)

    driver, wait = mercari.handle.get_selenium_driver(handle)

    try:
        fetch_sold_item_list(handle, False)
        fetch_bought_item_list(handle)

    except:
        driver, wait = mercari.handle.get_selenium_driver(handle)
        logging.error(traceback.format_exc())

        local_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), mercari.handle.get_debug_dir_path(handle)
        )
