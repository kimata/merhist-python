#!/usr/bin/env python3
"""
メルカリから販売履歴や購入履歴を収集して、Excel ファイルとして出力します。

Usage:
  merhist.py [-c CONFIG] [-e] [--fA|--fB|--fS] [-N] [-D] [-R]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  --fA              : 強制的にデータを収集し直します。(販売履歴も購入履歴も)
  --fB              : 購入履歴に関し、強制的にデータを収集し直します。
  --fS              : 販売履歴に関し、強制的にデータを収集し直します。
  -e                : データ収集は行わず、Excel ファイルの出力のみ行います。
  -N                : サムネイル画像を含めないようにします。
  -D                : デバッグモードで動作します。
  -R                : ブラウザ起動失敗時にプロファイルを削除します。
"""

from __future__ import annotations

import logging
import pathlib
import random
import sys

import my_lib.chrome_util
import my_lib.selenium_util
import my_lib.store.mercari.exceptions
import selenium.common.exceptions

import merhist.config
import merhist.const
import merhist.crawler
import merhist.handle
import merhist.history

_SCHEMA_CONFIG: str = "schema/config.schema"

_MAX_SESSION_RETRY_COUNT = 1


def _execute_fetch(
    handle: merhist.handle.Handle,
    continue_mode: merhist.crawler.ContinueMode,
) -> None:
    try:
        merhist.crawler.execute_login(handle)
        merhist.crawler.fetch_order_item_list(handle, continue_mode)
    except selenium.common.exceptions.InvalidSessionIdException:
        # セッションエラーはドライバーが壊れているのでダンプを試みず re-raise
        logging.warning("セッションエラーが発生しました（ブラウザがクラッシュした可能性があります）")
        raise
    except Exception:
        # シャットダウン要求時はダンプをスキップ（ドライバーが既に閉じている可能性が高い）
        if not merhist.crawler.is_shutdown_requested():
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
    clear_profile_on_browser_error: bool = False,
) -> int:
    """メイン処理を実行する。

    セッションエラー（ブラウザクラッシュ等）が発生した場合、
    clear_profile_on_browser_error=True であればプロファイルを削除してリトライする。

    Returns:
        int: 終了コード（0: 成功、1: エラー）
    """
    handle = merhist.handle.Handle(
        config,
        clear_profile_on_browser_error=clear_profile_on_browser_error,
        debug_mode=debug_mode,
        ignore_cache=debug_mode,
    )
    exit_code = 0

    try:
        if not export_mode:
            for retry in range(_MAX_SESSION_RETRY_COUNT + 1):
                try:
                    _execute_fetch(handle, continue_mode)
                    break  # 成功したらループを抜ける
                except selenium.common.exceptions.InvalidSessionIdException:
                    handle.quit_selenium()
                    if retry < _MAX_SESSION_RETRY_COUNT and clear_profile_on_browser_error:
                        logging.warning(
                            "セッションエラーが発生しました。プロファイルを削除してリトライします（%d/%d）",
                            retry + 1,
                            _MAX_SESSION_RETRY_COUNT,
                        )
                        handle.set_status(
                            f"🔄 セッションエラー、リトライ中... ({retry + 1}/{_MAX_SESSION_RETRY_COUNT})"
                        )
                        my_lib.chrome_util.delete_profile(
                            merhist.const.SELENIUM_PROFILE_NAME, config.selenium_data_dir_path
                        )
                        continue
                    # リトライ限度を超えた、または clear_profile_on_browser_error=False
                    logging.exception("セッションエラーが発生しました（リトライ不可）")
                    handle.set_status("❌ セッションエラー", is_error=True)
                    return 1
                except my_lib.selenium_util.SeleniumError as e:
                    logging.exception("Selenium の起動に失敗しました")
                    handle.set_status(f"❌ {e}", is_error=True)
                    return 1
                except my_lib.store.mercari.exceptions.LoginError as e:
                    logging.exception("メルカリへのログインに失敗しました")
                    handle.set_status(f"❌ {e}", is_error=True)
                    return 1
                except Exception:
                    # シャットダウン要求時は正常終了扱い（tracebackを出さない）
                    if not merhist.crawler.is_shutdown_requested():
                        driver, _ = handle.get_selenium_driver()
                        logging.exception("Failed to fetch data: %s", driver.current_url)
                        handle.set_status("❌ データの収集中にエラーが発生しました", is_error=True)
                        exit_code = 1
                    break  # 他の例外ではリトライしない
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

    if not handle.debug_mode:
        handle.pause_live()
        input("完了しました。エンターを押すと終了します。")

    return exit_code


######################################################################
if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file: str = args["-c"]
    is_continue_mode: merhist.crawler.ContinueMode = {
        "bought": not (args["--fA"] or args["--fB"]),
        "sold": not (args["--fA"] or args["--fS"]),
    }

    export_mode: bool = args["-e"]
    need_thumb: bool = not args["-N"]

    debug_mode: bool = args["-D"]
    clear_profile_on_browser_error: bool = args["-R"]

    # TTY環境ではシンプルなログフォーマットを使用（Rich の表示と干渉しないため）
    log_format = my_lib.logger.SIMPLE_FORMAT if sys.stdout.isatty() else None

    my_lib.logger.init(
        "bot.merhist",
        level=logging.DEBUG if debug_mode else logging.INFO,
        log_format=log_format,
    )

    config = merhist.config.Config.load(my_lib.config.load(config_file, pathlib.Path(_SCHEMA_CONFIG)))

    sys.exit(
        execute(config, is_continue_mode, export_mode, need_thumb, debug_mode, clear_profile_on_browser_error)
    )
