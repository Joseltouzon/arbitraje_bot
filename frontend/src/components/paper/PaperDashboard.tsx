import { formatPct, formatUsdt } from '../../lib/utils';

interface PaperTradeData {
  trade_id: number;
  currencies: string[];
  profit_usdt: number;
  profit_pct: number;
  balance: number;
}

interface PaperStats {
  enabled: boolean;
  initial_balance: number;
  current_balance: number;
  net_profit: number;
  net_profit_pct: number;
  total_trades: number;
  success_rate: number;
  total_fees_paid: number;
  consecutive_losses: number;
  avg_latency_ms: number;
}

interface PaperDashboardProps {
  stats: PaperStats | null;
  trades: PaperTradeData[];
  onToggle: (enabled: boolean) => void;
}

export function PaperDashboard({ stats, trades, onToggle }: PaperDashboardProps) {
  if (!stats) return null;

  const profitColor =
    stats.net_profit >= 0 ? 'text-green-400' : 'text-red-400';

  return (
    <div className="space-y-4">
      {/* Status Bar */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-white font-semibold">Paper Trading</h3>
          <button
            onClick={() => onToggle(!stats.enabled)}
            className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
              stats.enabled
                ? 'bg-green-600 hover:bg-green-700 text-white'
                : 'bg-gray-600 hover:bg-gray-500 text-gray-300'
            }`}
          >
            {stats.enabled ? 'Running' : 'Paused'}
          </button>
        </div>

        <div className="grid grid-cols-4 gap-4">
          <div>
            <p className="text-gray-500 text-xs">Balance</p>
            <p className="text-white font-mono text-lg">
              {formatUsdt(stats.current_balance)}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">P&L</p>
            <p className={`font-mono text-lg ${profitColor}`}>
              {formatUsdt(stats.net_profit)}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">P&L %</p>
            <p className={`font-mono text-lg ${profitColor}`}>
              {formatPct(stats.net_profit_pct)}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Trades</p>
            <p className="text-white font-mono text-lg">{stats.total_trades}</p>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-700">
          <div>
            <p className="text-gray-500 text-xs">Win Rate</p>
            <p className="text-yellow-400 font-mono">
              {stats.success_rate.toFixed(1)}%
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Total Fees</p>
            <p className="text-red-400 font-mono">
              {formatUsdt(stats.total_fees_paid)}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Streak</p>
            <p
              className={`font-mono ${
                stats.consecutive_losses > 0 ? 'text-red-400' : 'text-gray-300'
              }`}
            >
              {stats.consecutive_losses > 0
                ? `${stats.consecutive_losses} losses`
                : 'OK'}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Avg Latency</p>
            <p className="text-gray-300 font-mono">
              {stats.avg_latency_ms.toFixed(1)}ms
            </p>
          </div>
        </div>
      </div>

      {/* Recent Trades */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <h3 className="text-white font-semibold mb-3">Recent Paper Trades</h3>

        {trades.length === 0 ? (
          <p className="text-gray-500 text-center py-4">
            No paper trades yet. Enable paper trading to start.
          </p>
        ) : (
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {trades.map((trade) => (
              <div
                key={trade.trade_id}
                className="flex justify-between items-center bg-gray-900/50 rounded px-3 py-2"
              >
                <div>
                  <span className="text-white font-mono text-sm">
                    {trade.currencies.join(' → ')}
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
                    ({formatPct(trade.profit_pct)})
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
