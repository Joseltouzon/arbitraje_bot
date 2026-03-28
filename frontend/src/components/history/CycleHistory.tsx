import { useState, useEffect } from 'react';
import { fetchCycleHistory } from '../../lib/api';
import { formatPct, formatTime } from '../../lib/utils';
import type { HistoryCycle } from '../../types';

export function CycleHistory() {
  const [cycles, setCycles] = useState<HistoryCycle[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetchCycleHistory(50);
        setCycles(res.cycles || []);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <h3 className="text-white font-semibold mb-4">Cycle History</h3>
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-white font-semibold">Cycle History</h3>
        <span className="text-gray-400 text-sm">{cycles.length} cycles</span>
      </div>

      {cycles.length === 0 ? (
        <p className="text-gray-500 text-center py-6">
          No cycles recorded yet. Cycles are saved to the database as they are
          detected.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-left border-b border-gray-700">
                <th className="pb-2 pr-3">#</th>
                <th className="pb-2 pr-3">Cycle</th>
                <th className="pb-2 pr-3">Profit %</th>
                <th className="pb-2 pr-3">Profit USDT</th>
                <th className="pb-2">Detected</th>
              </tr>
            </thead>
            <tbody>
              {cycles.map((cycle) => (
                <tr
                  key={cycle.id}
                  className="border-b border-gray-700/50 hover:bg-gray-700/30"
                >
                  <td className="py-2 pr-3 text-gray-500">{cycle.id}</td>
                  <td className="py-2 pr-3 text-white font-mono">
                    {cycle.currencies.join(' → ')}
                  </td>
                  <td
                    className={`py-2 pr-3 font-mono ${
                      cycle.net_profit_pct > 0
                        ? 'text-green-400'
                        : 'text-red-400'
                    }`}
                  >
                    {formatPct(cycle.net_profit_pct)}
                  </td>
                  <td className="py-2 pr-3 text-gray-300 font-mono">
                    ${cycle.net_profit_usdt?.toFixed(6) || '0.00'}
                  </td>
                  <td className="py-2 text-gray-400">
                    {formatTime(cycle.detected_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
