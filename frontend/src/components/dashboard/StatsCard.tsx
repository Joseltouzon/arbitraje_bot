import type { TriangularCycle } from '../../types';
import { formatPct, formatUsdt } from '../../lib/utils';

interface StatsCardProps {
  cycles: TriangularCycle[];
}

export function StatsCard({ cycles }: StatsCardProps) {
  const totalCycles = cycles.length;
  const avgProfit =
    totalCycles > 0
      ? cycles.reduce((sum, c) => sum + c.net_profit_pct, 0) / totalCycles
      : 0;
  const bestProfit = totalCycles > 0 ? cycles[0].net_profit_pct : 0;
  const totalNetProfit =
    totalCycles > 0
      ? cycles.reduce((sum, c) => sum + (c.calculated?.net_profit ?? 0), 0)
      : 0;

  const stats = [
    {
      label: 'Cycles Found',
      value: totalCycles.toString(),
      color: 'text-blue-400',
    },
    {
      label: 'Best Profit',
      value: formatPct(bestProfit),
      color: 'text-green-400',
    },
    {
      label: 'Avg Profit',
      value: formatPct(avgProfit),
      color: 'text-green-300',
    },
    {
      label: 'Potential',
      value: formatUsdt(totalNetProfit),
      color: 'text-yellow-400',
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
