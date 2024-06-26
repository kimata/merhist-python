#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
メルカリの販売履歴や購入履歴をエクセルファイルに書き出します．

Usage:
  transaction_history.py [-c CONFIG] [-o EXCEL] [-N]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o EXCEL      : 生成する Excel ファイルを指定します．[default: amazhist.xlsx]
  -N            : サムネイル画像を含めないようにします．
"""

import logging

import openpyxl
import openpyxl.utils
import openpyxl.styles
import openpyxl.drawing.image
import openpyxl.drawing.xdr
import openpyxl.drawing.spreadsheet_drawing

import mercari.handle
import mercari.crawler
import local_lib.openpyxl_util

STATUS_INSERT_ITEM = "[generate] Insert item"
STATUS_ALL = "[generate] Excel file"


SHOP_NAME = "メルカリ"

SHEET_DEF = {
    "BOUGHT": {
        "SHEET_TITLE": "【{shop_name}】購入".format(shop_name=SHOP_NAME),
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
                    # NOTE: メルカリ向けでは，他のショップで「date」としている内容を「purchase_date」としているので，読み替える
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
                    # NOTE: メルカリ向けでは，他のショップで「id」としている内容が独立して存在しないため，読み替える
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
        "SHEET_TITLE": "【{shop_name}】販売".format(shop_name=SHOP_NAME),
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
                    # NOTE: メルカリ向けでは，他のショップで「date」としている内容を「purchase_date」としているので，読み替える
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
                    # NOTE: メルカリ向けでは，他のショップで「id」としている内容が独立して存在しないため，読み替える
                    "formal_key": "id",
                    "label": "注文番号",
                    "pos": 17,
                    "width": 19,
                    "format": "@",
                    "link_func": lambda item: mercari.crawler.gen_item_transaction_url(item),
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


def generate_sheet(handle, book, is_need_thumb=True):
    transaction_list = [
        {"mode": "BOUGHT", "item_list": mercari.handle.get_bought_item_list(handle)},
        {"mode": "SOLD", "item_list": mercari.handle.get_sold_item_list(handle)},
    ]

    for transaction_info in transaction_list:
        mercari.handle.set_progress_bar(handle, STATUS_INSERT_ITEM, len(transaction_info["item_list"]))

        local_lib.openpyxl_util.generate_list_sheet(
            book,
            transaction_info["item_list"],
            SHEET_DEF[transaction_info["mode"]],
            is_need_thumb,
            lambda item: mercari.handle.get_thumb_path(handle, item),
            lambda status: mercari.handle.set_status(handle, status),
            lambda: mercari.handle.get_progress_bar(handle, STATUS_ALL).update(),
            lambda: mercari.handle.get_progress_bar(handle, STATUS_INSERT_ITEM).update(),
        )


def generate_table_excel(handle, excel_file, is_need_thumb=True):
    mercari.handle.set_status(handle, "エクセルファイルの作成を開始します...")
    mercari.handle.set_progress_bar(handle, STATUS_ALL, 2 + 3 * 2)

    logging.info("Start to Generate excel file")

    book = openpyxl.Workbook()
    book._named_styles["Normal"].font = mercari.handle.get_excel_font(handle)

    mercari.handle.get_progress_bar(handle, STATUS_ALL).update()

    mercari.handle.normalize(handle)

    generate_sheet(handle, book, is_need_thumb)

    book.remove(book.worksheets[0])

    mercari.handle.set_status(handle, "エクセルファイルを書き出しています...")

    book.save(excel_file)

    mercari.handle.get_progress_bar(handle, STATUS_ALL).update()

    book.close()

    mercari.handle.get_progress_bar(handle, STATUS_ALL).update()

    mercari.handle.set_status(handle, "完了しました！")

    logging.info("Complete to Generate excel file")


if __name__ == "__main__":
    from docopt import docopt

    import local_lib.logger
    import local_lib.config

    args = docopt(__doc__)

    local_lib.logger.init("test", level=logging.INFO)

    config = local_lib.config.load(args["-c"])
    excel_file = args["-o"]
    is_need_thumb = not args["-N"]

    handle = mercari.handle.create(config)

    generate_table_excel(handle, excel_file, is_need_thumb)

    mercari.handle.finish(handle)
