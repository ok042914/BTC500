export default function SettingsPanel({ settings, onChange }) {
  const { startDate, dailyAmount, actualBtc } = settings;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 mb-5">
      <h2 className="text-base font-bold text-gray-700 mb-4">シミュレーション設定</h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="block text-xs font-semibold text-gray-500 mb-1">開始日</label>
          <input
            type="date"
            value={startDate}
            max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => onChange({ ...settings, startDate: e.target.value })}
            className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#FF6B6B]/40"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-500 mb-1">積立金額（円/日）</label>
          <input
            type="number"
            min="1"
            value={dailyAmount}
            onChange={(e) => onChange({ ...settings, dailyAmount: Number(e.target.value) })}
            className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#FF6B6B]/40"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-500 mb-1">
            実際の保有BTC <span className="text-gray-400 font-normal">（任意）</span>
          </label>
          <input
            type="number"
            min="0"
            step="0.00000001"
            placeholder="例: 0.01234567"
            value={actualBtc ?? ""}
            onChange={(e) =>
              onChange({
                ...settings,
                actualBtc: e.target.value === "" ? null : Number(e.target.value),
              })
            }
            className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#FF6B6B]/40"
          />
        </div>
      </div>
    </div>
  );
}
