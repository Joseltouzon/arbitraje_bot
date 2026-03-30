import { useState, useEffect } from 'react';
import { fetchHealth } from '../../lib/api';

interface StatsCardProps {
  currentCycles: number;
}

export function StatsCard({ currentCycles }: StatsCardProps) {
  const [health, setHealth] = useState<{
    scanner: {
      scan_count: number;
      current_cycles: number;
      top_profit: number;
      tickers_loaded: number;
    };
    paper: {
      net_profit_pct: number;
      total_trades: number;
    };
    live: {
      total_trades: number;
      total_profit_usdt: number;
    };
    spot_futures: {
      opportunities: number;
    };
    volatility: {
      volatility_score: number;
    };
  } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchHealth();
        setHealth(data);
      } catch {
        // ignore
      }
    };
    load();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, []);

  const s = health?.scanner;
  const sf = health?.spot_futures;

  const stats = [
    {
      label: 'Scans',
      value: s ? s.scan_count.toLocaleString() : '0',
      color: 'text-blue-400',
    },
    {
      label: 'Pairs',
      value: s ? s.tickers_loaded.toString() : '0',
      color: 'text-gray-300',
    },
    {
      label: 'Triangular',
      value: currentCycles.toString(),
      color: currentCycles > 0 ? 'text-green-400' : 'text-gray-500',
    },
    {
      label: 'Spot-Futures',
      value: sf ? sf.opportunities.toString() : '0',
      color: (sf?.opportunities ?? 0) > 0 ? 'text-blue-400' : 'text-gray-500',
    },
  ];

  return (
    <div className="grid grid-cols-4 gap-3 p-4">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="bg-gray-800 border border-gray-700 rounded-lg p-4"
        >
          <p className="text-gray-500 text-xs uppercase tracking-wide">
            {stat.label}
          </p>
          <p className={`text-xl font-bold font-mono mt-1 ${stat.color}`}>
            {stat.value}
          </p>
        </div>
      ))}
    </div>
  );
}
