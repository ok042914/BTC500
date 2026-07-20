import asyncio
import os
from collections import defaultdict
from datetime import datetime, timedelta, date
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BTC Accumulation Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")
CACHE_TTL_SEC = 6 * 3600

# ---------- インメモリキャッシュ ----------
_mem_cache: dict = {}


def _load_cache() -> tuple[list | None, bool]:
    if "prices" not in _mem_cache:
        return None, False
    age = datetime.now().timestamp() - _mem_cache["cached_at"]
    if age < CACHE_TTL_SEC:
        return _mem_cache["prices"], True
    return _mem_cache["prices"], False


def _save_cache(prices: list) -> None:
    _mem_cache["prices"] = prices
    _mem_cache["cached_at"] = datetime.now().timestamp()


def _build_cg_headers() -> dict[str, str]:
    api_key = os.environ.get("COINGECKO_API_KEY", "").strip()
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        if api_key.startswith("CG-"):
            headers["x-cg-demo-api-key"] = api_key
        else:
            headers["x-cg-pro-api-key"] = api_key
    return headers


# ---------- データ取得 ----------

async def _fetch_yahoo(client: httpx.AsyncClient) -> list:
    """
    Yahoo Finance から BTC-JPY の全期間日足データを取得（認証不要）。
    タイムスタンプは UTC 00:00 = JST 09:00 に対応する。
    """
    r = await client.get(
        "https://query1.finance.yahoo.com/v8/finance/chart/BTC-JPY",
        params={"interval": "1d", "range": "10y"},
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; BTC500/1.0)",
            "Accept": "application/json",
        },
    )
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    return sorted(
        [[ts * 1000, price] for ts, price in zip(timestamps, closes) if price is not None],
        key=lambda x: x[0],
    )


async def _fetch_cg_recent(client: httpx.AsyncClient) -> list:
    """
    CoinGecko から直近 90 日の時間足データを取得。
    Demo プランで動作確認済み（days=90 < 365 の制限内）。
    失敗時は空リストを返す（Yahoo のみで続行）。
    """
    try:
        r = await client.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            params={"vs_currency": "jpy", "days": "90"},
            headers=_build_cg_headers(),
        )
        if r.status_code == 200:
            return r.json().get("prices", [])
    except Exception:
        pass
    return []


def _merge_prices(yahoo_prices: list, cg_prices: list) -> list:
    """
    Yahoo（日足）と CoinGecko（時間足）をマージ。
    重複タイムスタンプは CoinGecko 優先（より高精度）。
    直近 90 日は CoinGecko、それ以前は Yahoo を使う。
    """
    if not cg_prices:
        return yahoo_prices

    # CoinGecko のカバー範囲の開始タイムスタンプ
    cg_start_ms = cg_prices[0][0]

    merged = [p for p in yahoo_prices if p[0] < cg_start_ms] + cg_prices
    merged.sort(key=lambda x: x[0])
    return merged


async def _fetch_prices() -> tuple[list, bool]:
    cached_prices, fresh = _load_cache()
    if fresh:
        return cached_prices, True

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            yahoo_prices, cg_prices = await asyncio.gather(
                _fetch_yahoo(client),
                _fetch_cg_recent(client),
            )

        prices = _merge_prices(yahoo_prices, cg_prices)
        if not prices:
            raise ValueError("価格データが空です")
        _save_cache(prices)
        return prices, False

    except Exception as exc:
        if cached_prices is not None:
            return cached_prices, True
        raise HTTPException(
            status_code=503,
            detail=f"価格データ取得エラー: {exc}",
        )


# ---------- JST 9:00 価格抽出 ----------

def _extract_jst9_prices(raw_prices: list) -> dict[date, float]:
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


# ---------- 推定価格乖離率（二分探索） ----------

def _estimate_deviation(
    sorted_dates: list[date],
    daily_prices: dict[date, float],
    daily_amount: float,
    actual_btc: float,
) -> float:
    lo, hi = 0.0, 0.1
    for _ in range(50):
        mid = (lo + hi) / 2
        sim = sum(daily_amount / (daily_prices[d] * (1 + mid)) for d in sorted_dates)
        if sim > actual_btc:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2 * 100


# ---------- エンドポイント ----------

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/check-key")
async def check_key():
    api_key = os.environ.get("COINGECKO_API_KEY", "").strip()
    result: dict = {
        "key_set": bool(api_key),
        "key_prefix": api_key[:6] + "..." if api_key else "(未設定)",
        "data_source": "Yahoo Finance (historical) + CoinGecko 90d (recent)",
    }
    headers = _build_cg_headers()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            yf_r = await client.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/BTC-JPY",
                params={"interval": "1d", "range": "1mo"},
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            )
            result["yahoo_status"] = yf_r.status_code
            result["yahoo_ok"] = yf_r.status_code == 200

            cg_r = await client.get(
                "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
                params={"vs_currency": "jpy", "days": "90"},
                headers=headers,
            )
            result["coingecko_90d_status"] = cg_r.status_code
            result["coingecko_90d_ok"] = cg_r.status_code == 200
    except Exception as e:
        result["error"] = str(e)
    return result


@app.get("/api/simulate")
async def simulate(
    start_date: str = Query("2021-10-25"),
    daily_amount: float = Query(500, gt=0),
    actual_btc: Optional[float] = Query(None, gt=0),
):
    raw_prices, cached = await _fetch_prices()
    daily_prices = _extract_jst9_prices(raw_prices)

    try:
        start = date.fromisoformat(start_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid start_date")

    sorted_dates = sorted(d for d in daily_prices if d >= start)
    if not sorted_dates:
        raise HTTPException(status_code=404, detail="指定期間の価格データがありません")

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
    current_value = cum_btc * latest_price
    profit = current_value - cum_inv

    dev_rate: Optional[float] = None
    if actual_btc is not None:
        dev_rate = round(
            _estimate_deviation(sorted_dates, daily_prices, daily_amount, actual_btc), 2
        )

    return {
        "summary": {
            "cumulative_investment": round(cum_inv),
            "current_value": round(current_value),
            "profit": round(profit),
            "profit_rate": round(profit / cum_inv * 100, 2) if cum_inv > 0 else 0.0,
            "latest_price": round(latest_price),
            "latest_date": sorted_dates[-1].isoformat(),
            "theoretical_btc": round(cum_btc, 8),
            "actual_btc": actual_btc,
            "btc_diff": round(actual_btc - cum_btc, 8) if actual_btc is not None else None,
            "btc_diff_jpy": round((actual_btc - cum_btc) * latest_price) if actual_btc is not None else None,
            "estimated_deviation_rate": dev_rate,
        },
        "history": history,
        "cached": cached,
    }
