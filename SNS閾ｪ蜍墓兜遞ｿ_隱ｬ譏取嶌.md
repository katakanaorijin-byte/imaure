# 📘 説明書②|X・Threads 自動投稿の設定マニュアル

サイトの毎朝6時の更新と同時に、**その日の売れ筋TOP3をXとThreadsに自動投稿**する機能の設定方法です。

- 投稿文は自動で作られます(日替わりで言い回しも変わります)
- **片方だけの設定でもOK**です(設定したSNSにだけ投稿されます)
- どちらも**各社の公式API**を使うので、規約違反やアカウント凍結の心配が少ない正規の方法です
- 作業時間:X 約20分/Threads 約15分(どちらも初回だけ)

> ⚠ 先に「説明書.md」のサイト公開(楽天APIキー設定まで)を終わらせてください。
> サイトがデモデータのままだと、間違った内容を投稿しないよう**自動的に投稿が止まる**仕組みになっています。

---

## パートA:X(旧Twitter)の設定

### A-1. 投稿用のXアカウントを用意する

サイト専用のアカウントを新しく作るのがおすすめです(例:「予約開始レーダー|ホビー新着予約速報」)。
**電話番号の認証を済ませておいてください**(開発者登録に必要な場合があります)。

### A-2. 開発者登録をする(無料)

1. 投稿したいアカウントでXにログインした状態で **developer.x.com**(X Developer Portal)を開く
2. 「Sign up for Free Account」など**無料プラン(Free)**で登録を進める
3. 利用目的を英語で書く欄が出たら、次をコピペでOK:
   `I will post a daily summary of trending products from my own website to my own account, once per day, using the official API.`
4. 登録が完了するとダッシュボードに **Project と App** が自動で1つ作られます

### A-3. アプリに「書き込み権限」をつける

ここが一番間違えやすいポイントです。

1. ダッシュボードで自分のApp(アプリ)を開く
2. 「**Settings**」タブ →「**User authentication settings**」の「**Set up**」(または Edit)をクリック
3. 次のように設定:
   - App permissions: **Read and write** ← 必ずこれ
   - Type of App: **Web App, Automated App or Bot**
   - Callback URI / Website URL: あなたのサイトURL(`https://〜.github.io/imaure/`)を両方に入力
4. 「Save」をクリック(Client ID等が表示されますが、今回は使わないので閉じてOK)

### A-4. 4つのキーを発行してメモする

1. Appの「**Keys and tokens**」タブを開く
2. **API Key and Secret** の「Regenerate」(または Generate)をクリック
   → 表示された2つをメモ:
   - **API Key**(キー1)
   - **API Key Secret**(キー2)
3. 同じページの **Access Token and Secret** の「Generate」(すでにあれば **Regenerate**)をクリック
   → 表示された2つをメモ:
   - **Access Token**(キー3)
   - **Access Token Secret**(キー4)

> ⚠ 重要:A-3の権限変更を**した後に** Access Token を発行(Regenerate)してください。
> 権限変更前のトークンだと「Read-only」のままで投稿に失敗します。
> Access Tokenの近くに「Created with **Read and Write** permissions」と表示されていれば正解です。

### A-5. GitHubに4つのキーを登録する

リポジトリの「Settings」→「Secrets and variables」→「Actions」→「New repository secret」で、以下の4つを登録します(楽天のときと同じ手順です)。

| Name(この通り正確に) | Secret(貼り付ける値) |
|---|---|
| `X_API_KEY` | キー1(API Key) |
| `X_API_SECRET` | キー2(API Key Secret) |
| `X_ACCESS_TOKEN` | キー3(Access Token) |
| `X_ACCESS_SECRET` | キー4(Access Token Secret) |

これでXの設定は完了です。

---

## パートB:Threadsの設定

### B-1. 前提

- Threadsのアカウント(Instagramアカウントに紐づくもの)を用意。サイト専用の新規アカウント推奨
- Threadsの**プロフィールを公開(非公開でない)**にしておく

### B-2. Meta開発者アプリを作る(無料)

1. **developers.facebook.com** を開き、Facebookアカウントでログイン(なければ無料登録)
2. 右上「マイアプリ」→「**アプリを作成**」
3. ユースケース選択で「**Threads APIにアクセス**(Access the Threads API)」を選ぶ
4. アプリ名(例: `imaure-bot`)を入れて作成

### B-3. 自分をテスト利用者として追加する

