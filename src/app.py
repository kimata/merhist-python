#!/usr/bin/env python3
"""
メルカリから販売履歴や購入履歴を収集して、Excel ファイルとして出力します。

Usage:
  merhist.py [-c CONFIG] [-e] [--fA|--fB|--fS] [-N] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  --fA              : 強制的にデータを収集し直します。(販売履歴も購入履歴も)
  --fB              : 購入履歴に関し、強制的にデータを収集し直します。
  --fS              : 販売履歴に関し、強制的にデータを収集し直します。
  -e                : データ収集は行わず、Excel ファイルの出力のみ行います。
  -N                : サムネイル画像を含めないようにします。
  -D                : デバッグモードで動作します。
"""
from __future__ import annotations

import logging
import pathlib
import random
import sys
from typing import Any

import merhist.config
import merhist.crawler
import merhist.handle
import merhist.history
import my_lib.selenium_util
import my_lib.store.mercari.exceptions

SCHEMA_CONFIG: str = "schema/config.schema"


def execute_fetch(
    handle: merhist.handle.Handle,
    continue_mode: merhist.crawler.ContinueMode,
    debug_mode: bool,
) -> None:
    try:
        merhist.crawler.execute_login(handle)
        merhist.crawler.fetch_order_item_list(handle, continue_mode, debug_mode)
    except Exception:
        driver, _ = handle.get_selenium_driver()
        my_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),  # noqa: S311
            handle.config.debug_dir_path,
        )
        raise


def execute(
    config: merhist.config.Config,
    continue_mode: merhist.crawler.ContinueMode,
    export_mode: bool = False,
    need_thumb: bool = True,
    debug_mode: bool = False,
) -> int:
    """メイン処理を実行する。

    Returns:
        int: 終了コード（0: 成功、1: エラー）
    """
    handle = merhist.handle.Handle(config)
    exit_code = 0

    try:
        if not export_mode:
            try:
                execute_fetch(handle, continue_mode, debug_mode)
            except my_lib.selenium_util.SeleniumError as e:
                logging.exception("Selenium の起動に失敗しました")
                handle.set_status(f"❌ {e}", is_error=True)
                return 1
            except my_lib.store.mercari.exceptions.LoginError as e:
                logging.exception("メルカリへのログインに失敗しました")
                handle.set_status(f"❌ {e}", is_error=True)
                return 1
            except Exception:
                driver, _ = handle.get_selenium_driver()
                logging.exception("Failed to fetch data: %s", driver.current_url)
                handle.set_status("❌ データの収集中にエラーが発生しました", is_error=True)
                exit_code = 1
            finally:
                handle.quit_selenium()

        try:
            merhist.history.generate_table_excel(handle, handle.config.excel_file_path, need_thumb)
        except Exception:
            handle.set_status("❌ エクセルファイルの生成中にエラーが発生しました", is_error=True)
            logging.exception("Failed to generate Excel file.")
            exit_code = 1
    finally:
        handle.finish()

    if not debug_mode:
        input("完了しました。エンターを押すと終了します。")

    return exit_code


######################################################################
if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None
    args = docopt.docopt(__doc__)

    config_file: str = args["-c"]
    is_continue_mode: merhist.crawler.ContinueMode = {
        "bought": not (args["--fA"] or args["--fB"]),
        "sold": not (args["--fA"] or args["--fS"]),
    }

    export_mode: bool = args["-e"]
    need_thumb: bool = not args["-N"]

    debug_mode: bool = args["-D"]

    # TTY環境ではシンプルなログフォーマットを使用（Rich の表示と干渉しないため）
    log_format = my_lib.logger.SIMPLE_FORMAT if sys.stdout.isatty() else None

    my_lib.logger.init(
        "bot.merhist",
        level=logging.DEBUG if debug_mode else logging.INFO,
        log_format=log_format,
    )

    config = merhist.config.Config.load(my_lib.config.load(config_file, pathlib.Path(SCHEMA_CONFIG)))

    sys.exit(execute(config, is_continue_mode, export_mode, need_thumb, debug_mode))
