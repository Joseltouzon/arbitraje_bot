import { formatUsdt } from '../../lib/utils';

interface LiveStats {
  enabled: boolean;
  confirmed: boolean;
  total_trades: number;
  profitable_trades: number;
  failed_trades: number;
  partial_trades: number;
  success_rate: number;
  total_profit_usdt: number;
  total_fees_usdt: number;
  risk: {
    paused: boolean;
    consecutive_losses: number;
    daily_pnl: number;
  };
}

interface LiveTrade {
  id: number;
  currencies: string[];
  profit_usdt: number;
  profit_pct: number;
  status: string;
  duration_ms: number;
}

interface LiveDashboardProps {
  stats: LiveStats | null;
  trades: LiveTrade[];
  onPause: () => void;
  onResume: () => void;
  onDisable: () => void;
}

export function LiveDashboard({
  stats,
  trades,
  onPause,
  onResume,
  onDisable,
}: LiveDashboardProps) {
  if (!stats) return null;

  const profitColor =
    stats.total_profit_usdt >= 0 ? 'text-green-400' : 'text-red-400';

  return (
    <div className="space-y-4">
      {/* Status & Controls */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-white font-semibold">Live Trading</h3>
          <div className="flex gap-2">
            {stats.risk.paused ? (
              <button
                onClick={onResume}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded text-sm"
              >
                Resume
              </button>
            ) : (
              <button
                onClick={onPause}
                className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded text-sm"
              >
                Pause
              </button>
            )}
            <button
              onClick={onDisable}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded text-sm"
            >
              Stop
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-gray-500 text-xs">State</p>
            <p
              className={`font-medium ${
                stats.risk.paused ? 'text-yellow-400' : 'text-green-400'
              }`}
            >
              {stats.risk.paused ? 'Paused' : 'Active'}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Total Trades</p>
            <p className="text-white font-mono">{stats.total_trades}</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Net P&L</p>
            <p className={`font-mono ${profitColor}`}>
              {formatUsdt(stats.total_profit_usdt)}
            </p>
          </div>
        </div>
      </div>

      {/* Stats */}
      {stats.total_trades > 0 && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          <h3 className="text-white font-semibold mb-3">Performance</h3>
          <div className="grid grid-cols-4 gap-3">
            <div>
              <p className="text-gray-500 text-xs">Win Rate</p>
              <p className="text-yellow-400 font-mono">
                {stats.success_rate.toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-gray-500 text-xs">Won</p>
              <p className="text-green-400 font-mono">
                {stats.profitable_trades}
              </p>
            </div>
            <div>
              <p className="text-gray-500 text-xs">Failed</p>
              <p className="text-red-400 font-mono">{stats.failed_trades}</p>
            </div>
            <div>
              <p className="text-gray-500 text-xs">Total Fees</p>
              <p className="text-red-400 font-mono">
                {formatUsdt(stats.total_fees_usdt)}
              </p>
            </div>
          </div>

          {stats.risk.consecutive_losses > 0 && (
            <div className="mt-3 bg-red-900/30 border border-red-800 rounded p-2 text-sm">
              <span className="text-red-400">
                Warning: {stats.risk.consecutive_losses} consecutive losses
              </span>
            </div>
          )}
        </div>
      )}

      {/* Recent Trades */}
      {trades.length > 0 && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          <h3 className="text-white font-semibold mb-3">Recent Trades</h3>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {trades.map((trade) => (
              <div
                key={trade.id}
                className="flex justify-between items-center bg-gray-900/50 rounded px-3 py-2"
              >
                <div>
                  <span className="text-white font-mono text-sm">
                    {trade.currencies.join(' → ')}
                  </span>
                  <span
                    className={`ml-2 text-xs px-2 py-0.5 rounded ${
                      trade.status === 'completed'
                        ? 'bg-green-900/50 text-green-300'
                        : trade.status === 'partial'
                          ? 'bg-yellow-900/50 text-yellow-300'
                          : 'bg-red-900/50 text-red-300'
                    }`}
                  >
                    {trade.status}
                  </span>
                </div>
                <div className="text-right">
                  <span
                    className={`font-mono font-medium ${
                      trade.profit_usdt >= 0
                        ? 'text-green-400'
                        : 'text-red-400'
                    }`}
                  >
                    {trade.profit_usdt >= 0 ? '+' : ''}
                    {formatUsdt(trade.profit_usdt)}
                  </span>
                  <span className="text-gray-500 ml-2 text-xs">
                    ({trade.duration_ms.toFixed(0)}ms)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
