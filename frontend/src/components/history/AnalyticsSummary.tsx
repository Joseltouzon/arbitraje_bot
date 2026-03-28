import { useState, useEffect } from 'react';
import { fetchAnalyticsSummary } from '../../lib/api';
import { formatPct, formatUsdt } from '../../lib/utils';
import type { AnalyticsSummary } from '../../types';

export function AnalyticsSummary() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchAnalyticsSummary();
        setSummary(data);
      } catch {
        // ignore
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  if (!summary) return null;

  const stats = [
    {
      label: 'Total Cycles',
      value: summary.total_cycles_detected.toString(),
      color: 'text-blue-400',
    },
    {
      label: 'Trades Executed',
      value: summary.total_trades_executed.toString(),
      color: 'text-purple-400',
    },
    {
      label: 'Best Profit',
      value: formatPct(summary.best_profit_pct),
      color: 'text-green-400',
    },
    {
      label: 'Avg Profit',
      value: formatPct(summary.avg_profit_pct),
      color: 'text-green-300',
    },
    {
      label: 'Total P&L',
      value: formatUsdt(summary.total_profit_usdt),
      color: summary.total_profit_usdt >= 0 ? 'text-green-400' : 'text-red-400',
    },
    {
      label: 'Success Rate',
      value: `${summary.success_rate.toFixed(1)}%`,
      color: 'text-yellow-400',
    },
  ];

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-4">Performance Analytics</h3>
      <div className="grid grid-cols-3 gap-3">
        {stats.map((stat) => (
          <div key={stat.label} className="bg-gray-900/50 rounded p-3">
            <p className="text-gray-500 text-xs">{stat.label}</p>
            <p className={`text-lg font-bold font-mono ${stat.color}`}>
              {stat.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
