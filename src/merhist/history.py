#!/usr/bin/env python3
"""
メルカリの販売履歴や購入履歴をエクセルファイルに書き出します。

Usage:
  history.py [-c CONFIG] [-o EXCEL] [-N]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -o EXCEL          : 生成する Excel ファイルを指定します。 [default: merhist.xlsx]
  -N                : サムネイル画像を含めないようにします。
"""

from __future__ import annotations

import datetime
import logging
import pathlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import merhist.item

import my_lib.openpyxl_util
import openpyxl
import openpyxl.drawing.image
import openpyxl.drawing.spreadsheet_drawing
import openpyxl.drawing.xdr
import openpyxl.styles
import openpyxl.utils

import merhist.crawler
import merhist.handle

_STATUS_INSERT_SOLD_ITEM: str = "[生成] 販売商品"
_STATUS_INSERT_BOUGHT_ITEM: str = "[生成] 購入商品"
_STATUS_ALL: str = "[生成] Excel"


_SHOP_NAME: str = "メルカリ"


@dataclass
class _TransactionConfig:
    """Excel出力用のトランザクション設定"""

    mode: Literal["BOUGHT", "SOLD"]
    item_list: Sequence[merhist.item.ItemBase]
    status: str


_SHEET_DEF = {
    "BOUGHT": {
        "SHEET_TITLE": f"【{_SHOP_NAME}】購入",
        "TABLE_HEADER": {
            "row": {"pos": 2, "height": {"default": 80, "without_thumb": 25}},
            "col": {
                "shop_name": {
                    "label": "ショップ",
                    "pos": 2,
                    "width": 15,
                    "format": "@",
                    "value": _SHOP_NAME,
                },
                "date": {
                    # NOTE: メルカリ向けでは，他のショップで「date」としている内容を
                    # 「purchase_date」としているので，読み替える
                    "formal_key": "purchase_date",
                    "label": "購入日",
                    "pos": 3,
                    "width": 23,
                    "format": 'yyyy"年"mm"月"dd"日 ("aaa")"',
                },
                "name": {"label": "商品名", "pos": 4, "width": 70, "wrap": True, "format": "@"},
                "image": {"label": "画像", "pos": 5, "width": 12},
                "count": {
                    "label": "数量",
                    "pos": 6,
                    "format": "0_ ",
                    "width": 8,
                },
                "price": {
                    "label": "価格",
                    "pos": 7,
                    "width": 16,
                    "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
                    "optional": True,
                },
                "condition": {"label": "コンディション", "pos": 8, "width": 13, "format": "@", "wrap": True},
                "postage_charge": {"label": "送料負担", "pos": 9, "width": 10, "format": "@", "wrap": True},
                "category": {"label": "カテゴリ", "pos": 10, "length": 3, "width": 16, "wrap": True},
                "shop": {"label": "ショップ", "pos": 13, "width": 13, "format": "@"},
                "shipping_method": {"label": "配送方法", "pos": 14, "width": 10, "format": "@", "wrap": True},
                "seller_region": {"label": "発送元の地域", "pos": 15, "width": 16, "format": "@"},
                "id": {
                    "label": "商品ID",
                    "pos": 16,
                    "width": 19,
                    "format": "@",
                    "link_func": lambda item: item["url"],
                },
                "no": {
                    # NOTE: メルカリ向けでは，他のショップで「id」としている内容が独立して存在しないため，
                    # 読み替える
                    "formal_key": "id",
                    "label": "注文番号",
                    "pos": 17,
                    "width": 19,
                    "format": "@",
                    "link_func": lambda item: item["order_url"],
                },
                "error": {
                    "label": "エラー",
                    "pos": 18,
                    "width": 15,
                    "format": "@",
                    "wrap": True,
                    "optional": True,
                },
            },
        },
    },
    "SOLD": {
        "SHEET_TITLE": f"【{_SHOP_NAME}】販売",
        "TABLE_HEADER": {
            "row": {"pos": 2, "height": {"default": 80, "without_thumb": 25}},
            "col": {
                "shop_name": {
                    "label": "ショップ",
                    "pos": 2,
                    "width": 15,
                    "format": "@",
                    "value": _SHOP_NAME,
                },
                "date": {
                    # NOTE: メルカリ向けでは，他のショップで「date」としている内容を「purchase_date」
                    # としているので，読み替える
                    "formal_key": "purchase_date",
                    "label": "販売日",
                    "pos": 3,
                    "width": 23,
                    "format": 'yyyy"年"mm"月"dd"日 ("aaa")"',
                },
                "name": {"label": "商品名", "pos": 4, "width": 70, "wrap": True, "format": "@"},
                "image": {"label": "画像", "pos": 5, "width": 12},
                "count": {
                    "label": "数量",
                    "pos": 6,
                    "format": "0_ ",
                    "width": 8,
                },
                "price": {
                    "label": "価格",
                    "pos": 7,
                    "width": 16,
                    "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
                },
                "commission": {
                    "label": "手数料",
                    "pos": 8,
                    "width": 10,
                    "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
                },
                "postage": {
                    "label": "送料",
                    "pos": 9,
                    "width": 10,
                    "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
                },
                "profit": {
                    "label": "回収金額",
                    "pos": 10,
                    "width": 16,
                    "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
                },
                "condition": {"label": "コンディション", "pos": 11, "width": 13, "format": "@", "wrap": True},
                "postage_charge": {"label": "送料負担", "pos": 12, "width": 10, "format": "@", "wrap": True},
                "shipping_method": {"label": "配送方法", "pos": 13, "width": 10, "format": "@", "wrap": True},
                "commission_rate": {
                    "label": "手数料率",
                    "pos": 14,
                    "width": 10,
                    "format": "0%",
                    "conv_func": lambda x: x / 100,
                },
                "category": {"label": "カテゴリ", "pos": 15, "length": 3, "width": 16, "wrap": True},
                "completion_date": {
                    "label": "取引完了日",
                    "pos": 18,
                    "width": 23,
                    "format": 'yyyy"年"mm"月"dd"日 ("aaa")"',
                },
                "seller_region": {"label": "発送元の地域", "pos": 19, "width": 16, "format": "@"},
                "id": {
                    "label": "商品ID",
                    "pos": 20,
                    "width": 19,
                    "format": "@",
                    "link_func": lambda item: item["url"],
                },
                "no": {
                    # NOTE: メルカリ向けでは，他のショップで「id」としている内容が独立して存在しないため，
                    # 読み替える
                    "formal_key": "id",
                    "label": "注文番号",
                    "pos": 21,
                    "width": 19,
                    "format": "@",
                    "link_func": lambda item: merhist.crawler.gen_item_transaction_url(item),
                },
                "error": {
                    "label": "エラー",
                    "pos": 22,
                    "width": 15,
                    "format": "@",
                    "wrap": True,
                    "optional": True,
                },
            },
        },
    },
}


