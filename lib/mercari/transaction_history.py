#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
メルカリの販売履歴や購入履歴をエクセルファイルに書き出します．

Usage:
  transaction_history.py [-c CONFIG] [-o EXCEL]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o EXCEL      : CONFIG を設定ファイルとして読み込んで実行します．[default: merhist.xlsx]
"""

import logging

import openpyxl
import openpyxl.utils
import openpyxl.styles
import openpyxl.drawing.image
import openpyxl.drawing.xdr
import openpyxl.drawing.spreadsheet_drawing

import mercari.handle


SHEET_DEF = {
    "BOUGHT": {
        "LABEL": "購入",
        "TABLE_HEADER": {
            "row": {"pos": 2, "height": 80},
            "col": {
                "purchase_date": {
                    "label": "購入日",
                    "pos": 2,
                    "width": 23,
                    "format": 'yyyy"年"mm"月"dd"日 ("aaa")"',
                },
                "name": {"label": "商品名", "pos": 3, "width": 70, "wrap": True, "format": "@"},
                "image": {"label": "画像", "pos": 4, "width": 12},
                "price": {
                    "label": "価格",
                    "pos": 5,
                    "width": 16,
                    "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
                    "optional": True,
                },
                "condition": {"label": "コンディション", "pos": 6, "width": 13, "format": "@", "wrap": True},
                "postage_charge": {"label": "送料負担", "pos": 7, "width": 10, "format": "@", "wrap": True},
                "category": {"label": "カテゴリ", "pos": 8, "length": 3, "width": 16, "wrap": True},
                "shop": {"label": "ショップ", "pos": 11, "width": 13, "format": "@"},
                "shipping_method": {"label": "配送方法", "pos": 12, "width": 10, "format": "@", "wrap": True},
                "seller_region": {"label": "発送元の地域", "pos": 13, "width": 16, "format": "@"},
                "id": {"label": "商品ID", "pos": 14, "width": 13, "format": "@"},
                "error": {"label": "エラー", "pos": 15, "width": 15, "format": "@", "wrap": True},
            },
        },
    },
    "SOLD": {
        "LABEL": "販売",
        "TABLE_HEADER": {
            "row": {"pos": 2, "height": 80},
            "col": {
                "purchase_date": {
                    "label": "購入日",
                    "pos": 2,
                    "width": 23,
                    "format": 'yyyy"年"mm"月"dd"日 ("aaa")"',
                },
                "name": {"label": "商品名", "pos": 3, "width": 70, "wrap": True, "format": "@"},
                "image": {"label": "画像", "pos": 4, "width": 12},
                "price": {
                    "label": "価格",
                    "pos": 5,
                    "width": 16,
                    "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
                },
                "commission": {
                    "label": "手数料",
                    "pos": 6,
                    "width": 10,
                    "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
                },
                "postage": {
                    "label": "送料",
                    "pos": 7,
                    "width": 10,
                    "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
                },
                "profit": {
                    "label": "回収金額",
                    "pos": 8,
                    "width": 16,
                    "format": '_ ¥* #,##0_ ;_ ¥* -#,##0_ ;_ ¥* "-"_ ;_ @_ ',  # NOTE: 末尾の空白要
                },
                "condition": {"label": "コンディション", "pos": 9, "width": 13, "format": "@", "wrap": True},
                "postage_charge": {"label": "送料負担", "pos": 10, "width": 10, "format": "@", "wrap": True},
                "shipping_method": {"label": "配送方法", "pos": 11, "width": 10, "format": "@", "wrap": True},
                "commission_rate": {
                    "label": "手数料率",
                    "pos": 12,
                    "width": 10,
                    "format": "0%",
                    "conv_func": lambda x: x / 100,
                },
                "category": {"label": "カテゴリ", "pos": 13, "length": 3, "width": 16, "wrap": True},
                "completion_date": {
                    "label": "取引完了日",
                    "pos": 16,
                    "width": 23,
                    "format": 'yyyy"年"mm"月"dd"日 ("aaa")"',
                },
                "seller_region": {"label": "発送元の地域", "pos": 17, "width": 16, "format": "@"},
                "id": {"label": "商品ID", "pos": 17, "width": 13, "format": "@"},
                "error": {"label": "エラー", "pos": 18, "width": 15, "format": "@", "wrap": True},
            },
        },
    },
}

STATUS_INSERT_ITEM = "[generate] Insert item"
STATUS_ALL = "[generate] Excel file"


def gen_text_pos(row, col):
    return "{col}{row}".format(
        row=row,
        col=openpyxl.utils.get_column_letter(col),
    )


def set_header_cell_style(sheet, row, col, value, width, style):
    sheet.cell(row, col).value = value
    sheet.cell(row, col).style = "Normal"
    sheet.cell(row, col).border = style["border"]
    sheet.cell(row, col).fill = style["fill"]

    if width is not None:
        sheet.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width


def set_item_cell_style(sheet, row, col, value, style):
    sheet.cell(row, col).value = value
    sheet.cell(row, col).style = "Normal"
    sheet.cell(row, col).border = style["border"]
    sheet.cell(row, col).alignment = openpyxl.styles.Alignment(wrap_text=style["text_wrap"], vertical="top")

    if "text_format" in style:
        sheet.cell(row, col).number_format = style["text_format"]


def insert_table_header(handle, mode, sheet, row, style):
    mercari.handle.set_status(handle, "テーブルのヘッダを設定しています...")

    for key in SHEET_DEF[mode]["TABLE_HEADER"]["col"].keys():
        col = SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]["pos"]
        if "width" in SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]:
            width = SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]["width"]
        else:
            width = None

        if key == "category":
            for i in range(SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]["length"]):
                set_header_cell_style(
                    sheet,
                    row,
                    col + i,
                    SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]["label"] + " ({i})".format(i=i + 1),
                    width,
                    style,
                )
        else:
            set_header_cell_style(
                sheet, row, col, SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]["label"], width, style
            )


def insert_table_cell_image(handle, mode, sheet, row, col, item):
    thumb_path = mercari.handle.get_thumb_path(handle, item)

    if (thumb_path is None) or (not thumb_path.exists()):
        return

    img = openpyxl.drawing.image.Image(thumb_path)

    # NOTE: マジックナンバー「8」は下記等を参考にして設定．(日本語フォントだと 8 が良さそう)
    # > In all honesty, I cannot tell you how many blogs and stack overflow answers
    # > I read before I stumbled across this magic number: 7.5
    # https://imranhugo.medium.com/how-to-right-align-an-image-in-excel-cell-using-python-and-openpyxl-7ca75a85b13a
    cell_width_pix = SHEET_DEF[mode]["TABLE_HEADER"]["col"]["image"]["width"] * 8
    cell_height_pix = openpyxl.utils.units.points_to_pixels(SHEET_DEF[mode]["TABLE_HEADER"]["row"]["height"])

    cell_width_emu = openpyxl.utils.units.pixels_to_EMU(cell_width_pix)
    cell_height_emu = openpyxl.utils.units.pixels_to_EMU(cell_height_pix)

    margin_pix = 2
    content_width_pix = cell_width_pix - (margin_pix * 2)
    content_height_pix = cell_height_pix - (margin_pix * 2)

    content_ratio = content_width_pix / content_height_pix
    image_ratio = img.width / img.height

    if (img.width > content_width_pix) or (img.height > content_height_pix):
        if image_ratio > content_ratio:
            # NOTE: 画像の横幅をセルの横幅に合わせる
            scale = content_width_pix / img.width
        else:
            # NOTE: 画像の高さをセルの高さに合わせる
            scale = content_height_pix / img.height

        img.width *= scale
        img.height *= scale

    image_width_emu = openpyxl.utils.units.pixels_to_EMU(img.width)
    image_height_emu = openpyxl.utils.units.pixels_to_EMU(img.height)

    col_offset_emu = (cell_width_emu - image_width_emu) / 2
    row_offset_emu = (cell_height_emu - image_height_emu) / 2

    marker_1 = openpyxl.drawing.spreadsheet_drawing.AnchorMarker(
        col=col - 1, row=row - 1, colOff=col_offset_emu, rowOff=row_offset_emu
    )
    marker_2 = openpyxl.drawing.spreadsheet_drawing.AnchorMarker(
        col=col, row=row, colOff=-col_offset_emu, rowOff=-row_offset_emu
    )
    size = openpyxl.drawing.xdr.XDRPositiveSize2D(image_width_emu, image_height_emu)

    img.anchor = openpyxl.drawing.spreadsheet_drawing.TwoCellAnchor(_from=marker_1, to=marker_2)

    sheet.add_image(img)


def gen_item_cell_style(mode, base_style, key):
    style = base_style.copy()

    if "format" in SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]:
        style["text_format"] = SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]["format"]

    if "wrap" in SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]:
        style["text_wrap"] = SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]["wrap"]
    else:
        style["text_wrap"] = False

    return style


def insert_table_item(handle, mode, sheet, row, item, style):
    for key in SHEET_DEF[mode]["TABLE_HEADER"]["col"].keys():
        col = SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]["pos"]

        cell_style = gen_item_cell_style(mode, style, key)

        if key == "category":
            for i in range(SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]["length"]):
                if i < len(item["category"]):
                    value = item[key][i]
                else:
                    value = ""
                set_item_cell_style(sheet, row, col + i, value, cell_style)
        elif key == "image":
            sheet.cell(row, col).border = cell_style["border"]
            insert_table_cell_image(handle, mode, sheet, row, col, item)
        else:
            if (
                ("optional" in SHEET_DEF[mode]["TABLE_HEADER"]["col"][key])
                and (not SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]["optional"])
            ) or (key in item):
                value = item[key]

                if "conv_func" in SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]:
                    value = SHEET_DEF[mode]["TABLE_HEADER"]["col"][key]["conv_func"](value)
            else:
                value = None

            set_item_cell_style(sheet, row, col, value, cell_style)

        if key == "id":
            sheet.cell(row, col).hyperlink = item["url"]


def setting_table_view(handle, mode, sheet, row_last):
    mercari.handle.set_status(handle, "テーブルの表示設定しています...")

    sheet.column_dimensions.group(
        openpyxl.utils.get_column_letter(SHEET_DEF[mode]["TABLE_HEADER"]["col"]["image"]["pos"]),
        openpyxl.utils.get_column_letter(SHEET_DEF[mode]["TABLE_HEADER"]["col"]["image"]["pos"]),
        hidden=False,
    )

    sheet.freeze_panes = gen_text_pos(
        SHEET_DEF[mode]["TABLE_HEADER"]["row"]["pos"] + 1,
        SHEET_DEF[mode]["TABLE_HEADER"]["col"]["price"]["pos"] + 1,
    )

    sheet.auto_filter.ref = "{start}:{end}".format(
        start=gen_text_pos(
            SHEET_DEF[mode]["TABLE_HEADER"]["row"]["pos"],
            min(map(lambda x: x["pos"], SHEET_DEF[mode]["TABLE_HEADER"]["col"].values())),
        ),
        end=gen_text_pos(
            row_last, max(map(lambda x: x["pos"], SHEET_DEF[mode]["TABLE_HEADER"]["col"].values()))
        ),
    )
    sheet.sheet_view.showGridLines = False


def insert_sum_row(handle, mode, sheet, row_last, style):
    logging.info("Insert sum row")

    mercari.handle.set_status(handle, "集計行を挿入しています...")

    col = SHEET_DEF[mode]["TABLE_HEADER"]["col"]["price"]["pos"]
    set_item_cell_style(
        sheet,
        row_last + 1,
        col,
        "=sum({cell_first}:{cell_last})".format(
            cell_first=gen_text_pos(SHEET_DEF[mode]["TABLE_HEADER"]["row"]["pos"] + 1, col),
            cell_last=gen_text_pos(row_last, col),
        ),
        gen_item_cell_style(mode, style, "price"),
    )


def generate_list_sheet(handle, mode, book, item_list):
    sheet = book.create_sheet()
    sheet.title = "{label}アイテム一覧".format(label=SHEET_DEF[mode]["LABEL"])

    side = openpyxl.styles.Side(border_style="thin", color="000000")
    border = openpyxl.styles.Border(top=side, left=side, right=side, bottom=side)
    fill = openpyxl.styles.PatternFill(patternType="solid", fgColor="F2F2F2")

    style = {"border": border, "fill": fill}

    row = SHEET_DEF[mode]["TABLE_HEADER"]["row"]["pos"]
    insert_table_header(handle, mode, sheet, row, style)

    mercari.handle.get_progress_bar(handle, STATUS_ALL).update()

    mercari.handle.set_progress_bar(handle, STATUS_INSERT_ITEM, len(item_list))
    mercari.handle.set_status(handle, "{label}商品の記載をしています...".format(label=SHEET_DEF[mode]["LABEL"]))

    row += 1
    for item in item_list:
        sheet.row_dimensions[row].height = SHEET_DEF[mode]["TABLE_HEADER"]["row"]["height"]
        insert_table_item(handle, mode, sheet, row, item, style)
        mercari.handle.get_progress_bar(handle, STATUS_INSERT_ITEM).update()
        row += 1

    row_last = row - 1

    mercari.handle.get_progress_bar(handle, STATUS_INSERT_ITEM).update()
    mercari.handle.get_progress_bar(handle, STATUS_ALL).update()

    # NOTE: 下記を行うと，ピボットテーブルの作成の邪魔になるのでコメントアウト
    # insert_sum_row(sheet, row_last, style)
    setting_table_view(handle, mode, sheet, row_last)

    mercari.handle.get_progress_bar(handle, STATUS_ALL).update()


def generate_table_excel(handle, excel_file):
    mercari.handle.set_status(handle, "エクセルファイルの作成を開始します...")
    mercari.handle.set_progress_bar(handle, STATUS_ALL, 5)

    logging.info("Start to Generate excel file")

    book = openpyxl.Workbook()
    book._named_styles["Normal"].font = mercari.handle.get_excel_font(handle)

    mercari.handle.get_progress_bar(handle, STATUS_ALL).update()

    transaction_list = [
        {"mode": "BOUGHT", "item_list": mercari.handle.get_bought_item_list(handle)},
        {"mode": "SOLD", "item_list": mercari.handle.get_sold_item_list(handle)},
    ]

    mercari.handle.normalize(handle)
    for transaction_info in transaction_list:
        generate_list_sheet(handle, transaction_info["mode"], book, transaction_info["item_list"])
    book.remove_sheet(book.worksheets[0])

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

    handle = mercari.handle.create(config)

    generate_table_excel(handle, excel_file)

    mercari.handle.finish(handle)
