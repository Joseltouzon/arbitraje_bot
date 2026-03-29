import { formatPct } from '../../lib/utils';

interface SpotFuturesData {
  symbol: string;
  spot_price: number;
  futures_price: number;
  premium_pct: number;
  net_profit_pct: number;
  direction: string;
  funding_rate: number;
}

interface SpotFuturesFeedProps {
  opportunities: SpotFuturesData[];
}

export function SpotFuturesFeed({ opportunities }: SpotFuturesFeedProps) {
  if (opportunities.length === 0) {
    return (
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <h3 className="text-white font-semibold mb-2">
          Spot-Futures Premium
        </h3>
        <p className="text-gray-500 text-sm">
          No premium opportunities detected.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-3">
        Spot-Futures Opportunities
      </h3>
      <div className="space-y-2">
        {opportunities.map((opp, idx) => (
          <div
            key={idx}
            className="bg-gray-900/50 rounded px-3 py-2 flex justify-between items-center"
          >
            <div>
              <span className="text-white font-mono font-medium">
                {opp.symbol}
              </span>
              <span
                className={`ml-2 text-xs px-2 py-0.5 rounded ${
                  opp.direction === 'futures_premium'
                    ? 'bg-green-900/50 text-green-300'
                    : 'bg-red-900/50 text-red-300'
                }`}
              >
                {opp.direction === 'futures_premium' ? 'Premium' : 'Discount'}
              </span>
            </div>
            <div className="text-right">
              <span
                className={`font-mono font-medium ${
                  opp.net_profit_pct > 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {formatPct(opp.net_profit_pct)}
              </span>
              <span className="text-gray-500 ml-2 text-xs">
                spot: ${opp.spot_price.toLocaleString()} / futures: $
                {opp.futures_price.toLocaleString()}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
