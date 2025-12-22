#!/usr/bin/env python3
"""設定クラス"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any, Self

import my_lib.notify.slack
import my_lib.store.mercari.config
import openpyxl.styles


@dataclass(frozen=True)
class MercariCacheConfig:
    """メルカリキャッシュ設定"""

    order: str
    thumb: str

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からパース"""
        return cls(
            order=data["order"],
            thumb=data["thumb"],
        )


@dataclass(frozen=True)
class MercariDataConfig:
    """メルカリデータ設定"""

    cache: MercariCacheConfig

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からパース"""
        return cls(
            cache=MercariCacheConfig.parse(data["cache"]),
        )


@dataclass(frozen=True)
class DataConfig:
    """データ設定"""

    selenium: str
    debug: str
    mercari: MercariDataConfig

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からパース"""
        return cls(
            selenium=data["selenium"],
            debug=data["debug"],
            mercari=MercariDataConfig.parse(data["mercari"]),
        )


@dataclass(frozen=True)
class ExcelFontConfig:
    """Excelフォント設定"""

    name: str
    size: int

    def to_openpyxl_font(self) -> openpyxl.styles.Font:
        """openpyxl.styles.Font に変換"""
        return openpyxl.styles.Font(name=self.name, size=self.size)

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からパース"""
        return cls(
            name=data["name"],
            size=data["size"],
        )


@dataclass(frozen=True)
class ExcelConfig:
    """Excel設定"""

    font: ExcelFontConfig
    table: str

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からパース"""
        return cls(
            font=ExcelFontConfig.parse(data["font"]),
            table=data["table"],
        )


@dataclass(frozen=True)
class OutputConfig:
    """出力設定"""

    captcha: str
    excel: ExcelConfig

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からパース"""
        return cls(
            captcha=data["captcha"],
            excel=ExcelConfig.parse(data["excel"]),
        )


@dataclass(frozen=True)
class LoginConfig:
    """ログイン設定"""

    line: my_lib.store.mercari.config.LineLoginConfig
    mercari: my_lib.store.mercari.config.MercariLoginConfig

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からパース"""
        return cls(
            line=my_lib.store.mercari.config.parse_line_login(data["line"]),
            mercari=my_lib.store.mercari.config.parse_mercari_login(data["mercari"]),
        )


@dataclass(frozen=True)
class Config:
    """アプリケーション設定"""

    base_dir: pathlib.Path
    login: LoginConfig
    data: DataConfig
    output: OutputConfig
    slack: my_lib.notify.slack.SlackConfig | None = None

    # --- パス関連プロパティ ---
    @property
    def cache_file_path(self) -> pathlib.Path:
        return self.base_dir / self.data.mercari.cache.order

    @property
    def excel_file_path(self) -> pathlib.Path:
        return self.base_dir / self.output.excel.table

    @property
    def thumb_dir_path(self) -> pathlib.Path:
        return self.base_dir / self.data.mercari.cache.thumb

    @property
    def selenium_data_dir_path(self) -> pathlib.Path:
        return self.base_dir / self.data.selenium

    @property
    def debug_dir_path(self) -> pathlib.Path:
        return self.base_dir / self.data.debug

    @property
    def captcha_file_path(self) -> pathlib.Path:
        return self.base_dir / self.output.captcha

    @property
    def excel_font(self) -> openpyxl.styles.Font:
        return self.output.excel.font.to_openpyxl_font()

    @classmethod
    def load(cls, data: dict[str, Any]) -> Self:
        """辞書から Config を生成する"""
        slack = None
        if "slack" in data:
            slack = my_lib.notify.slack.parse_config(data["slack"])

        return cls(
            base_dir=pathlib.Path(data["base_dir"]),
            login=LoginConfig.parse(data["login"]),
            data=DataConfig.parse(data["data"]),
            output=OutputConfig.parse(data["output"]),
            slack=slack,
        )
