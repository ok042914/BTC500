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


def _build_headers() -> dict[str, str]:
    api_key = os.environ.get("COINGECKO_API_KEY", "").strip()
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        if api_key.startswith("CG-"):
            headers["x-cg-demo-api-key"] = api_key
        else:
            headers["x-cg-pro-api-key"] = api_key
    return headers


async def _fetch_chunked(client: httpx.AsyncClient) -> list:
    """Demo プラン向け: 360日ごとに並列リクエストして全期間を取得"""
    # 2020-01-01 から現在まで取得（実用的な開始日をすべてカバー）
    chunk_start = datetime(2020, 1, 1, tzinfo=UTC)
    now = datetime.now(UTC)

    chunks: list[tuple[datetime, datetime]] = []
    cur = chunk_start
    while cur < now:
        chunk_end = min(cur + timedelta(days=360), now)
        chunks.append((cur, chunk_end))
        cur = chunk_end + timedelta(seconds=1)

    headers = _build_headers()

    async def _fetch_one(s: datetime, e: datetime) -> list:
        try:
            r = await client.get(
                "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range",
                params={"vs_currency": "jpy", "from": int(s.timestamp()), "to": int(e.timestamp())},
                headers=headers,
            )
            if r.status_code == 200:
                return r.json().get("prices", [])
        except Exception:
            pass
        return []

    results = await asyncio.gather(*[_fetch_one(s, e) for s, e in chunks])

    all_prices: list = []
    for chunk_prices in results:
        all_prices.extend(chunk_prices)
    all_prices.sort(key=lambda x: x[0])
    return all_prices


async def _fetch_prices() -> tuple[list, bool]:
    cached_prices, fresh = _load_cache()
    if fresh:
        return cached_prices, True

    headers = _build_headers()

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            # まず days=max を試す（Pro プランや旧来の公開 API で有効）
            resp = await client.get(
                "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
                params={"vs_currency": "jpy", "days": "max"},
                headers=headers,
            )
            if resp.status_code == 200:
                prices = resp.json()["prices"]
                _save_cache(prices)
                return prices, False

            if resp.status_code in (401, 403):
                # Demo プランは days=max 非対応 → 360日チャンクで並列取得
                prices = await _fetch_chunked(client)
                if prices:
                    _save_cache(prices)
                    return prices, False

            resp.raise_for_status()

    except HTTPException:
        raise
    except Exception as exc:
        if cached_prices is not None:
            return cached_prices, True
        api_key = os.environ.get("COINGECKO_API_KEY", "").strip()
        hint = ""
        if not api_key:
            hint = " — 環境変数 COINGECKO_API_KEY を設定してください"
        key_info = f"key_prefix={api_key[:4]}..." if api_key else "key=未設定"
        raise HTTPException(
            status_code=503,
            detail=f"CoinGecko API エラー ({key_info}): {exc}{hint}",
        )

    if cached_prices is not None:
        return cached_prices, True
    raise HTTPException(status_code=503, detail="価格データを取得できません")


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
        "key_type": "demo" if api_key.startswith("CG-") else ("pro" if api_key else "none"),
    }
    headers = _build_headers()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get("https://api.coingecko.com/api/v3/ping", headers=headers)
            result["ping_status"] = r.status_code
            result["ping_ok"] = r.status_code == 200

            r2 = await client.get(
                "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
                params={"vs_currency": "jpy", "days": "365"},
                headers=headers,
            )
            result["days_365_status"] = r2.status_code

            r3 = await client.get(
                "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
                params={"vs_currency": "jpy", "days": "max"},
                headers=headers,
            )
            result["days_max_status"] = r3.status_code
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
