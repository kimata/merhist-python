#!/usr/bin/env python3
from __future__ import annotations

import datetime
import logging
import os
import pathlib
import time
import zoneinfo
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

import my_lib.chrome_util
import my_lib.selenium_util
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
import merhist.const
import merhist.database
import merhist.item

# SQLite スキーマファイルのパス（プロジェクトルートからの相対パス）
_SQLITE_SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"

# ステータスバーの色定義
_STATUS_STYLE_NORMAL = "bold #FFFFFF on #E72121"  # メルカリレッド
_STATUS_STYLE_ERROR = "bold white on red"


@dataclass
class TradingState:
    """取引状態（メモリ上で管理するカウンタ）"""

    sold_total_count: int = 0
    bought_total_count: int = 0


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


class _NullProgress:
    """非TTY環境用の何もしない Progress（Null Object パターン）"""

    tasks: ClassVar[list[rich.progress.Task]] = []

    def add_task(self, description: str, total: float | None = None) -> rich.progress.TaskID:
        return rich.progress.TaskID(0)

    def update(self, task_id: rich.progress.TaskID, advance: float = 1) -> None:
        pass

    def __rich__(self) -> rich.text.Text:
        """Rich プロトコル対応（空のテキストを返す）"""
        return rich.text.Text("")


class _NullLive:
    """非TTY環境用の何もしない Live（Null Object パターン）"""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def refresh(self) -> None:
        pass


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
        self._handle._progress.update(self._task_id, advance=advance)
        self._handle._refresh_display()


@dataclass
class Handle:
    config: merhist.config.Config
    clear_profile_on_browser_error: bool = False
    debug_mode: bool = False
    ignore_cache: bool = False
    trading: TradingState = field(default_factory=TradingState)
    selenium: SeleniumInfo | None = None
    _db: merhist.database.Database | None = field(default=None, repr=False)

    # Rich 関連
    _console: rich.console.Console = field(default_factory=rich.console.Console)
    _progress: rich.progress.Progress | _NullProgress = field(default_factory=_NullProgress, repr=False)
    _live: rich.live.Live | _NullLive = field(default_factory=_NullLive, repr=False)
    _start_time: float = field(default_factory=time.time)
    _status_text: str = ""
    _status_is_error: bool = False
    _display_renderable: _DisplayRenderable | None = field(default=None, repr=False)

    # プログレスタスク管理
    progress_bar: dict[str, ProgressTask] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._prepare_directory()
        self._init_database()
        self._init_progress()

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
            rich.progress.TextColumn("経過:"),
            rich.progress.TimeElapsedColumn(),
            rich.progress.TextColumn("残り:"),
            rich.progress.TimeRemainingColumn(),
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
        style = _STATUS_STYLE_ERROR if self._status_is_error else _STATUS_STYLE_NORMAL
        elapsed = time.time() - self._start_time
        elapsed_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"

        # ターミナル幅を取得し、明示的に幅を制限
        # NOTE: tmux 環境では幅計算が実際と異なることがあるため、余裕を持たせる
        terminal_width = self._console.width
        if os.environ.get("TMUX"):
            terminal_width -= 2

        table = rich.table.Table(
            show_header=False,
            show_edge=False,
            box=None,
            padding=0,
            expand=False,  # expand=False にして幅を明示的に制御
            width=terminal_width,  # ターミナル幅に制限
            style=style,
        )
        table.add_column("title", justify="left", ratio=1, no_wrap=True, overflow="ellipsis", style=style)
        table.add_column("status", justify="center", ratio=3, no_wrap=True, overflow="ellipsis", style=style)
        table.add_column("time", justify="right", ratio=1, no_wrap=True, overflow="ellipsis", style=style)

        table.add_row(
            rich.text.Text(" 🛒メルカリ ", style=style),
            rich.text.Text(self._status_text, style=style),
            rich.text.Text(f" {elapsed_str} ", style=style),
        )

        return table

    def _create_display(self) -> Any:
        """表示内容を作成"""
        status_bar = self._create_status_bar()
        # NullProgress の場合 tasks は常に空なのでこの条件で十分
        if len(self._progress.tasks) > 0:
            return rich.console.Group(status_bar, self._progress)
        return status_bar

    def _refresh_display(self) -> None:
        """表示を強制的に再描画"""
        self._live.refresh()

    def pause_live(self) -> None:
        """Live 表示を一時停止（input() の前に呼び出す）"""
        self._live.stop()

    def resume_live(self) -> None:
        """Live 表示を再開（input() の後に呼び出す）"""
        self._live.start()

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
        task_id = self._progress.add_task(desc, total=total)
        self.progress_bar[desc] = ProgressTask(self, task_id, total)
        self._refresh_display()

    def update_progress_bar(self, desc: str, advance: int = 1) -> None:
        """プログレスバーを進める（存在しない場合は何もしない）"""
        if desc in self.progress_bar:
            self.progress_bar[desc].update(advance)

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
        self._live.stop()
        self._live = _NullLive()
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
