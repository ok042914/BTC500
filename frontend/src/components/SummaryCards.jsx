function fmt(n) {
  if (n == null) return "—";
  return Math.round(n).toLocaleString("ja-JP");
}

function fmtBtc(n) {
  if (n == null) return "—";
  return n.toFixed(8);
}

function fmtPct(n) {
  if (n == null) return "—";
  return n.toFixed(2) + "%";
}

function Card({ label, value, sub, highlight, warn }) {
  return (
    <div
      className={`rounded-2xl p-4 shadow-sm border ${
        highlight
          ? "bg-[#FF6B6B] border-[#FF6B6B] text-white"
          : "bg-white border-gray-100 text-gray-800"
      }`}
    >
      <div className={`text-xs font-semibold mb-1 ${highlight ? "text-white/80" : "text-gray-500"}`}>
        {label}
      </div>
      <div className={`text-xl font-bold leading-tight ${warn ? "text-orange-500" : ""}`}>
        {value}
      </div>
      {sub && (
        <div className={`text-xs mt-0.5 ${highlight ? "text-white/70" : "text-gray-400"}`}>{sub}</div>
      )}
    </div>
  );
}

export default function SummaryCards({ summary }) {
  if (!summary) return null;

  const {
    cumulative_investment,
    current_value,
    profit,
    profit_rate,
    latest_price,
    latest_date,
    theoretical_btc,
    actual_btc,
    btc_diff,
    btc_diff_jpy,
    estimated_deviation_rate,
  } = summary;

  const isProfit = profit >= 0;

  return (
    <div className="mb-5 space-y-3">
      {/* メインカード */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card label="投資元本" value={`¥${fmt(cumulative_investment)}`} />
        <Card label="現在評価額" value={`¥${fmt(current_value)}`} highlight />
        <Card
          label="損益額"
          value={`${isProfit ? "+" : ""}¥${fmt(profit)}`}
          warn={!isProfit}
        />
        <Card
          label="損益率"
          value={`${isProfit ? "+" : ""}${fmtPct(profit_rate)}`}
          warn={!isProfit}
        />
      </div>

      {/* BTC価格 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Card
          label="最新BTC価格（JST 9:00基準）"
          value={`¥${fmt(latest_price)}`}
          sub={`データ日付: ${latest_date}`}
        />
        <Card label="理論累計BTC量" value={`${fmtBtc(theoretical_btc)} BTC`} />
      </div>

      {/* 乖離率カード（実際BTC入力時のみ） */}
      {actual_btc != null && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
          <div className="text-xs font-bold text-amber-700 mb-3">推定価格乖離率の分析</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <div className="text-xs text-amber-600 font-semibold mb-0.5">理論BTC</div>
              <div className="font-bold text-sm">{fmtBtc(theoretical_btc)}</div>
            </div>
            <div>
              <div className="text-xs text-amber-600 font-semibold mb-0.5">実際の保有BTC</div>
              <div className="font-bold text-sm">{fmtBtc(actual_btc)}</div>
            </div>
            <div>
              <div className="text-xs text-amber-600 font-semibold mb-0.5">差分BTC</div>
              <div className={`font-bold text-sm ${btc_diff < 0 ? "text-red-500" : "text-green-600"}`}>
                {btc_diff >= 0 ? "+" : ""}{fmtBtc(btc_diff)}
              </div>
            </div>
            <div>
              <div className="text-xs text-amber-600 font-semibold mb-0.5">差分金額（現在価格換算）</div>
              <div className={`font-bold text-sm ${btc_diff_jpy < 0 ? "text-red-500" : "text-green-600"}`}>
                {btc_diff_jpy >= 0 ? "+" : ""}¥{fmt(btc_diff_jpy)}
              </div>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-amber-200 flex items-center gap-3">
            <div className="text-xs text-amber-600 font-semibold">推定価格乖離率</div>
            <div className="text-2xl font-black text-amber-800">
              {estimated_deviation_rate != null ? fmtPct(estimated_deviation_rate) : "—"}
            </div>
            <div className="text-xs text-amber-500 leading-tight">
              手数料・スプレッド・時刻差・端数処理を含む目安値
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
