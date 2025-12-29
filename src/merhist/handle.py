#!/usr/bin/env python3
from __future__ import annotations

import datetime
import logging
import pathlib
import time
import zoneinfo
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import my_lib.selenium_util
import my_lib.serializer
import rich.console
import rich.live
import rich.panel
import rich.progress
import rich.table
import rich.text
import selenium.webdriver.remote.webdriver
import selenium.webdriver.support.wait

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support.wait import WebDriverWait

import merhist.config
import merhist.item

# ステータスバーの色定義
STATUS_STYLE_NORMAL = "bold #FFFFFF on #E72121"  # メルカリレッド
STATUS_STYLE_ERROR = "bold white on red"


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


class _DisplayRenderable:
    """Live 表示用の動的 renderable クラス"""

    def __init__(self, handle: Handle) -> None:
        self._handle = handle

    def __rich__(self) -> Any:
        """Rich が描画時に呼び出すメソッド"""
        return self._handle._create_display()


class ProgressTask:
    """Rich Progress のタスクを管理するクラス"""

    def __init__(self, handle: Handle, task_id: rich.progress.TaskID, total: int) -> None:
        self._handle = handle
        self._task_id = task_id
        self._total = total
        self._count = 0

    @property
    def total(self) -> int:
        return self._total

    @property
    def count(self) -> int:
        return self._count

    def update(self, advance: int = 1) -> None:
        """プログレスを進める"""
        self._count += advance
        if self._handle._progress is not None:
            self._handle._progress.update(self._task_id, advance=advance)
            self._handle._refresh_display()


@dataclass
class Handle:
    config: merhist.config.Config
    trading: TradingInfo = field(default_factory=TradingInfo)
    selenium: SeleniumInfo | None = None

    # Rich 関連
    _console: rich.console.Console = field(default_factory=rich.console.Console)
    _progress: rich.progress.Progress | None = field(default=None, repr=False)
    _live: rich.live.Live | None = field(default=None, repr=False)
    _start_time: float = field(default_factory=time.time)
    _status_text: str = ""
    _status_is_error: bool = False
    _display_renderable: _DisplayRenderable | None = field(default=None, repr=False)

    # プログレスタスク管理
    progress_bar: dict[str, ProgressTask] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._load_trading_info()
        self._prepare_directory()
        self._init_progress()

    def _init_progress(self) -> None:
        """Progress と Live を初期化"""
        # 非TTY環境では Live を使用しない
        if not self._console.is_terminal:
            return

        self._progress = rich.progress.Progress(
            rich.progress.TextColumn("[bold]{task.description:<31}"),
            rich.progress.BarColumn(bar_width=None),
            rich.progress.TaskProgressColumn(),
            rich.progress.TextColumn("{task.completed:>5} / {task.total:<5}"),
            rich.progress.TimeElapsedColumn(),
            console=self._console,
            expand=True,
        )
        self._start_time = time.time()
        self._display_renderable = _DisplayRenderable(self)
        self._live = rich.live.Live(
            self._display_renderable,
            console=self._console,
            refresh_per_second=4,
        )
        self._live.start()

    def _create_status_bar(self) -> rich.table.Table:
        """ステータスバーを作成（左: タイトル、中央: 進捗、右: 時間）"""
        style = STATUS_STYLE_ERROR if self._status_is_error else STATUS_STYLE_NORMAL
        elapsed = time.time() - self._start_time
        elapsed_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"

        table = rich.table.Table(
            show_header=False,
            show_edge=False,
            box=None,
            padding=0,
            expand=True,
            style=style,
        )
        table.add_column("title", justify="left", ratio=1, no_wrap=True, style=style)
        table.add_column("status", justify="center", ratio=3, no_wrap=True, style=style)
        table.add_column("time", justify="right", ratio=1, no_wrap=True, style=style)

        table.add_row(
            rich.text.Text(" メルカリ ", style=style),
            rich.text.Text(self._status_text, style=style),
            rich.text.Text(f" {elapsed_str} ", style=style),
        )

        return table

    def _create_display(self) -> Any:
        """表示内容を作成"""
        status_bar = self._create_status_bar()
        if self._progress is not None and len(self._progress.tasks) > 0:
            return rich.console.Group(status_bar, self._progress)
        return status_bar

    def _refresh_display(self) -> None:
        """表示を強制的に再描画"""
        if self._live is not None:
            self._live.refresh()

    # --- Selenium 関連 ---
    def get_selenium_driver(
        self,
    ) -> tuple["WebDriver", "WebDriverWait"]:
        if self.selenium is not None:
            return (self.selenium.driver, self.selenium.wait)

        try:
            driver = my_lib.selenium_util.create_driver(
                "Merhist", self.config.selenium_data_dir_path, clean_profile=True
            )
            wait = selenium.webdriver.support.wait.WebDriverWait(driver, 5)

            my_lib.selenium_util.clear_cache(driver)

            self.selenium = SeleniumInfo(driver=driver, wait=wait)

            return (driver, wait)
        except Exception as e:
            raise my_lib.selenium_util.SeleniumError(f"Selenium の起動に失敗しました: {e}") from e

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
        """プログレスバーを作成"""
        if self._progress is None:
            return

        task_id = self._progress.add_task(desc, total=total)
        self.progress_bar[desc] = ProgressTask(self, task_id, total)
        self._refresh_display()

    def set_status(self, status: str, is_error: bool = False) -> None:
        """ステータスを更新"""
        self._status_text = status
        self._status_is_error = is_error

        # 非TTY環境では logging で出力
        if not self._console.is_terminal:
            if is_error:
                logging.error(status)
            else:
                logging.info(status)
            return

        self._refresh_display()

    # --- 終了処理 ---
    def quit_selenium(self) -> None:
        if self.selenium is not None:
            self.set_status("🛑 クローラを終了しています...")
            my_lib.selenium_util.quit_driver_gracefully(self.selenium.driver, wait_sec=5)
            self.selenium = None

    def finish(self) -> None:
        self.quit_selenium()
        if self._live is not None:
            self._live.stop()
            self._live = None

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
