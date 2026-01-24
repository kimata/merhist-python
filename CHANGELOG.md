# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.3] - 2026-01-24

### Changed

- 動的バージョニングに移行
- TypedDict と辞書リテラルを dataclass に変換
- エントリーポイントを `[project.scripts]` パターンに統一
- BrowserManager を使用するように変更
- 進捗表示を `my_lib.cui_progress` に移行
- セッションリトライを `with_session_retry()` で共通化

### Fixed

- CLI エントリーポイントを修正
- テストの mock.patch パスを修正

## [0.2.2] - 2025-12-31

### Added

- ブラウザ起動失敗時にプロファイル削除する `-R` オプションを追加

### Changed

- config.schema を `schema/` ディレクトリに移動
- GitHub リリースアクションを `softprops/action-gh-release` へ移行

### Fixed

- テーブル幅のオーバーフロー対策を追加
- CI の Chrome プロファイル破損対策を追加

## [0.2.1] - 2025-12-30

### Added

- 非 TTY 環境でのログ出力を改善
- Selenium/Login エラー時にエラー終了するように変更
- ステータスメッセージの UI を改善
- カスタム警告ハンドラーを実装
- CLAUDE.md を追加

### Changed

- プログレスバー表示を enlighten から rich へ移行
- XPath セレクタを `xpath.py` に集約
- パース関数を `parser.py` に分離

### Fixed

- 未完了取引ページの行タイトル取得 XPath を修正
- 非 TTY 環境でのプログレスバー更新時の KeyError を修正
- pyright の型チェックエラーを修正
- テストの失敗を修正
- Slack 設定の型チェックを修正して mypy エラーを解消

## [0.2.0] - 2025-12-23

### Added

- メルカリの販売履歴・購入履歴を自動収集する機能
- LINE 認証を経由したログイン処理
- 商品画像のサムネイル付き Excel 出力
- 増分更新対応（中断しても途中から再開可能）
- Slack 連携による認証コードのやり取り
- `-e` オプション: Excel 出力のみ
- `--fA` オプション: 全データ強制再収集
- `--fB` オプション: 購入履歴のみ強制再収集
- `--fS` オプション: 販売履歴のみ強制再収集
- `-N` オプション: サムネイルなし
- `-D` オプション: デバッグモード
- Ctrl+C による安全な終了機能
- プログレスバーに推定残り時間を表示
- InvalidSessionIdException 発生時にプロファイル削除してリトライする機能
- Slack 設定を柔軟化し captcha のみでも動作可能に

### Changed

- 中間データの保存形式を pickle から SQLite に移行
- パッケージマネージャを Rye から uv に変更
- Handle クラスの整理と Selenium 終了処理の改善
- データ収集後に Selenium を終了してから Excel 生成を開始

[Unreleased]: https://github.com/kimata/merhist-python/compare/v0.2.3...HEAD
[0.2.3]: https://github.com/kimata/merhist-python/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/kimata/merhist-python/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/kimata/merhist-python/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/kimata/merhist-python/releases/tag/v0.2.0
