import { useState, useEffect } from 'react';
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
  onStart: () => void;
  onDisable: () => void;
}

export function LiveDashboard({
  stats,
  trades,
  onPause,
  onResume,
  onStart,
  onDisable,
}: LiveDashboardProps) {
  const [balance, setBalance] = useState<{
    spot_usdt: number;
    futures_usdt: number;
    total_usdt: number;
  } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch('/api/prices/balance');
        const data = await res.json();
        setBalance(data);
      } catch {
        // ignore
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  if (!stats) return null;

  const isStopped = !stats.enabled;
  const profitColor =
    stats.total_profit_usdt >= 0 ? 'text-green-400' : 'text-red-400';

  return (
    <div className="space-y-4">
      {/* Status & Controls */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-white font-semibold">Live Trading</h3>
          <div className="flex gap-2">
            {isStopped ? (
              <button
                onClick={onStart}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded text-sm font-medium"
              >
                Start
              </button>
            ) : stats.risk.paused ? (
              <button
                onClick={onResume}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded text-sm"
              >
                Resume
              </button>
            ) : (
              <>
                <button
                  onClick={onPause}
                  className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded text-sm"
                >
                  Pause
                </button>
                <button
                  onClick={onDisable}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded text-sm"
                >
                  Stop
                </button>
              </>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <div>
            <p className="text-gray-500 text-xs">Spot Balance</p>
            <p className="text-white font-mono text-lg">
              ${balance?.spot_usdt?.toFixed(2) ?? '...'}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Futures Balance</p>
            <p className="text-blue-400 font-mono text-lg">
              ${balance?.futures_usdt?.toFixed(2) ?? '...'}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">P&L</p>
            <p className={`font-mono text-lg ${profitColor}`}>
              {formatUsdt(stats.total_profit_usdt)}
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
              {formatUsdt(stats.total_fees_usdt)}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Streak</p>
            <p
              className={`font-mono ${
                stats.risk.consecutive_losses > 0
                  ? 'text-red-400'
                  : 'text-gray-300'
              }`}
            >
              {stats.risk.consecutive_losses > 0
                ? `${stats.risk.consecutive_losses} losses`
                : 'OK'}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Failed</p>
            <p className="text-red-400 font-mono">{stats.failed_trades}</p>
          </div>
        </div>
      </div>

      {/* Recent Trades - always visible */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <h3 className="text-white font-semibold mb-3">Recent Trades</h3>
        {trades.length === 0 ? (
          <p className="text-gray-500 text-center py-4">
            No trades yet. Waiting for opportunities...
          </p>
        ) : (
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
        )}
      </div>
    </div>
  );
}
