# BTC 毎朝9時積立シミュレーター

毎日JST 9:00に定額でビットコインを積立投資した場合の理論シミュレーションを行うWebアプリ。

## セットアップと起動

### 1. CoinGecko APIキーの取得（無料）

1. https://www.coingecko.com/en/developers/dashboard にアクセス
2. 「Add New Key」→ **Demo Plan** を選択
3. 発行されたキーをメモしておく

### 2. バックエンド

```bash
cd backend
pip install -r requirements.txt
COINGECKO_API_KEY=your_api_key_here python3 -m uvicorn main:app --reload
```

### フロントエンド

```bash
cd frontend
npm install
npm run dev
```

### アクセスURL

- フロントエンド: http://localhost:5173
- バックエンド API: http://localhost:8000
- API ドキュメント: http://localhost:8000/docs

## API仕様

### GET /simulate

| パラメータ | 型 | デフォルト | 説明 |
|---|---|---|---|
| start_date | string (YYYY-MM-DD) | 2021-10-25 | 積立開始日（JST） |
| daily_amount | number | 500 | 1日の積立金額（円） |
| actual_btc | number | 任意 | 実際の保有BTC量 |

### GET /health

ヘルスチェックエンドポイント。

## キャッシュ仕様

- 保存先: `backend/cache/bitcoin_market_chart_jpy.json`
- 有効期限: 6時間
- 有効期限内は外部API（CoinGecko）を呼ばない
- CoinGecko が 429/5xx を返した場合はキャッシュにフォールバック
- キャッシュ利用時はレスポンスに `cached: true` を含める

## データソース

CoinGecko Public API (`/coins/bitcoin/market_chart?vs_currency=jpy&days=max`)

### JST 9:00価格の抽出ルール

| 期間 | ルール |
|---|---|
| 90日より前 | 日次データ（UTC 00:00 = JST 09:00）をそのまま使用 |
| 90日以内 | 時間足データから各JST日の09:00に最も近い価格を採用（±30分以内を優先） |

## 推定価格乖離率の計算方法

理論BTC数量と実際の保有BTC数量の差から、等価固定乖離率を二分探索（50回）で推定する。

```
effective_price = price × (1 + rate)
simulated_btc = Σ daily_amount / effective_price
simulated_btc ≒ actual_btc となる rate を求める（0.0%〜10.0%）
```

## 制約事項・免責事項

- CoinGeckoの価格と実際の取引所価格には差異があります。
- 積立実行時刻がJST 9:00以外の場合、推定価格乖離率に誤差が生じます。
- 端数処理や積立未実行日も差分要因となります。
- 推定価格乖離率は「実際にどれだけ理論価格から乖離していたか」の目安であり、特定の手数料率を示すものではありません。
- 本アプリは理論シミュレーションであり、投資助言ではありません。
