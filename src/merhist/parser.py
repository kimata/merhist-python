#!/usr/bin/env python3
"""
HTMLテキストを解析するパース関数群

Selenium で取得したテキストデータを解析し、適切な型に変換します。
これらの関数は Selenium に依存せず、純粋なロジックとしてテスト可能です。
"""

from __future__ import annotations

import datetime
import re

import merhist.exceptions


def parse_date(date_text: str) -> datetime.datetime:
    """日付テキストをパース

    Args:
        date_text: 日付テキスト（例: "2025/01/15"）

    Returns:
        datetime オブジェクト

    Raises:
        ValueError: パースできない形式の場合
    """
    return datetime.datetime.strptime(date_text, "%Y/%m/%d")


def parse_datetime(datetime_text: str, is_japanese: bool = True) -> datetime.datetime:
    """日時テキストをパース

    Args:
        datetime_text: 日時テキスト
        is_japanese: True の場合 "2025年01月15日 10:30" 形式、
                     False の場合 "2025/01/15 10:30" 形式

    Returns:
        datetime オブジェクト

    Raises:
        ValueError: パースできない形式の場合
    """
    if is_japanese:
        return datetime.datetime.strptime(datetime_text, "%Y年%m月%d日 %H:%M")
    else:
        return datetime.datetime.strptime(datetime_text, "%Y/%m/%d %H:%M")


def parse_price(text: str) -> int:
    """価格テキストから数値を抽出

    Args:
        text: 価格テキスト（例: "¥1,500", "1,500", "￥1,234,567"）

    Returns:
        価格（整数）

    Raises:
        ValueError: パースできない形式の場合
    """
    cleaned = text.replace("¥", "").replace("￥", "").replace(",", "").strip()
    if not cleaned:
        raise ValueError(f"価格テキストが空です: {text!r}")
    return int(cleaned)


def parse_rate(text: str) -> int:
    """手数料率テキストから数値を抽出

    Args:
        text: 手数料率テキスト（例: "10%"）

    Returns:
        手数料率（整数）

    Raises:
        ValueError: パースできない形式の場合
    """
    cleaned = text.replace("%", "").strip()
    if not cleaned:
        raise ValueError(f"手数料率テキストが空です: {text!r}")
    return int(cleaned)


def parse_sold_count(paging_text: str) -> int:
    """ページングテキストから売上件数を抽出

    Args:
        paging_text: ページングテキスト（例: "1～20/全100件"）

    Returns:
        総件数（整数）

    Raises:
        InvalidPageFormatError: パースできない形式の場合
    """
    match = re.match(r".*全(\d+)件", paging_text)
    if match is None:
        raise merhist.exceptions.InvalidPageFormatError("ページング情報の形式が想定と異なります", paging_text)
    return int(match.group(1))


def parse_price_with_shipping(body_text: str, number_text: str | None = None) -> int:
    """送料込み考慮の価格パース

    Args:
        body_text: 価格欄の全テキスト（"送料込み" を含む可能性あり）
        number_text: 数値部分のテキスト（"送料込み" でない場合に使用）

    Returns:
        価格（整数）。送料込みの場合は 0
    """
    if "送料込み" in body_text:
        return 0
    if number_text is None:
        return parse_price(body_text)
    return parse_price(number_text)
