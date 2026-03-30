import { useState, useEffect } from 'react';
import { fetchSpotFuturesStats, fetchSpotFuturesHistory } from '../../lib/api';
import { formatTime } from '../../lib/utils';

export function SpotFuturesStats() {
  const [stats, setStats] = useState<{
    opportunities: number;
    last_scan: string | null;
  } | null>(null);
  const [historyCount, setHistoryCount] = useState(0);

  useEffect(() => {
    const load = async () => {
      try {
        const [s, h] = await Promise.all([
          fetchSpotFuturesStats(),
          fetchSpotFuturesHistory(200),
        ]);
        setStats(s);
        setHistoryCount(h.count || 0);
      } catch {
        // ignore
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-3">Spot-Futures Scanner</h3>
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-900/50 rounded p-3">
          <p className="text-gray-500 text-xs">Total Detected</p>
          <p className="text-blue-400 text-lg font-bold font-mono">
            {historyCount}
          </p>
        </div>
        <div className="bg-gray-900/50 rounded p-3">
          <p className="text-gray-500 text-xs">Current Scan</p>
          <p className="text-white text-lg font-bold font-mono">
            {stats?.opportunities ?? 0}
          </p>
        </div>
        <div className="bg-gray-900/50 rounded p-3">
          <p className="text-gray-500 text-xs">Last Scan</p>
          <p className="text-gray-300 text-sm font-mono">
            {stats?.last_scan ? formatTime(stats.last_scan) : '-'}
          </p>
        </div>
      </div>
    </div>
  );
}
