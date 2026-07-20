import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const AXIS_STYLE = { fontSize: 11, fill: "#9ca3af" };

function yFmt(v) {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v;
}

function tooltipJpy(label) {
  return `¥${Math.round(label).toLocaleString("ja-JP")}`;
}

// 月単位間引き
function sampleMonthly(history) {
  if (!history?.length) return [];
  const seen = new Set();
  return history.filter((row) => {
    const ym = row.date.slice(0, 7);
    if (seen.has(ym)) return false;
    seen.add(ym);
    return true;
  });
}

// 週次間引き（90日以内向け）
function sampleWeekly(history) {
  if (!history?.length) return [];
  return history.filter((_, i) => i % 7 === 0);
}

// 全体のデータ量に応じてサンプリング方法を切り替え
function sample(history) {
  if (!history?.length) return [];
  return history.length > 120 ? sampleMonthly(history) : history;
}

function ChartCard({ title, children }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
      <div className="text-sm font-bold text-gray-600 mb-3">{title}</div>
      {children}
    </div>
  );
}

const InvestmentTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload;
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-3 shadow-md text-xs">
      <div className="font-bold text-gray-700 mb-1">{label}</div>
      <div className="text-blue-500">投資元本: ¥{Math.round(data?.cumulative_investment ?? 0).toLocaleString()}</div>
      <div className="text-[#FF6B6B]">評価額: ¥{Math.round(data?.historical_value ?? 0).toLocaleString()}</div>
      <div className={data?.historical_value >= data?.cumulative_investment ? "text-green-600" : "text-red-500"}>
        損益: ¥{Math.round((data?.historical_value ?? 0) - (data?.cumulative_investment ?? 0)).toLocaleString()}
      </div>
    </div>
  );
};

export default function Charts({ history }) {
  if (!history?.length) return null;

  const sampled = sample(history);

  return (
    <>
      <ChartCard title="① 累計投資額 vs 評価額">
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={sampled} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
            <defs>
              <linearGradient id="gradInv" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#93c5fd" stopOpacity={0.6} />
                <stop offset="95%" stopColor="#93c5fd" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="gradVal" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#FF6B6B" stopOpacity={0.6} />
                <stop offset="95%" stopColor="#FF6B6B" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={AXIS_STYLE} tickFormatter={(v) => v.slice(0, 7)} interval="preserveStartEnd" />
            <YAxis tick={AXIS_STYLE} tickFormatter={yFmt} width={55} />
            <Tooltip content={<InvestmentTooltip />} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Area
              type="monotone"
              dataKey="cumulative_investment"
              name="投資元本"
              stroke="#93c5fd"
              fill="url(#gradInv)"
              strokeWidth={2}
              dot={false}
            />
            <Area
              type="monotone"
              dataKey="historical_value"
              name="評価額"
              stroke="#FF6B6B"
              fill="url(#gradVal)"
              strokeWidth={2}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ChartCard title="② 日次購入価格の推移（JST 9:00）">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={sampled} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={AXIS_STYLE} tickFormatter={(v) => v.slice(0, 7)} interval="preserveStartEnd" />
              <YAxis tick={AXIS_STYLE} tickFormatter={yFmt} width={55} />
              <Tooltip
                formatter={(v) => [`¥${Math.round(v).toLocaleString()}`, "購入価格"]}
                labelStyle={{ fontSize: 11 }}
                contentStyle={{ fontSize: 11 }}
              />
              <Line
                type="monotone"
                dataKey="purchase_price"
                name="購入価格"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="③ 累計BTC量の推移">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={sampled} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={AXIS_STYLE} tickFormatter={(v) => v.slice(0, 7)} interval="preserveStartEnd" />
              <YAxis tick={AXIS_STYLE} tickFormatter={(v) => v.toFixed(4)} width={65} />
              <Tooltip
                formatter={(v) => [v.toFixed(8), "累計BTC"]}
                labelStyle={{ fontSize: 11 }}
                contentStyle={{ fontSize: 11 }}
              />
              <Line
                type="monotone"
                dataKey="cumulative_btc"
                name="累計BTC"
                stroke="#10b981"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </>
  );
}
