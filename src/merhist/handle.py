#!/usr/bin/env python3
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import my_lib.browser_manager
import my_lib.cui_progress
import my_lib.time

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
class Handle:
    config: merhist.config.Config
    clear_profile_on_browser_error: bool = False
    debug_mode: bool = False
    ignore_cache: bool = False
    trading: TradingState = field(default_factory=TradingState)
    _db: merhist.database.Database | None = field(default=None, repr=False)
    _browser_manager: my_lib.browser_manager.BrowserManager | None = field(
        default=None, init=False, repr=False
    )

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
        self._browser_manager = my_lib.browser_manager.BrowserManager(
            profile_name=merhist.const.SELENIUM_PROFILE_NAME,
            data_dir=self.config.selenium_data_dir_path,
            clear_profile_on_error=self.clear_profile_on_browser_error,
        )

    def _init_database(self) -> None:
        """データベースを初期化"""
        db_path = self.config.cache_file_path

        # キャッシュ無視モードでは、収集済みキャッシュを保護するため専用の DB を使う
        if self.ignore_cache:
            db_path = db_path.with_name(db_path.stem + "_debug" + db_path.suffix)
            logging.info("キャッシュを無視します（デバッグ用 DB を使用: %s）", db_path)
            if db_path.exists():
                db_path.unlink()

        self._db = merhist.database.open_database(
            db_path,
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
    def get_selenium_driver(self) -> tuple[WebDriver, WebDriverWait]:
        """Selenium ドライバーを取得（必要に応じて起動）"""
        if self._browser_manager is None:
            raise RuntimeError("BrowserManager is not initialized")
        return self._browser_manager.get_driver()

    # --- 販売アイテム関連 ---
    def record_sold_item(self, item: merhist.item.SoldItem) -> None:
        # NOTE: 強制再収集時に最新データで上書きできるよう、存在チェックせず upsert する
        self.db.upsert_sold_item(item)

    def get_sold_item_stat(self, item: merhist.item.SoldItem) -> bool:
        return self.db.exists_sold_item(item.id)

    def get_sold_item_list(self) -> list[merhist.item.SoldItem]:
        return self.db.get_sold_item_list()

    def get_sold_checked_count(self) -> int:
        return self.db.get_sold_count()

    # --- 購入アイテム関連 ---
    def record_bought_item(self, item: merhist.item.BoughtItem) -> None:
        # NOTE: 強制再収集時に最新データで上書きできるよう、存在チェックせず upsert する
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
        """Selenium ドライバーを終了"""
        if self._browser_manager is not None and self._browser_manager.has_driver():
            self.set_status("🛑 クローラを終了しています...")
            self._browser_manager.quit()

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
            my_lib.time.now().isoformat(),
        )

    def _prepare_directory(self) -> None:
        self.config.selenium_data_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.debug_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.thumb_dir_path.mkdir(parents=True, exist_ok=True)
        self.config.cache_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.captcha_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.excel_file_path.parent.mkdir(parents=True, exist_ok=True)
