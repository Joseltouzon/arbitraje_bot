import type { TriangularCycle } from '../../types';
import { formatRate } from '../../lib/utils';

interface CycleDetailProps {
  cycle: TriangularCycle;
}

export function CycleDetail({ cycle }: CycleDetailProps) {
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-5 mt-2">
      <h3 className="text-white font-semibold mb-3">Cycle Breakdown</h3>

      <div className="space-y-3">
        {cycle.legs.map((leg, idx) => (
          <div
            key={idx}
            className="flex items-center gap-3 bg-gray-800 rounded-lg p-3"
          >
            <span className="text-gray-500 w-6 text-center">{idx + 1}</span>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-white font-medium">
                  {leg.from_currency}
                </span>
                <span className="text-gray-500">→</span>
                <span className="text-white font-medium">
                  {leg.to_currency}
                </span>
              </div>
              <div className="text-sm text-gray-400 mt-1">
                {leg.pair} •{' '}
                <span
                  className={
                    leg.side === 'buy' ? 'text-green-400' : 'text-red-400'
                  }
                >
                  {leg.side.toUpperCase()}
                </span>
              </div>
            </div>
            <div className="text-right">
              <div className="text-white font-mono text-sm">
                {formatRate(leg.rate)}
              </div>
              {leg.bid > 0 && leg.ask > 0 && (
                <div className="text-xs text-gray-500 mt-1">
                  bid: {leg.bid} ask: {leg.ask}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {cycle.calculated && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <h4 className="text-gray-400 text-sm mb-2">Profit Breakdown</h4>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-800 rounded p-3">
              <span className="text-gray-500 text-xs">Initial</span>
              <p className="text-white font-mono">
                ${cycle.calculated.initial_amount.toFixed(2)} USDT
              </p>
            </div>
            <div className="bg-gray-800 rounded p-3">
              <span className="text-gray-500 text-xs">Final</span>
              <p className="text-white font-mono">
                ${cycle.calculated.final_amount.toFixed(6)} USDT
              </p>
            </div>
            <div className="bg-gray-800 rounded p-3">
              <span className="text-gray-500 text-xs">Total Fees</span>
              <p className="text-red-400 font-mono">
                ${cycle.calculated.total_fees.toFixed(6)}
              </p>
            </div>
            <div className="bg-gray-800 rounded p-3">
              <span className="text-gray-500 text-xs">Slippage Cost</span>
              <p className="text-red-400 font-mono">
                ${cycle.calculated.total_slippage.toFixed(6)}
              </p>
            </div>
          </div>
          <div className="mt-3 bg-gray-800 rounded p-3 flex justify-between items-center">
            <span className="text-gray-400">Net Profit</span>
            <div className="text-right">
              <span
                className={`font-bold text-lg ${
                  cycle.calculated.net_profit > 0
                    ? 'text-green-400'
                    : 'text-red-400'
                }`}
              >
                ${cycle.calculated.net_profit.toFixed(6)}
              </span>
              <span className="text-gray-400 ml-2 text-sm">
                ({cycle.calculated.net_profit_pct.toFixed(4)}%)
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
