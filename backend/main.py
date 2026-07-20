from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from collections import defaultdict
import json
import os
from pathlib import Path
from typing import Optional

# CoinGecko Demo API key（無料登録で取得可能）
# https://www.coingecko.com/en/developers/dashboard
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "")

app = FastAPI(title="BTC Accumulation Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_FILE = CACHE_DIR / "bitcoin_market_chart_jpy.json"
CACHE_TTL_SEC = 6 * 3600  # 6時間


# ---------- キャッシュ ----------

def _load_cache() -> tuple[list | None, bool]:
    if not CACHE_FILE.exists():
        return None, False
    with open(CACHE_FILE, "r") as f:
        data = json.load(f)
    age = datetime.now().timestamp() - data["cached_at"]
    if age < CACHE_TTL_SEC:
        return data["prices"], True
    return data["prices"], False  # 期限切れでも値は返す（フォールバック用）


def _save_cache(prices: list) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump({"cached_at": datetime.now().timestamp(), "prices": prices}, f)


async def _fetch_prices() -> tuple[list, bool]:
    """CoinGecko から取得。失敗時はキャッシュにフォールバック。"""
    cached_prices, fresh = _load_cache()
    if fresh:
        return cached_prices, True

    try:
        headers: dict[str, str] = {"Accept": "application/json"}
        if COINGECKO_API_KEY:
            headers["x-cg-demo-api-key"] = COINGECKO_API_KEY
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
                params={"vs_currency": "jpy", "days": "max"},
                headers=headers,
            )
            resp.raise_for_status()
            prices = resp.json()["prices"]
            _save_cache(prices)
            return prices, False
    except Exception as exc:
        if cached_prices is not None:
            # CoinGecko 障害時はキャッシュで継続
            return cached_prices, True
        hint = ""
        if not COINGECKO_API_KEY and "401" in str(exc):
            hint = " — 環境変数 COINGECKO_API_KEY を設定してください（https://www.coingecko.com/en/developers/dashboard で無料取得）"
        raise HTTPException(status_code=503, detail=f"CoinGecko API エラー（キャッシュなし）: {exc}{hint}")


# ---------- JST 9:00 価格抽出 ----------

def _extract_jst9_prices(raw_prices: list) -> dict[date, float]:
    """
    90日より前: 日次データ (UTC 00:00 ≒ JST 09:00)
    90日以内 : 時間足データ — 各JST日の09:00に最も近い価格を採用
    """
    now_jst = datetime.now(JST)
    today_jst = now_jst.date()
    threshold_dt = now_jst - timedelta(days=90)

    by_date: dict[date, list[tuple[datetime, float]]] = defaultdict(list)
    for ts_ms, price in raw_prices:
        dt_jst = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).astimezone(JST)
        d = dt_jst.date()
        if d >= today_jst:
            continue
        by_date[d].append((dt_jst, price))

    result: dict[date, float] = {}
    for d, entries in by_date.items():
        target = datetime(d.year, d.month, d.day, 9, 0, 0, tzinfo=JST)
        is_recent = datetime(d.year, d.month, d.day, tzinfo=JST) >= threshold_dt

        if is_recent:
            within_30 = [e for e in entries if abs((e[0] - target).total_seconds()) <= 1800]
            pool = within_30 if within_30 else entries
        else:
            pool = entries

        closest = min(pool, key=lambda e: abs((e[0] - target).total_seconds()))
        result[d] = closest[1]

    return result


# ---------- 乖離率推定 ----------

def _estimate_deviation(
    sorted_dates: list[date],
    daily_prices: dict[date, float],
    daily_amount: float,
    actual_btc: float,
) -> float:
    """
    二分探索 (50回) で simulated_btc ≒ actual_btc となる rate を求める。
    effective_price = price * (1 + rate)
    返り値: 百分率 (%)
    """
    lo, hi = 0.0, 0.1

    for _ in range(50):
        mid = (lo + hi) / 2
        sim = sum(daily_amount / (daily_prices[d] * (1 + mid)) for d in sorted_dates)
        if sim > actual_btc:
            lo = mid  # rate が低すぎ → 上げる
        else:
            hi = mid  # rate が高すぎ → 下げる

    return (lo + hi) / 2 * 100


# ---------- エンドポイント ----------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/simulate")
async def simulate(
    start_date: str = Query("2021-10-25", description="YYYY-MM-DD (JST)"),
    daily_amount: float = Query(500, gt=0, description="1日の積立金額（円）"),
    actual_btc: Optional[float] = Query(None, gt=0, description="実際の保有BTC量"),
):
    raw_prices, cached = await _fetch_prices()
    daily_prices = _extract_jst9_prices(raw_prices)

    try:
        start = date.fromisoformat(start_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid start_date format")

    sorted_dates = sorted(d for d in daily_prices if d >= start)
    if not sorted_dates:
        raise HTTPException(status_code=404, detail="No price data for the specified period")

    # 日次シミュレーション
    cum_inv = 0.0
    cum_btc = 0.0
    history = []

    for d in sorted_dates:
        price = daily_prices[d]
        bought = daily_amount / price
        cum_inv += daily_amount
        cum_btc += bought

        history.append({
            "date": d.isoformat(),
            "purchase_price": round(price),
            "purchased_btc": round(bought, 8),
            "cumulative_btc": round(cum_btc, 8),
            "cumulative_investment": round(cum_inv),
            "historical_value": round(cum_btc * price),
        })

    latest_price = daily_prices[sorted_dates[-1]]
    latest_date_str = sorted_dates[-1].isoformat()
    current_value = cum_btc * latest_price
    profit = current_value - cum_inv
    profit_rate = profit / cum_inv * 100 if cum_inv > 0 else 0.0

    dev_rate: Optional[float] = None
    if actual_btc is not None:
        dev_rate = round(
            _estimate_deviation(sorted_dates, daily_prices, daily_amount, actual_btc), 2
        )

    summary = {
        "cumulative_investment": round(cum_inv),
        "current_value": round(current_value),
        "profit": round(profit),
        "profit_rate": round(profit_rate, 2),
        "latest_price": round(latest_price),
        "latest_date": latest_date_str,
        "theoretical_btc": round(cum_btc, 8),
        "actual_btc": actual_btc,
        "btc_diff": round(actual_btc - cum_btc, 8) if actual_btc is not None else None,
        "btc_diff_jpy": round((actual_btc - cum_btc) * latest_price) if actual_btc is not None else None,
        "estimated_deviation_rate": dev_rate,
    }

    return {"summary": summary, "history": history, "cached": cached}
