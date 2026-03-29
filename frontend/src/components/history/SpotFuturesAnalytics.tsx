import { useState, useEffect } from 'react';
import { fetchSpotFuturesHistory, fetchSpotFuturesStats } from '../../lib/api';
import { formatPct } from '../../lib/utils';

interface SFRecord {
  id: number;
  symbol: string;
  premium_pct: number;
  net_profit_pct: number;
  direction: string;
  funding_rate: number;
  detected_at: string;
}

export function SpotFuturesAnalytics() {
  const [records, setRecords] = useState<SFRecord[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        const [histRes] = await Promise.all([
          fetchSpotFuturesHistory(200),
          fetchSpotFuturesStats(),
        ]);
        setRecords(histRes.records || []);
      } catch {
        // ignore
      }
    };
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  const totalDetected = records.length;
  const avgPremium =
    totalDetected > 0
      ? records.reduce((s, r) => s + r.premium_pct, 0) / totalDetected
      : 0;
  const avgNetProfit =
    totalDetected > 0
      ? records.reduce((s, r) => s + r.net_profit_pct, 0) / totalDetected
      : 0;
  const bestPremium =
    totalDetected > 0
      ? Math.max(...records.map((r) => r.premium_pct))
      : 0;
  const bestNetProfit =
    totalDetected > 0
      ? Math.max(...records.map((r) => r.net_profit_pct))
      : 0;
  const totalPremiumProfit =
    totalDetected > 0
      ? records.reduce((s, r) => s + r.net_profit_pct, 0)
      : 0;

  const premiumCount = records.filter((r) => r.direction === 'futures_premium').length;
  const discountCount = records.filter((r) => r.direction === 'futures_discount').length;

  const symbolBreakdown: Record<string, number> = {};
  records.forEach((r) => {
    symbolBreakdown[r.symbol] = (symbolBreakdown[r.symbol] || 0) + 1;
  });

  const items = [
    { label: 'Total Detected', value: totalDetected.toString(), color: 'text-blue-400' },
    { label: 'Avg Premium', value: formatPct(avgPremium), color: 'text-green-400' },
    { label: 'Avg Net Profit', value: formatPct(avgNetProfit), color: 'text-green-300' },
    { label: 'Best Premium', value: formatPct(bestPremium), color: 'text-green-400' },
    { label: 'Best Net Profit', value: formatPct(bestNetProfit), color: 'text-yellow-400' },
    { label: 'Total Premium %', value: formatPct(totalPremiumProfit), color: 'text-blue-300' },
    { label: 'Premium Count', value: premiumCount.toString(), color: 'text-green-300' },
    { label: 'Discount Count', value: discountCount.toString(), color: 'text-red-300' },
  ];

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-4">
        Spot-Futures Performance
      </h3>
      <div className="grid grid-cols-4 gap-3">
        {items.map((item) => (
          <div key={item.label} className="bg-gray-900/50 rounded p-3">
            <p className="text-gray-500 text-xs">{item.label}</p>
            <p className={`text-lg font-bold font-mono ${item.color}`}>
              {item.value}
            </p>
          </div>
        ))}
      </div>

      {Object.keys(symbolBreakdown).length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <h4 className="text-gray-400 text-sm mb-2">By Symbol</h4>
          <div className="flex gap-4">
            {Object.entries(symbolBreakdown)
              .sort(([, a], [, b]) => b - a)
              .map(([symbol, count]) => (
                <div key={symbol} className="text-sm">
                  <span className="text-white font-mono">{symbol}</span>
                  <span className="text-gray-500 ml-2">{count} detections</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
