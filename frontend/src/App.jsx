import { useState, useEffect, useCallback } from "react";
import SettingsPanel from "./components/SettingsPanel";
import SummaryCards from "./components/SummaryCards";
import Charts from "./components/Charts";
import DataTable from "./components/DataTable";

const API_BASE = "/api";
const VERSION = "v1.0.0";
const DEPLOY_DATE = "2026-07-20";

export default function App() {
  const [settings, setSettings] = useState({
    startDate: "2021-10-25",
    dailyAmount: 500,
    actualBtc: null,
  });

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [cached, setCached] = useState(false);

  const fetchSimulation = useCallback(async (s) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        start_date: s.startDate,
        daily_amount: s.dailyAmount,
      });
      if (s.actualBtc != null && s.actualBtc > 0) {
        params.set("actual_btc", s.actualBtc);
      }
      const res = await fetch(`${API_BASE}/simulate?${params}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `HTTP ${res.status}`);
      }
      const data = await res.json();
      setResult(data);
      setCached(data.cached ?? false);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => fetchSimulation(settings), 400);
    return () => clearTimeout(t);
  }, [settings, fetchSimulation]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-[#FF6B6B] text-white px-5 py-4 shadow-sm">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-black leading-tight">₿ BTC 毎朝9時積立シミュレーター</h1>
            <p className="text-xs text-white/80 mt-0.5">JST 9:00 の価格に基づく理論シミュレーション</p>
          </div>
          {cached && (
            <span className="text-xs bg-white/20 px-2 py-1 rounded-lg">キャッシュ利用中</span>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-5">
        <SettingsPanel settings={settings} onChange={setSettings} />

        {loading && (
          <div className="text-center py-10 text-gray-400 text-sm">
            <div className="animate-pulse">データを取得中...</div>
          </div>
        )}

        {error && !loading && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-4 mb-5 text-red-700 text-sm space-y-1">
            <div><strong>エラー:</strong> {error}</div>
            {error.includes("COINGECKO_API_KEY") || error.includes("401") || error.includes("503") ? (
              <div className="text-xs text-red-600 bg-red-100 rounded-lg px-3 py-2 mt-2">
                <strong>APIキーが必要です:</strong>{" "}
                <a
                  href="https://www.coingecko.com/en/developers/dashboard"
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  CoinGecko Dashboard
                </a>{" "}
                で無料APIキーを取得し、バックエンドを{" "}
                <code className="bg-red-200 px-1 rounded">COINGECKO_API_KEY=xxx python3 -m uvicorn main:app --reload</code>{" "}
                で起動してください。
              </div>
            ) : null}
          </div>
        )}

        {!loading && result && (
          <>
            <SummaryCards summary={result.summary} />
            <Charts history={result.history} />
            <DataTable history={result.history} />
          </>
        )}
      </main>

      <footer className="text-center py-4 text-xs text-gray-400 border-t border-gray-100">
        {VERSION} &nbsp;|&nbsp; {DEPLOY_DATE} &nbsp;|&nbsp; データソース: CoinGecko &nbsp;|&nbsp;
        本アプリは理論シミュレーションであり、実際の取引結果を保証するものではありません
      </footer>
    </div>
  );
}
