import { useState, useEffect } from 'react';
import { fetchSpotFuturesStats } from '../../lib/api';

interface SFStats {
  opportunities: number;
  last_scan: string | null;
  top_opportunity: {
    symbol: string;
    premium_pct: number;
    net_profit_pct: number;
    funding_rate: number;
  } | null;
}

export function SpotFuturesStats() {
  const [stats, setStats] = useState<SFStats | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchSpotFuturesStats();
        setStats(data);
      } catch {
        // ignore
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  if (!stats) return null;

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-4">Spot-Futures Scanner</h3>
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-900/50 rounded p-3">
          <p className="text-gray-500 text-xs">Opportunities Found</p>
          <p className="text-blue-400 text-lg font-bold font-mono">
            {stats.opportunities}
          </p>
        </div>
        <div className="bg-gray-900/50 rounded p-3">
          <p className="text-gray-500 text-xs">Best Premium</p>
          <p className="text-green-400 text-lg font-bold font-mono">
            {stats.top_opportunity
              ? `${stats.top_opportunity.premium_pct.toFixed(3)}%`
              : '-'}
          </p>
        </div>
        <div className="bg-gray-900/50 rounded p-3">
          <p className="text-gray-500 text-xs">Best Symbol</p>
          <p className="text-white text-lg font-bold font-mono">
            {stats.top_opportunity?.symbol || '-'}
          </p>
        </div>
      </div>
    </div>
  );
}