1. 作ったアプリの管理画面 → 左メニュー「**アプリの役割(App Roles)**」→「**役割(Roles)**」
2. 「**ユーザーを追加**」→「**Threadsテスト利用者(Threads Tester)**」を選び、自分のThreadsユーザー名を入力して招待
3. **Threadsアプリ(スマホ)側で承認**:
   Threadsの「設定」→「アカウント」→「ウェブサイトのアクセス許可」→「招待」→ 承認する

### B-4. アクセストークンを発行する

1. アプリ管理画面の左メニュー「**ユースケース**」→ Threads API の「**カスタマイズ**」→「**設定**」
2. 権限(アクセス許可)で **threads_basic** と **threads_content_publish** を有効にする
3. 同じ画面にある「**アクセストークンを生成**(Generate access token)」ボタンをクリック
   → 自分のThreadsアカウントでログイン・許可すると、**長い文字列のトークン**が表示されます
4. これをコピー(これが **Threadsのキー** です)

### B-5. GitHubにキーを登録する

| Name(この通り正確に) | Secret |
|---|---|
| `THREADS_ACCESS_TOKEN` | B-4でコピーしたトークン |

> ⏰ **注意:Threadsのトークンは約60日で期限切れになります。**
> 投稿が止まったら(Actionsに「トークン期限切れの可能性」と出ます)、B-4の手順でトークンを再発行して、GitHubのSecretを上書き(Secret名をクリック→Update)してください。作業3分です。
> カレンダーに「2ヶ月ごと:Threadsトークン更新」と入れておくのがおすすめです。

---

## 共通:サイトURLを投稿に載せる

投稿文の最後にサイトへのリンクを入れるため、Secretをもう1つ登録します。

| Name | Secret |
|---|---|
| `SITE_URL` | `https://あなたのユーザー名.github.io/imaure/` |

(これが**収益の入口**になるリンクです。忘れずに!)

---

## テスト実行する

1. リポジトリの「**Actions**」タブ →「サイトを毎日自動更新」→「**Run workflow**」
2. 実行ログの「**SNSに自動投稿**」を開くと、投稿文と結果が表示されます
   - `X: 投稿しました → id ...` / `Threads: 投稿しました → id ...` と出れば成功🎉
3. 実際にX・Threadsのアカウントを開いて投稿を確認

これで明日から毎朝6時、**サイト更新 → X投稿 → Threads投稿** がすべて自動で回ります。

---

## 投稿される内容(自動生成)

```
【6/11】楽天で“いま売れてる”TOP3🛒
🥇 商品名…(5,980円)
🥈 商品名…(2,980円)
🥉 商品名…(1,690円)
👇全ジャンルのランキング(15分ごと監視)
https://あなたのサイトURL
#楽天 #売れ筋ランキング
```

- 冒頭の言い回しと締めの一文は**日替わりで自動的に変わります**(毎日同一文面によるスパム判定を防ぐため)
- Xは文字数制限(日本語約140字)に収まるよう商品名を自動で短縮します

カスタマイズしたい場合は `post_sns.py` の上の方にある `HEADERS`(書き出し)と `FOOTERS`(締め)のリストを書き換えるだけです。

---

## ❓ トラブルシューティング

| 症状 | 対処 |
|---|---|
| X: 403エラー(Forbidden) | A-3の権限が「Read and write」になっているか確認 → なっていたら **Access Tokenを再発行**(権限変更前のトークンは使えません)→ GitHubのSecretを上書き |
| X: 401エラー | 4つのキーのどれかが間違っています。コピペし直し(前後の空白に注意) |
| X: 429エラー | 投稿しすぎ(無料枠の上限)。1日1回なら通常起きません。翌日に回復します |
| Threads: 401/403エラー | トークン期限切れ。B-4で再発行 → Secret上書き |
| 「デモデータのため投稿しません」 | 楽天APIキー(`RAKUTEN_APP_ID`)が未設定です。説明書①のステップ③へ |
| 投稿文にURLが無い | Secret `SITE_URL` を登録したか確認 |

---

## 運用上の注意

- **投稿頻度は1日1回のまま**にしてください。自動投稿の頻度を上げすぎると、X・Threads両方でスパム判定のリスクが上がります(規約上、過度な自動投稿は禁止されています)
- 自動投稿だけに任せず、**週に何回かは手動で「人間のひとこと」を投稿**すると、アカウントが伸びやすく、凍結リスクも下がります(例:1位の商品への感想、セール情報)
- フォロワーとのリプライのやり取りは自動化しないでください(規約違反のリスクが高い領域です)
