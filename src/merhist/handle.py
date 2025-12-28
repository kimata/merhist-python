#!/usr/bin/env python3
from __future__ import annotations

import datetime
import pathlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
import zoneinfo

import enlighten
import my_lib.selenium_util
import my_lib.serializer
import selenium.webdriver.support.wait

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support.wait import WebDriverWait

import merhist.config
import merhist.item


@dataclass
class TradingInfo:
    sold_item_list: list[merhist.item.SoldItem] = field(default_factory=list)
    sold_item_id_stat: dict[str, bool] = field(default_factory=dict)
    sold_total_count: int = 0
    sold_checked_count: int = 0
    bought_item_list: list[merhist.item.BoughtItem] = field(default_factory=list)
    bought_item_id_stat: dict[str, bool] = field(default_factory=dict)
    bought_total_count: int = 0
    bought_checked_count: int = 0
    last_modified: datetime.datetime = field(
        default_factory=lambda: datetime.datetime(1994, 7, 5, tzinfo=zoneinfo.ZoneInfo("Asia/Tokyo"))
    )


@dataclass
class SeleniumInfo:
    driver: selenium.webdriver.remote.webdriver.WebDriver
    wait: selenium.webdriver.support.wait.WebDriverWait


@dataclass
class Handle:
    config: merhist.config.Config
    progress_manager: enlighten.Manager = field(default_factory=enlighten.get_manager)
    progress_bar: dict[str, enlighten.Counter] = field(default_factory=dict)
    trading: TradingInfo = field(default_factory=TradingInfo)
    selenium: SeleniumInfo | None = None
    status: enlighten.StatusBar | None = None

    def __post_init__(self) -> None:
        self._load_trading_info()
        self._prepare_directory()

    # --- Selenium 関連 ---
    def get_selenium_driver(
        self,
    ) -> tuple[WebDriver, WebDriverWait]:
        if self.selenium is not None:
            return (self.selenium.driver, self.selenium.wait)

        driver = my_lib.selenium_util.create_driver(
            "Merhist", self.config.selenium_data_dir_path, clean_profile=True
        )
        wait = selenium.webdriver.support.wait.WebDriverWait(driver, 5)

        my_lib.selenium_util.clear_cache(driver)

        self.selenium = SeleniumInfo(driver=driver, wait=wait)

        return (driver, wait)

    # --- 販売アイテム関連 ---
    def record_sold_item(self, item: merhist.item.SoldItem) -> None:
        if self.get_sold_item_stat(item):
            return
        self.trading.sold_item_list.append(item)
        self.trading.sold_item_id_stat[item.id] = True
        self.trading.sold_checked_count += 1

    def get_sold_item_stat(self, item: merhist.item.SoldItem) -> bool:
        return item.id in self.trading.sold_item_id_stat

    def get_sold_item_list(self) -> list[merhist.item.SoldItem]:
        return sorted(self.trading.sold_item_list, key=lambda x: x.completion_date or datetime.datetime.min)

    # --- 購入アイテム関連 ---
    def record_bought_item(self, item: merhist.item.BoughtItem) -> None:
        if self.get_bought_item_stat(item):
            return
        self.trading.bought_item_list.append(item)
        self.trading.bought_item_id_stat[item.id] = True
        self.trading.bought_checked_count += 1

    def get_bought_item_stat(self, item: merhist.item.BoughtItem) -> bool:
        return item.id in self.trading.bought_item_id_stat

    def get_bought_item_list(self) -> list[merhist.item.BoughtItem]:
        return sorted(self.trading.bought_item_list, key=lambda x: x.purchase_date or datetime.datetime.min)

    # --- 正規化 ---
    def normalize(self) -> None:
        self.trading.bought_item_list = list(
            {item.id: item for item in self.trading.bought_item_list}.values()
        )
        self.trading.bought_checked_count = len(self.trading.bought_item_list)

        self.trading.sold_item_list = list(
            {item.id: item for item in self.trading.sold_item_list}.values()
        )
        self.trading.sold_checked_count = len(self.trading.sold_item_list)

    # --- サムネイル ---
    def get_thumb_path(self, item: merhist.item.ItemBase) -> pathlib.Path:
        return self.config.thumb_dir_path / (item.id + ".png")

    # --- プログレスバー ---
    def set_progress_bar(self, desc: str, total: int) -> None:
        BAR_FORMAT = (
            "{desc:31s}{desc_pad}{percentage:3.0f}% |{bar}| {count:5d} / {total:5d} "
            "[{elapsed}<{eta}, {rate:6.2f}{unit_pad}{unit}/s]"
        )
        COUNTER_FORMAT = (
            "{desc:30s}{desc_pad}{count:5d} {unit}{unit_pad}[{elapsed}, {rate:6.2f}{unit_pad}{unit}/s]{fill}"
        )
        self.progress_bar[desc] = self.progress_manager.counter(
            total=total, desc=desc, bar_format=BAR_FORMAT, counter_format=COUNTER_FORMAT
        )

    def set_status(self, status: str, is_error: bool = False) -> None:
        color = "bold_bright_white_on_red" if is_error else "bold_bright_white_on_lightslategray"

        if self.status is None:
            self.status = self.progress_manager.status_bar(
                status_format="メルカリ{fill}{status}{fill}{elapsed}",
                color=color,
                justify=enlighten.Justify.CENTER,
                status=status,
            )
        else:
            self.status.color = color
            self.status.update(status=status, force=True)

    # --- 終了処理 ---
    def quit_selenium(self) -> None:
        if self.selenium is not None:
            self.set_status("クローラを終了しています...")
            my_lib.selenium_util.quit_driver_gracefully(self.selenium.driver, wait_sec=5)
            self.selenium = None

    def finish(self) -> None:
        self.quit_selenium()
        self.progress_manager.stop()

    # --- シリアライズ ---
    def store_trading_info(self) -> None:
        self.trading.last_modified = datetime.datetime.now(tz=zoneinfo.ZoneInfo("Asia/Tokyo"))
        my_lib.serializer.store(self.config.cache_file_path, self.trading)

    def _load_trading_info(self) -> None:
        self.trading = my_lib.serializer.load(self.config.cache_file_path, TradingInfo())

    def _prepare_directory(self) -> None:
        self.config.selenium_data_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.debug_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.thumb_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.cache_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.captcha_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.excel_file_path.parent.mkdir(parents=True, exist_ok=True)
