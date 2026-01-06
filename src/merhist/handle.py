#!/usr/bin/env python3
from __future__ import annotations

import datetime
import logging
import pathlib
import zoneinfo
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import my_lib.chrome_util
import my_lib.cui_progress
import my_lib.selenium_util
import selenium.webdriver.remote.webdriver
import selenium.webdriver.support.wait

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support.wait import WebDriverWait

import merhist.config
import merhist.const
import merhist.database
import merhist.item

# SQLite スキーマファイルのパス（プロジェクトルートからの相対パス）
_SQLITE_SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"


@dataclass
class TradingState:
    """取引状態（メモリ上で管理するカウンタ）"""

    sold_total_count: int = 0
    bought_total_count: int = 0


@dataclass
class SeleniumInfo:
    driver: selenium.webdriver.remote.webdriver.WebDriver
    wait: selenium.webdriver.support.wait.WebDriverWait


@dataclass
class Handle:
    config: merhist.config.Config
    clear_profile_on_browser_error: bool = False
    debug_mode: bool = False
    ignore_cache: bool = False
    trading: TradingState = field(default_factory=TradingState)
    selenium: SeleniumInfo | None = None
    _db: merhist.database.Database | None = field(default=None, repr=False)

    # プログレス管理
    _progress_manager: my_lib.cui_progress.ProgressManager = field(
        default_factory=lambda: my_lib.cui_progress.ProgressManager(
            color="#E72121",  # メルカリレッド
            title=" 🛒メルカリ ",
        ),
        repr=False,
    )

    def __post_init__(self) -> None:
        self._prepare_directory()
        self._init_database()

    def _init_database(self) -> None:
        """データベースを初期化"""
        # キャッシュ無視モードの場合、既存のデータベースを削除
        if self.ignore_cache and self.config.cache_file_path.exists():
            logging.info("キャッシュを無視します")
            self.config.cache_file_path.unlink()

        self._db = merhist.database.open_database(
            self.config.cache_file_path,
            _SQLITE_SCHEMA_PATH,
        )
        # メタデータからカウンタを復元
        self.trading.sold_total_count = self._db.get_metadata_int("sold_total_count", 0)
        self.trading.bought_total_count = self._db.get_metadata_int("bought_total_count", 0)

    @property
    def db(self) -> merhist.database.Database:
        """データベースインスタンスを取得"""
        if self._db is None:
            raise RuntimeError("Database is not initialized")
        return self._db

    def pause_live(self) -> None:
        """Live 表示を一時停止（input() の前に呼び出す）"""
        self._progress_manager.pause_live()

    def resume_live(self) -> None:
        """Live 表示を再開（input() の後に呼び出す）"""
        self._progress_manager.resume_live()

    # --- Selenium 関連 ---
    def get_selenium_driver(
        self,
    ) -> tuple[WebDriver, WebDriverWait]:
        if self.selenium is not None:
            return (self.selenium.driver, self.selenium.wait)

        try:
            driver = my_lib.selenium_util.create_driver(
                merhist.const.SELENIUM_PROFILE_NAME, self.config.selenium_data_dir_path, use_undetected=True
            )
            wait = selenium.webdriver.support.wait.WebDriverWait(driver, 5)

            my_lib.selenium_util.clear_cache(driver)

            self.selenium = SeleniumInfo(driver=driver, wait=wait)

            return (driver, wait)
        except Exception as e:
            if self.clear_profile_on_browser_error:
                my_lib.chrome_util.delete_profile(
                    merhist.const.SELENIUM_PROFILE_NAME, self.config.selenium_data_dir_path
                )
            raise my_lib.selenium_util.SeleniumError(f"Selenium の起動に失敗しました: {e}") from e

    # --- 販売アイテム関連 ---
    def record_sold_item(self, item: merhist.item.SoldItem) -> None:
        if self.get_sold_item_stat(item):
            return
        self.db.upsert_sold_item(item)

    def get_sold_item_stat(self, item: merhist.item.SoldItem) -> bool:
        return self.db.exists_sold_item(item.id)

    def get_sold_item_list(self) -> list[merhist.item.SoldItem]:
        return self.db.get_sold_item_list()

    def get_sold_checked_count(self) -> int:
        return self.db.get_sold_count()

    # --- 購入アイテム関連 ---
    def record_bought_item(self, item: merhist.item.BoughtItem) -> None:
        if self.get_bought_item_stat(item):
            return
        self.db.upsert_bought_item(item)

    def get_bought_item_stat(self, item: merhist.item.BoughtItem) -> bool:
        return self.db.exists_bought_item(item.id)

    def get_bought_item_list(self) -> list[merhist.item.BoughtItem]:
        return self.db.get_bought_item_list()

    def get_bought_checked_count(self) -> int:
        return self.db.get_bought_count()

    # --- 正規化 ---
    def normalize(self) -> None:
        # SQLite では PRIMARY KEY 制約により重複は発生しないため、何もしない
        pass

    # --- サムネイル ---
    def get_thumb_path(self, item: merhist.item.ItemBase) -> pathlib.Path:
        return self.config.thumb_dir_path / (item.id + ".png")

    # --- プログレスバー ---
    def set_progress_bar(self, desc: str, total: int) -> None:
        """プログレスバーを作成"""
        self._progress_manager.set_progress_bar(desc, total)

    def update_progress_bar(self, desc: str, advance: int = 1) -> None:
        """プログレスバーを進める（存在しない場合は何もしない）"""
        self._progress_manager.update_progress_bar(desc, advance)

    def has_progress_bar(self, desc: str) -> bool:
        """プログレスバーが存在するか確認"""
        return self._progress_manager.has_progress_bar(desc)

    def get_progress_bar(self, desc: str) -> my_lib.cui_progress.ProgressTask:
        """プログレスバーを取得"""
        return self._progress_manager.get_progress_bar(desc)

    def set_status(self, status: str, is_error: bool = False) -> None:
        """ステータスを更新"""
        self._progress_manager.set_status(status, is_error=is_error)

    # --- 終了処理 ---
    def quit_selenium(self) -> None:
        if self.selenium is not None:
            self.set_status("🛑 クローラを終了しています...")
            my_lib.selenium_util.quit_driver_gracefully(self.selenium.driver, wait_sec=5)
            self.selenium = None

    def finish(self) -> None:
        self.quit_selenium()
        self._progress_manager.stop()
        if self._db is not None:
            self._db.close()
            self._db = None

    # --- メタデータ保存 ---
    def store_trading_info(self) -> None:
        """メタデータを保存（アイテムは record_* で即座に保存されるため不要）"""
        self.db.set_metadata_int("sold_total_count", self.trading.sold_total_count)
        self.db.set_metadata_int("bought_total_count", self.trading.bought_total_count)
        self.db.set_metadata(
            "last_modified",
            datetime.datetime.now(tz=zoneinfo.ZoneInfo("Asia/Tokyo")).isoformat(),
        )

    def _prepare_directory(self) -> None:
        self.config.selenium_data_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.debug_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.thumb_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.cache_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.captcha_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.excel_file_path.parent.mkdir(parents=True, exist_ok=True)
