#!/usr/bin/env python3
"""
メルカリから販売履歴や購入履歴を収集して，Excel ファイルとして出力します．

Usage:
  merhist.py [-c CONFIG] [-e] [--fA|--fB|--fS] [-N] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  --fA              : 強制的にデータを収集し直します．(販売履歴も購入履歴も)
  --fB              : 購入履歴に関し，強制的にデータを収集し直します．
  --fS              : 購入履歴に関し，強制的にデータを収集し直します．
  -e                : データ収集は行わず，Excel ファイルの出力のみ行います．
  -N                : サムネイル画像を含めないようにします．
  -d                : デバッグモードで動作します．
"""

import logging
import pathlib
import random

import merhist.crawler
import merhist.handle
import merhist.history

SCHEMA_CONFIG = "config.schema"


def execute_fetch(handle, is_continue_mode):
    try:
        merhist.crawler.fetch_bought_item_list(handle, is_continue_mode["bought"])
        merhist.crawler.fetch_sold_item_list(handle, is_continue_mode["sold"])
    except:
        driver, wait = merhist.handle.get_selenium_driver(handle)
        my_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),  # noqa: S311
            merhist.handle.get_debug_dir_path(handle),
        )
        raise


def execute(config, is_continue_mode, is_export_mode=False, is_need_thumb=True):
    handle = merhist.handle.create(config)

    try:
        if not is_export_mode:
            execute_fetch(handle, is_continue_mode)
        merhist.history.generate_table_excel(
            handle, merhist.handle.get_excel_file_path(handle), is_need_thumb
        )

        merhist.handle.finish(handle)
    except Exception:
        merhist.handle.set_status(handle, "エラーが発生しました", is_error=True)
        logging.exception("Failed")

    input("完了しました．エンターを押すと終了します．")


######################################################################
if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    is_continue_mode = {
        "bought": not (args["--fA"] or args["--fB"]),
        "sold": not (args["--fA"] or args["--fS"]),
    }

    is_export_mode = args["-e"]
    is_need_thumb = not args["-N"]

    debug_mode = args["-d"]

    my_lib.logger.init("bot.merhist", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file, pathlib.Path(SCHEMA_CONFIG))

    execute(config, is_continue_mode, is_export_mode, is_need_thumb)
