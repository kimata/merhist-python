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

import logging
import pathlib
from typing import Any

import merhist.crawler
import merhist.handle
import my_lib.openpyxl_util
import openpyxl
import openpyxl.drawing.image
import openpyxl.drawing.spreadsheet_drawing
import openpyxl.drawing.xdr
import openpyxl.styles
import openpyxl.utils

STATUS_INSERT_ITEM: str = "[generate] Insert item"
STATUS_ALL: str = "[generate] Excel file"


SHOP_NAME: str = "メルカリ"

SHEET_DEF = {
    "BOUGHT": {
        "SHEET_TITLE": f"【{SHOP_NAME}】購入",
        "TABLE_HEADER": {
            "row": {"pos": 2, "height": {"default": 80, "without_thumb": 25}},
            "col": {
                "shop_name": {
                    "label": "ショップ",
                    "pos": 2,
                    "width": 15,
                    "format": "@",
                    "value": SHOP_NAME,
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
        "SHEET_TITLE": f"【{SHOP_NAME}】販売",
        "TABLE_HEADER": {
            "row": {"pos": 2, "height": {"default": 80, "without_thumb": 25}},
            "col": {
                "shop_name": {
                    "label": "ショップ",
                    "pos": 2,
                    "width": 15,
                    "format": "@",
                    "value": SHOP_NAME,
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
                    "pos": 17,
                    "width": 19,
                    "format": "@",
                    "link_func": lambda item: merhist.crawler.gen_item_transaction_url(item),
                },
                "error": {
                    "label": "エラー",
                    "pos": 21,
                    "width": 15,
                    "format": "@",
                    "wrap": True,
                    "optional": True,
                },
            },
        },
    },
}


def generate_sheet(
    handle: merhist.handle.Handle,
    book: openpyxl.Workbook,
    is_need_thumb: bool = True,
) -> None:
    transaction_list: list[dict[str, Any]] = [
        {"mode": "BOUGHT", "item_list": handle.get_bought_item_list()},
        {"mode": "SOLD", "item_list": handle.get_sold_item_list()},
    ]

    for transaction_info in transaction_list:
        handle.set_progress_bar(STATUS_INSERT_ITEM, len(transaction_info["item_list"]))

        my_lib.openpyxl_util.generate_list_sheet(
            book,
            transaction_info["item_list"],
            SHEET_DEF[transaction_info["mode"]],
            is_need_thumb,
            lambda item: handle.get_thumb_path(item),
            lambda status: handle.set_status(status),
            lambda: handle.progress_bar[STATUS_ALL].update(),
            lambda: handle.progress_bar[STATUS_INSERT_ITEM].update(),
        )


def generate_table_excel(
    handle: merhist.handle.Handle,
    excel_file: pathlib.Path,
    is_need_thumb: bool = True,
) -> None:
    handle.set_status("エクセルファイルの作成を開始します...")
    handle.set_progress_bar(STATUS_ALL, 2 + 3 * 2)

    logging.info("Start to Generate excel file")

    book = openpyxl.Workbook()
    book._named_styles["Normal"].font = handle.config.excel_font  # noqa: SLF001

    handle.progress_bar[STATUS_ALL].update()

    handle.normalize()

    generate_sheet(handle, book, is_need_thumb)

    book.remove(book.worksheets[0])

    handle.set_status("エクセルファイルを書き出しています...")

    book.save(excel_file)

    handle.progress_bar[STATUS_ALL].update()

    book.close()

    handle.progress_bar[STATUS_ALL].update()

    handle.set_status("完了しました！")

    logging.info("Complete to Generate excel file")


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    import merhist.config

    args = docopt.docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config_file: str = args["-c"]
    excel_file: pathlib.Path = pathlib.Path(args["-o"])
    need_thumb: bool = not args["-N"]

    config = merhist.config.Config.load(my_lib.config.load(config_file))

    handle = merhist.handle.Handle(config)

    generate_table_excel(handle, excel_file, need_thumb)

    handle.finish()
