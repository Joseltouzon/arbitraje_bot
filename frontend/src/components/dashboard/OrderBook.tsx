import { useState, useEffect, useCallback } from 'react';
import { fetchPrices } from '../../lib/api';

interface Ticker {
  bid: number;
  ask: number;
  spread_pct: number;
}

export function OrderBook() {
  const [tickers, setTickers] = useState<Record<string, Ticker>>({});
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetchPrices();
      if (res && res.tickers) {
        setTickers(res.tickers);
        setTotal(res.total || Object.keys(res.tickers).length);
        setLastUpdate(new Date());
        setError(null);
      }
      setLoading(false);
    } catch (e) {
      setError('Cannot connect to backend');
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    // Poll every 3 seconds for live updates
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, [load]);

  const filtered = Object.entries(tickers).filter(([symbol]) =>
    symbol.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <h3 className="text-white font-semibold mb-3">Order Book</h3>
        <p className="text-gray-500 text-center py-4">Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <h3 className="text-white font-semibold mb-3">Order Book</h3>
        <p className="text-red-400 text-center py-4">{error}</p>
        <button
          onClick={load}
          className="w-full bg-gray-700 hover:bg-gray-600 text-white rounded py-2 text-sm"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-white font-semibold">Order Book (Top Tickers)</h3>
        <div className="flex items-center gap-2">
          <span className="text-green-500 text-xs flex items-center gap-1">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
            LIVE
          </span>
          <span className="text-gray-400 text-sm">{total} pairs</span>
        </div>
      </div>
      {lastUpdate && (
        <div className="text-xs text-gray-500 mb-2">
          Updated: {lastUpdate.toLocaleTimeString()}
        </div>
      )}

      <input
        type="text"
        placeholder="Search pair (e.g. BTCUSDT)..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-2 text-white text-sm mb-3 focus:outline-none focus:border-blue-500"
      />

      <div className="overflow-y-auto max-h-80">
        {filtered.length === 0 ? (
          <p className="text-gray-500 text-center py-4">
            No pairs match "{search}"
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-800">
              <tr className="text-gray-500 text-left">
                <th className="pb-2 pr-3">Pair</th>
                <th className="pb-2 pr-3 text-right">Bid</th>
                <th className="pb-2 pr-3 text-right">Ask</th>
                <th className="pb-2 text-right">Spread %</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 50).map(([symbol, data]) => (
                <tr
                  key={symbol}
                  className="border-t border-gray-700/50 hover:bg-gray-700/30"
                >
                  <td className="py-1.5 pr-3 text-white font-mono font-medium">
                    {symbol}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-green-400 font-mono">
                    {data.bid.toLocaleString(undefined, {
                      maximumFractionDigits: 8,
                    })}
                  </td>
                  <td className="py-1.5 pr-3 text-right text-red-400 font-mono">
                    {data.ask.toLocaleString(undefined, {
                      maximumFractionDigits: 8,
                    })}
                  </td>
                  <td className="py-1.5 text-right text-gray-400 font-mono">
                    {data.spread_pct.toFixed(4)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
