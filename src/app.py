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


def execute_fetch(handle, continue_mode, debug_mode):
    try:
        merhist.crawler.execute_login(handle)
        merhist.crawler.fetch_order_item_list(handle, continue_mode, debug_mode)
    except:
        driver, wait = merhist.handle.get_selenium_driver(handle)
        my_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),  # noqa: S311
            merhist.handle.get_debug_dir_path(handle),
        )
        raise


def execute(config, continue_mode, export_mode=False, need_thumb=True, debug_mode=False):
    handle = merhist.handle.create(config)

    try:
        if not export_mode:
            try:
                execute_fetch(handle, continue_mode, debug_mode)
            except Exception:
                driver, _ = merhist.handle.get_selenium_driver(handle)
                logging.exception("Failed to fetch data: %s", driver.current_url)
                merhist.handle.set_status(handle, "データの収集中にエラーが発生しました", is_error=True)

        try:
            merhist.history.generate_table_excel(
                handle, merhist.handle.get_excel_file_path(handle), need_thumb
            )
        except Exception:
            merhist.handle.set_status(handle, "エクセルファイルの生成中にエラーが発生しました", is_error=True)
            logging.exception("Failed to generate Excel file.")
    finally:
        merhist.handle.finish(handle)

    if not debug_mode:
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

    export_mode = args["-e"]
    need_thumb = not args["-N"]

    debug_mode = args["-d"]

    my_lib.logger.init("bot.merhist", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file, pathlib.Path(SCHEMA_CONFIG))

    execute(config, is_continue_mode, export_mode, need_thumb, debug_mode)
