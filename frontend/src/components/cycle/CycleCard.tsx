import { useState } from 'react';
import type { TriangularCycle } from '../../types';
import { formatPct, formatUsdt } from '../../lib/utils';
import { CycleDetail } from './CycleDetail';

interface CycleCardProps {
  cycle: TriangularCycle;
}

export function CycleCard({ cycle }: CycleCardProps) {
  const [expanded, setExpanded] = useState(false);

  const profitColor =
    cycle.net_profit_pct > 0.5
      ? 'text-green-400'
      : cycle.net_profit_pct > 0
        ? 'text-green-300'
        : 'text-red-400';

  const bgColor =
    cycle.net_profit_pct > 0.5
      ? 'border-green-700/50'
      : cycle.net_profit_pct > 0
        ? 'border-green-800/30'
        : 'border-red-800/30';

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className={`w-full text-left bg-gray-800 border ${bgColor} rounded-lg p-4 hover:border-gray-500 transition-colors cursor-pointer`}
      >
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center gap-2">
            <span className="text-white font-mono text-sm font-medium">
              {cycle.currencies.join(' → ')}
            </span>
            <span className="text-gray-500 text-xs">
              {cycle.legs.length} legs
            </span>
          </div>
          <div className={`font-bold text-lg ${profitColor}`}>
            {formatPct(cycle.net_profit_pct)}
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {cycle.legs.map((leg, idx) => (
            <div
              key={idx}
              className="flex items-center gap-1.5 text-sm text-gray-400 bg-gray-900/50 rounded px-2.5 py-1"
            >
              <span className="font-mono text-gray-300">{leg.pair}</span>
              <span
                className={`px-1.5 py-0.5 rounded text-xs ${
                  leg.side === 'buy'
                    ? 'bg-green-900/50 text-green-300'
                    : 'bg-red-900/50 text-red-300'
                }`}
              >
                {leg.side}
              </span>
            </div>
          ))}
        </div>

        {cycle.calculated && (
          <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Invest</span>
              <p className="text-white font-mono">
                {formatUsdt(cycle.calculated.initial_amount)}
              </p>
            </div>
            <div>
              <span className="text-gray-500">Get back</span>
              <p className="text-white font-mono">
                {formatUsdt(cycle.calculated.final_amount)}
              </p>
            </div>
            <div>
              <span className="text-gray-500">Net profit</span>
              <p className={`font-mono ${profitColor}`}>
                {formatUsdt(cycle.calculated.net_profit)}
              </p>
            </div>
          </div>
        )}

        <div className="mt-2 text-xs text-gray-600 text-right">
          {expanded ? '▲ Hide details' : '▼ Show details'}
        </div>
      </button>

      {expanded && <CycleDetail cycle={cycle} />}
    </div>
  );
}
