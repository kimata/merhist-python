#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib
import enlighten
import datetime
import functools

from selenium.webdriver.support.wait import WebDriverWait
import openpyxl.styles

import local_lib.serializer
import local_lib.selenium_util


def create(config):
    handle = {
        "progress_manager": enlighten.get_manager(),
        "progress_bar": {},
        "config": config,
    }

    load_trading_info(handle)

    prepare_directory(handle)

    return handle


def get_login_user(handle):
    return handle["config"]["login"]["user"]


def get_login_pass(handle):
    return handle["config"]["login"]["pass"]


def prepare_directory(handle):
    get_selenium_data_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_debug_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_thumb_dir_path(handle).mkdir(parents=True, exist_ok=True)
    get_caceh_file_path(handle).parent.mkdir(parents=True, exist_ok=True)
    get_excel_file_path(handle).parent.mkdir(parents=True, exist_ok=True)


def get_excel_font(handle):
    font_config = handle["config"]["output"]["excel"]["font"]
    return openpyxl.styles.Font(name=font_config["name"], size=font_config["size"])


def get_caceh_file_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["cache"]["order"])


def get_excel_file_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["output"]["excel"]["table"])


def get_thumb_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["cache"]["thumb"])


def get_selenium_data_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["selenium"])


def get_debug_dir_path(handle):
    return pathlib.Path(handle["config"]["base_dir"], handle["config"]["data"]["debug"])


def get_selenium_driver(handle):
    if "selenium" in handle:
        return (handle["selenium"]["driver"], handle["selenium"]["wait"])
    else:
        driver = local_lib.selenium_util.create_driver("Merhist", get_selenium_data_dir_path(handle))
        wait = WebDriverWait(driver, 5)

        local_lib.selenium_util.clear_cache(driver)

        handle["selenium"] = {
            "driver": driver,
            "wait": wait,
        }

        return (driver, wait)


def record_sold_item(handle, item):
    if get_sold_item_stat(handle, item):
        return

    handle["trading"]["sold_item_list"].append(item)
    handle["trading"]["sold_item_id_stat"][item["id"]] = True
    handle["trading"]["sold_checked_count"] += 1


def get_sold_item_stat(handle, item):
    return item["id"] in handle["trading"]["sold_item_id_stat"]


def set_sold_total_count(handle, sold_count):
    handle["trading"]["sold_total_count"] = sold_count


def get_sold_total_count(handle):
    return handle["trading"]["sold_total_count"]


def set_sold_checked_count(handle, sold_count):
    handle["trading"]["sold_checked_count"] = sold_count


def get_sold_checked_count(handle):
    return handle["trading"]["sold_checked_count"]


def get_sold_item_list(handle):
    return sorted(handle["trading"]["sold_item_list"], key=lambda x: x["completion_date"])


def record_bought_item(handle, item):
    if get_bought_item_stat(handle, item):
        return

    handle["trading"]["bought_item_list"].append(item)
    handle["trading"]["bought_item_id_stat"][item["id"]] = True
    handle["trading"]["bought_checked_count"] += 1


def get_bought_item_stat(handle, item):
    return item["id"] in handle["trading"]["bought_item_id_stat"]


def set_bought_total_count(handle, bought_count):
    handle["trading"]["bought_total_count"] = bought_count


def get_bought_total_count(handle):
    return handle["trading"]["bought_total_count"]


def set_bought_checked_count(handle, bought_count):
    handle["trading"]["bought_checked_count"] = bought_count


def get_bought_checked_count(handle):
    return handle["trading"]["bought_checked_count"]


def get_bought_item_list(handle):
    return sorted(handle["trading"]["bought_item_list"], key=lambda x: x["purchase_date"])


def normalize(handle):
    handle["trading"]["bought_item_list"] = functools.reduce(
        lambda x, y: x + [y] if y["id"] not in map(lambda item: item["id"], x) else x,
        handle["trading"]["bought_item_list"],
        [],
    )
    handle["trading"]["bought_checked_count"] = len(handle["trading"]["bought_item_list"])

    handle["trading"]["sold_item_list"] = functools.reduce(
        lambda x, y: x + [y] if y["id"] not in map(lambda item: item["id"], x) else x,
        handle["trading"]["sold_item_list"],
        [],
    )
    handle["trading"]["sold_checked_count"] = len(handle["trading"]["sold_item_list"])


def get_thumb_path(handle, item):

    return get_thumb_dir_path(handle) / (item["id"] + ".png")


def get_cache_last_modified(handle):
    return handle["trading"]["last_modified"]


def set_progress_bar(handle, desc, total):
    BAR_FORMAT = (
        "{desc:31s}{desc_pad}{percentage:3.0f}% |{bar}| {count:5d} / {total:5d} "
        + "[{elapsed}<{eta}, {rate:6.2f}{unit_pad}{unit}/s]"
    )
    COUNTER_FORMAT = (
        "{desc:30s}{desc_pad}{count:5d} {unit}{unit_pad}[{elapsed}, {rate:6.2f}{unit_pad}{unit}/s]{fill}"
    )

    handle["progress_bar"][desc] = handle["progress_manager"].counter(
        total=total, desc=desc, bar_format=BAR_FORMAT, counter_format=COUNTER_FORMAT
    )


def set_status(handle, status):
    if "status" not in handle:
        handle["status"] = handle["progress_manager"].status_bar(
            status_format="Merhist{fill}{status}{fill}{elapsed}",
            color="bold_bright_white_on_lightslategray",
            justify=enlighten.Justify.CENTER,
            status=status,
        )
    else:
        handle["status"].update(status=status, force=True)


def finish(handle):
    if "selenium" in handle:
        handle["selenium"]["driver"].quit()
        handle.pop("selenium")

    handle["progress_manager"].stop()


def store_trading_info(handle):
    handle["trading"]["last_modified"] = datetime.datetime.now()

    local_lib.serializer.store(get_caceh_file_path(handle), handle["trading"])


def load_trading_info(handle):
    handle["trading"] = local_lib.serializer.load(
        get_caceh_file_path(handle),
        {
            "sold_item_list": [],
            "sold_item_id_stat": {},
            "sold_total_count": 0,
            "sold_checked_count": 0,
            "bought_item_list": [],
            "bought_item_id_stat": {},
            "bought_total_count": 0,
            "bought_checked_count": 0,
            "last_modified": datetime.datetime(1994, 7, 5),
        },
    )


def get_progress_bar(handle, desc):
    return handle["progress_bar"][desc]
