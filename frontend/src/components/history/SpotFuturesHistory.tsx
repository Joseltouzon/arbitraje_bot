import { useState, useEffect } from 'react';
import { fetchSpotFuturesHistory } from '../../lib/api';
import { formatPct, formatTime } from '../../lib/utils';

interface SpotFuturesRecord {
  id: number;
  symbol: string;
  spot_price: number;
  futures_price: number;
  premium_pct: number;
  net_profit_pct: number;
  direction: string;
  funding_rate: number;
  detected_at: string;
}

export function SpotFuturesHistory() {
  const [records, setRecords] = useState<SpotFuturesRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetchSpotFuturesHistory(50);
        setRecords(res.records || []);
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
        <h3 className="text-white font-semibold mb-4">Spot-Futures History</h3>
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-white font-semibold">Spot-Futures History</h3>
        <span className="text-gray-400 text-sm">{records.length} records</span>
      </div>

      {records.length === 0 ? (
        <p className="text-gray-500 text-center py-6">
          No spot-futures opportunities recorded yet.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-left border-b border-gray-700">
                <th className="pb-2 pr-3">#</th>
                <th className="pb-2 pr-3">Symbol</th>
                <th className="pb-2 pr-3">Spot</th>
                <th className="pb-2 pr-3">Futures</th>
                <th className="pb-2 pr-3">Premium</th>
                <th className="pb-2 pr-3">Net Profit</th>
                <th className="pb-2 pr-3">Funding</th>
                <th className="pb-2">Detected</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-gray-700/50 hover:bg-gray-700/30"
                >
                  <td className="py-2 pr-3 text-gray-500">{r.id}</td>
                  <td className="py-2 pr-3 text-white font-mono font-medium">
                    {r.symbol}
                  </td>
                  <td className="py-2 pr-3 text-gray-300 font-mono">
                    ${r.spot_price.toLocaleString()}
                  </td>
                  <td className="py-2 pr-3 text-gray-300 font-mono">
                    ${r.futures_price.toLocaleString()}
                  </td>
                  <td
                    className={`py-2 pr-3 font-mono ${
                      r.premium_pct > 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {formatPct(r.premium_pct)}
                  </td>
                  <td
                    className={`py-2 pr-3 font-mono ${
                      r.net_profit_pct > 0
                        ? 'text-green-400'
                        : 'text-red-400'
                    }`}
                  >
                    {formatPct(r.net_profit_pct)}
                  </td>
                  <td className="py-2 pr-3 text-gray-400 font-mono">
                    {(r.funding_rate * 100).toFixed(4)}%
                  </td>
                  <td className="py-2 text-gray-400">
                    {formatTime(r.detected_at)}
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