def _warning_handler(item: my_lib.openpyxl_util.RowData, message: str) -> None:
    """警告メッセージを「⚠️ YY年MM月DD日 商品名: 警告メッセージ」の形式で出力する。"""
    name = item["name"] if "name" in item else "不明"  # noqa: SIM401
    date_str = ""
    if "purchase_date" in item and item["purchase_date"] is not None:
        date_val = item["purchase_date"]
        if isinstance(date_val, datetime.datetime):
            date_str = date_val.strftime("%y年%m月%d日 ")
    logging.warning("⚠️ %s%s: %s", date_str, name, message)


def _generate_sheet(
    handle: merhist.handle.Handle,
    book: openpyxl.Workbook,
    is_need_thumb: bool = True,
) -> None:
    transaction_list = [
        _TransactionConfig(
            mode="BOUGHT", item_list=handle.get_bought_item_list(), status=_STATUS_INSERT_BOUGHT_ITEM
        ),
        _TransactionConfig(
            mode="SOLD", item_list=handle.get_sold_item_list(), status=_STATUS_INSERT_SOLD_ITEM
        ),
    ]

    for transaction_info in transaction_list:
        handle.set_progress_bar(transaction_info.status, len(transaction_info.item_list))

        my_lib.openpyxl_util.generate_list_sheet(
            book,
            transaction_info.item_list,  # type: ignore[arg-type]
            _SHEET_DEF[transaction_info.mode],
            is_need_thumb,
            lambda item: handle.get_thumb_path(item),  # pyright: ignore[reportArgumentType]
            lambda status: handle.set_status(status),
            lambda: handle.update_progress_bar(_STATUS_ALL),
            lambda status=transaction_info.status: handle.update_progress_bar(status),
            warning_handler=_warning_handler,
        )


def generate_table_excel(
    handle: merhist.handle.Handle,
    excel_file: pathlib.Path,
    is_need_thumb: bool = True,
) -> None:
    handle.set_status("📊 エクセルファイルの作成を開始します...")
    # 直接呼び出し 3 回 + generate_list_sheet 内での呼び出し 3 回 × 2 シート
    handle.set_progress_bar(_STATUS_ALL, 3 + 3 * 2)

    logging.info("Start to Generate excel file")

    book = openpyxl.Workbook()
    book._named_styles["Normal"].font = handle.config.excel_font  # pyright: ignore[reportAttributeAccessIssue]

    handle.update_progress_bar(_STATUS_ALL)

    handle.normalize()

    _generate_sheet(handle, book, is_need_thumb)

    book.remove(book.worksheets[0])

    handle.set_status("💾 エクセルファイルを書き出しています...")

    book.save(excel_file)

    handle.update_progress_bar(_STATUS_ALL)

    book.close()

    handle.update_progress_bar(_STATUS_ALL)

    handle.set_status("🎉 完了しました！")

    logging.info("Complete to Generate excel file")


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    import merhist.config

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config_file: str = args["-c"]
    excel_file: pathlib.Path = pathlib.Path(args["-o"])
    need_thumb: bool = not args["-N"]

    config = merhist.config.Config.load(my_lib.config.load(config_file))

    handle = merhist.handle.Handle(config)

    generate_table_excel(handle, excel_file, need_thumb)

    handle.finish()
