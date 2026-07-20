import { useState, useMemo } from "react";

const COLS = [
  { key: "date", label: "日付", fmt: (v) => v },
  { key: "purchase_price", label: "購入価格（JPY）", fmt: (v) => `¥${Math.round(v).toLocaleString()}` },
  { key: "purchased_btc", label: "購入BTC量", fmt: (v) => v.toFixed(8) },
  { key: "cumulative_btc", label: "累計BTC量", fmt: (v) => v.toFixed(8) },
  { key: "cumulative_investment", label: "累計投資額", fmt: (v) => `¥${Math.round(v).toLocaleString()}` },
  { key: "historical_value", label: "当日時点評価額", fmt: (v) => `¥${Math.round(v).toLocaleString()}` },
];

export default function DataTable({ history }) {
  const [sortKey, setSortKey] = useState("date");
  const [sortDir, setSortDir] = useState("desc");

  const sorted = useMemo(() => {
    if (!history?.length) return [];
    return [...history].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [history, sortKey, sortDir]);

  function handleSort(key) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  function downloadCsv() {
    const header = COLS.map((c) => c.label).join(",");
    const rows = (history ?? []).map((row) =>
      COLS.map((c) => {
        const v = row[c.key];
        return typeof v === "string" ? v : v;
      }).join(",")
    );
    const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "btc_simulation.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!history?.length) return null;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-5">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-bold text-gray-600">詳細テーブル（{history.length}件）</div>
        <button
          onClick={downloadCsv}
          className="text-xs bg-[#FF6B6B] text-white px-3 py-1.5 rounded-lg hover:bg-[#e85d5d] transition-colors min-h-[36px]"
        >
          CSV ダウンロード
        </button>
      </div>
      <div className="overflow-auto max-h-80">
        <table className="w-full text-xs border-collapse">
          <thead className="sticky top-0 bg-gray-50">
            <tr>
              {COLS.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  className="text-left px-3 py-2 text-gray-500 font-semibold cursor-pointer hover:text-gray-800 whitespace-nowrap border-b border-gray-100 select-none"
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span className="ml-1">{sortDir === "asc" ? "▲" : "▼"}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <tr key={row.date} className={i % 2 === 0 ? "bg-white" : "bg-gray-50/50"}>
                {COLS.map((col) => (
                  <td key={col.key} className="px-3 py-1.5 whitespace-nowrap text-gray-700">
                    {col.fmt(row[col.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
