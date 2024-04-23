#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
メルカリから販売履歴や購入履歴を収集して，Excel ファイルとして出力します．

Usage:
  merhist.py [-c CONFIG] [-e] [--fA|--fB|--fS] [-N]

Options:
  -c CONFIG     : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  --fA          : 強制的にデータを収集し直します．(販売履歴も購入履歴も)
  --fB          : 購入履歴に関し，強制的にデータを収集し直します．
  --fS          : 購入履歴に関し，強制的にデータを収集し直します．
  -e            : データ収集は行わず，Excel ファイルの出力のみ行います．
  -N            : サムネイル画像を含めないようにします．
"""

import logging
import random

import mercari.handle
import mercari.crawler
import mercari.transaction_history
import local_lib.selenium_util

NAME = "amazhist"
VERSION = "0.1.0"


def execute_fetch(handle, is_continue_mode):
    try:
        mercari.crawler.fetch_sold_item_list(handle, is_continue_mode["sold"])
        mercari.crawler.fetch_bought_item_list(handle, is_continue_mode["bought"])
    except:
        driver, wait = mercari.handle.get_selenium_driver(handle)
        local_lib.selenium_util.dump_page(
            driver, int(random.random() * 100), mercari.handle.get_debug_dir_path(handle)
        )
        raise


def execute(config, is_continue_mode, is_export_mode=False, is_need_thumb=True):
    handle = mercari.handle.create(config)

    try:
        if not is_export_mode:
            execute_fetch(handle, is_continue_mode)
        mercari.transaction_history.generate_table_excel(
            handle, mercari.handle.get_excel_file_path(handle), is_need_thumb
        )

        mercari.handle.finish(handle)
    except:
        mercari.handle.set_status(handle, "エラーが発生しました", is_error=True)
        logging.error(traceback.format_exc())

    input("完了しました．エンターを押すと終了します．")


######################################################################
if __name__ == "__main__":
    from docopt import docopt
    import traceback

    import local_lib.logger
    import local_lib.config

    args = docopt(__doc__)

    local_lib.logger.init("merhist", level=logging.INFO)

    config_file = args["-c"]
    is_continue_mode = {
        "bought": not (args["--fA"] or args["--fB"]),
        "sold": not (args["--fA"] or args["--fS"]),
    }

    is_export_mode = args["-e"]
    is_need_thumb = not args["-N"]

    config = local_lib.config.load(args["-c"])

    try:
        execute(config, is_continue_mode, is_export_mode, is_need_thumb)
    except:
        logging.error(traceback.format_exc())
