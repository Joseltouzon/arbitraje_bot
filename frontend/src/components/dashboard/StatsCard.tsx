import { useState, useEffect } from 'react';
import { fetchHealth } from '../../lib/api';

interface StatsCardProps {
  currentCycles: number;
}

export function StatsCard({ currentCycles }: StatsCardProps) {
  const [health, setHealth] = useState<{
    scanner: { scan_count: number; tickers_loaded: number };
    spot_futures: { opportunities: number };
  } | null>(null);
  const [balance, setBalance] = useState<number | null>(null);

  useEffect(() => {
    const loadHealth = async () => {
      try {
        const h = await fetchHealth();
        setHealth(h);
      } catch { /* ignore */ }
    };
    const loadBalance = async () => {
      try {
        const res = await fetch('/api/prices/balance');
        const data = await res.json();
        setBalance(data.spot_usdt);
      } catch { /* ignore */ }
    };
    loadHealth();
    loadBalance();
    const interval = setInterval(() => { loadHealth(); loadBalance(); }, 5000);
    return () => clearInterval(interval);
  }, []);

  const s = health?.scanner;
  const sf = health?.spot_futures;

  const stats = [
    {
      label: 'Spot Balance',
      value: balance !== null ? `$${balance.toFixed(2)}` : '...',
      color: 'text-white',
    },
    {
      label: 'Scans',
      value: s ? s.scan_count.toLocaleString() : '0',
      color: 'text-blue-400',
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
        <div key={stat.label} className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          <p className="text-gray-500 text-xs uppercase tracking-wide">{stat.label}</p>
          <p className={`text-xl font-bold font-mono mt-1 ${stat.color}`}>{stat.value}</p>
        </div>
      ))}
    </div>
  );
}
