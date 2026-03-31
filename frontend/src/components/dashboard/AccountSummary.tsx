import { useState, useEffect } from 'react';

export function AccountSummary() {
  const [data, setData] = useState<{
    totalPnl: number;
    triangularPnl: number;
    triangularTrades: number;
    sfTrades: number;
  }>({ totalPnl: 0, triangularPnl: 0, triangularTrades: 0, sfTrades: 0 });

  useEffect(() => {
    const load = async () => {
      try {
        const health = await fetch('/health').then((r) => r.json());
        const triPnl = health.live?.total_profit_usdt || 0;
        const triTrades = health.live?.total_trades || 0;
        const sfTrades = health.sf_executor?.total_trades || 0;
        setData({
          totalPnl: triPnl,
          triangularPnl: triPnl,
          triangularTrades: triTrades,
          sfTrades,
        });
      } catch { /* ignore */ }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  const totalTrades = data.triangularTrades + data.sfTrades;
  const pnlColor = data.totalPnl >= 0 ? 'text-green-400' : 'text-red-400';

  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <p className="text-gray-500 text-xs uppercase tracking-wide">Total P&L</p>
        <p className={`text-xl font-bold font-mono mt-1 ${pnlColor}`}>
          {data.totalPnl >= 0 ? '+' : ''}${data.totalPnl.toFixed(4)}
        </p>
        <p className="text-gray-600 text-xs mt-1">Tri + Spot-Futures</p>
      </div>
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <p className="text-gray-500 text-xs uppercase tracking-wide">Total Trades</p>
        <p className="text-xl font-bold font-mono mt-1 text-blue-400">{totalTrades}</p>
        <p className="text-gray-600 text-xs mt-1">
          Tri: {data.triangularTrades} | SF: {data.sfTrades}
        </p>
      </div>
    </div>
  );
}
