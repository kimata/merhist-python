# 📊 merhist-python

メルカリの販売履歴・購入履歴を収集し、サムネイル付きの Excel ファイルとして出力するツール

[![Test Status](https://github.com/kimata/merhist-python/actions/workflows/test.yaml/badge.svg)](https://github.com/kimata/merhist-python/actions/workflows/test.yaml)
[![Test Report](https://img.shields.io/badge/Test_Report-pytest.html-blue)](https://kimata.github.io/merhist-python/pytest.html)
[![Coverage Status](https://coveralls.io/repos/github/kimata/merhist-python/badge.svg?branch=main)](https://coveralls.io/github/kimata/merhist-python?branch=main)

## 📋 概要

メルカリの取引履歴を自動的に収集し、見やすい Excel 形式で出力します。

### 主な特徴

- 📦 **販売履歴の収集** - 出品して売れた商品の履歴を取得
- 🛒 **購入履歴の収集** - 購入した商品の履歴を取得
- 🖼️ **サムネイル付き出力** - 商品画像付きの Excel ファイルを生成
- 🔄 **途中再開対応** - 中断しても途中から再開可能
- 🔐 **LINE認証対応** - LINE経由の安全なログイン処理
- 📱 **Slack連携** - 認証コードのやり取りを Slack 経由で実施可能

### 出力サンプル

![表示サンプル](img/example.png)

## 🖥️ 動作環境

Python と Selenium が動作する環境で動作します。

- Linux (Ubuntu 24.04)
- Windows 11

## 🚀 セットアップ

### 1. 設定ファイルの準備

```bash
cp config.example.yaml config.yaml
```

`config.yaml` を編集して、LINE のログイン情報を設定：

```yaml
login:
    line:
        user: LINE のユーザ ID
        pass: LINE のログインパスワード
```

メルカリに LINE アカウントでログインするため、LINE の認証情報が必要です。

### 2. Slack 連携（オプション）

認証コードのやり取りを Slack で行いたい場合は、以下を設定：

```yaml
slack:
    bot_token: xoxp-XXXXXXXXXXXX-XXXXXXXXXXXX-XXXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    from: Mercari History
    captcha:
        channel:
            name: "#captcha"
            id: XXXXXXXXXXX
```

設定しない場合は、標準入出力経由で認証コードをやり取りします。

## 💻 実行方法

### Docker を使用する場合（推奨）

```bash
# Docker のインストール（未インストールの場合）
sudo apt install docker.io docker-compose-v2

# 実行
docker compose run --build --rm merhist
```

### Docker を使用しない場合

#### uv を使用（推奨）

ブラウザ自動化に Google Chrome を使用するため、事前にインストールしておく必要があります：

```bash
# Google Chrome のインストール（未インストールの場合）
wget -P /tmp https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y /tmp/google-chrome-stable_current_amd64.deb
```

> ⚠️ **重要**: メルカリのボット検出を回避するため、ブラウザは **headful（ヘッドレスではない）** で
> 起動します。GUI の無いサーバー等では **仮想ディスプレイ（Xvfb）が必要**です。

```bash
# uv のインストール（未インストールの場合）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 依存関係のインストール
uv sync

# 実行（GUI のある環境）
uv run merhist

# 実行（GUI の無いサーバー等 — Xvfb 経由）
sudo apt install -y xvfb   # 未インストールの場合
xvfb-run -a -s "-screen 0 1920x1080x24" uv run merhist
```

### Windows で実行する場合

[リリースページ](https://gitlab.green-rabbit.net/kimata/merhist-python/-/releases) から `merhist-windows_x64-binary-*.zip` をダウンロードし、中に入っている `app.exe` を実行してください。

> ⚠️ **注意**: 環境によってはウィルス判定されることがあります。これは Python スクリプトを [Nuitka](https://nuitka.net/) で実行ファイルに変換していることが原因です。検疫されてしまった場合は、Windows Defender の設定を一時的に変更してください。

### コマンドラインオプション

```bash
# 設定ファイルを指定
uv run merhist -c custom-config.yaml

# データ収集せず Excel 出力のみ
uv run merhist -e

# 強制的に全データを再収集
uv run merhist --fA

# 購入履歴のみ強制再収集
uv run merhist --fB

# 販売履歴のみ強制再収集
uv run merhist --fS

# サムネイル画像なしで出力
uv run merhist -N

# デバッグモード
uv run merhist -D

# ブラウザ起動失敗時にプロファイルを削除
uv run merhist -R
```

## ⏱️ 実行時間について

取引履歴の数が多い場合、1時間以上かかることがあります。放置しておくことをお勧めします。

中断した場合でも、再度実行することで途中から再開できます。また、新しい取引が増えた場合も、前回以降のデータのみを収集します。

## 🔧 トラブルシューティング

### 「Looks like you launched a headed browser without having a XServer running」と表示される

ディスプレイ（X サーバー）が無い環境で headful ブラウザを起動しようとしています。`xvfb-run` 経由で実行してください：

```bash
xvfb-run -a -s "-screen 0 1920x1080x24" uv run merhist
```

（メルカリのボット検出回避のため headful 起動が必須です。ヘッドレスでは新規ログインが 403 で失敗します。）

### ブラウザの起動に失敗する（Chrome が見つからない）

Google Chrome がインストールされていません。「実行方法」セクションの手順に従って Google Chrome をインストールしてください。

### 「巡回ロボットの準備をします...」で止まる

内部的に使用している Chrome のプロファイルデータが破損している可能性があります。`data/chrome` ディレクトリを削除すると改善します。

```bash
rm -rf data/chrome
```

## 📚 ドキュメント

- [アーキテクチャ解説](doc/architecture.md) - モジュール構成・実行フロー・データモデルなど、内部構造の詳細（SVG 図解付き）

## 📝 ライセンス

Apache License Version 2.0

---

<div align="center">

**⭐ このプロジェクトが役に立った場合は、Star をお願いします！**

[🐛 Issue 報告](https://gitlab.green-rabbit.net/kimata/merhist-python/-/issues)

</div>
