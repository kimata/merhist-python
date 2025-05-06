# merhist-python

merhist-python は，メルカリの販売履歴や購入履歴を収集し，
サムネイル付きの Excel 形式で出力するソフトウェアです．

## 動作環境

基本的には，Python と Selenium が動作する環境であれば動作します．
下記の環境での動作を確認しています．

- Linux (Ubuntu 22.04)
- Windows 11

## 設定

同封されている `config.example.yaml` を `config.yaml` に名前変更して，下記の部分を書き換えます。

```yaml:config.yaml
    line:
        user: LINE のユーザ ID
        pass: LINE のログインパスワード
```

メルカリに LINE アカウントでログインするため、LINE にログインするのに必要な情報を指定します。
(一度パスコードでログインできるようにした場合、メルカリにメールアドレスとパスワードではログインできなくなります)

ログインに関する認証コードのやり取りを Slack で行いたい場合は、下記の部分もコメントアウトを解除した上で書き換えてください。
コメントアウトしたままだと、標準入出力経由でやり取りする動作になります。

```yaml:config.yaml
slack:
    bot_token: xoxp-XXXXXXXXXXXX-XXXXXXXXXXXX-XXXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    from: Mercari Bot
    captcha:
        channel:
            name: "#captcha"
            id: XXXXXXXXXXX
```

## Linux での動かし方

### 準備

```bash:bash
sudo apt install docker
```

### 実行

```bash:bash
docker compose run --build --rm merhist
```

取引履歴の数が沢山ある場合，1時間以上がかかりますので，放置しておくのがオススメです．

なお，何らかの事情で中断した場合，再度実行することで，途中から再開できます．
コマンドを実行した後に注文履歴が増えた場合も，再度実行することで前回以降のデータからデータ収集を再開できます．

### Docker を使いたくない場合

[Rye](https://rye.astral.sh/) と Google Chrome がインストールされた環境であれば，
下記のようにして Docker を使わずに実行できます．

```
rye sync
rye run python src/app.py
```

## Windows での動かし方

### 準備

[リリースページ](https://github.com/kimata/merhist-python/releases) から「merhist-windows_x64-binary-*.zip」を
ダウンロードします．

#### 注意

環境によってはファイルがウィルス判定されることがあります．
これは，Python スクリプトを [Nuitka](https://nuitka.net/) を使って実行ファイルを生成していることが原因です．

ウィルス判定されてしまった場合は，検疫されないように Windows Defender の設定を一時的に変更お願いします．

### 実行

`merhist.exe` をダブルクリックすればOKです．

## ライセンス

Apache License Version 2.0 を適用します．
