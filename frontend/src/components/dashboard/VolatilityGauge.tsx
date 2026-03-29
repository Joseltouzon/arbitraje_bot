import { useState, useEffect } from 'react';
import { fetchHealth } from '../../lib/api';

interface VolatilityData {
  volatility_score: number;
  is_volatile: boolean;
  update_count: number;
}

export function VolatilityGauge() {
  const [data, setData] = useState<VolatilityData | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const health = await fetchHealth();
        setData(health.volatility || null);
      } catch {
        // ignore
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!data) return null;

  const score = Math.min(data.volatility_score, 100);
  const color = score > 60 ? 'bg-red-500' : score > 40 ? 'bg-yellow-500' : score > 20 ? 'bg-blue-500' : 'bg-gray-500';
  const label = score > 60 ? 'HIGH' : score > 40 ? 'ELEVATED' : score > 20 ? 'NORMAL' : 'LOW';
  const textColor = score > 60 ? 'text-red-400' : score > 40 ? 'text-yellow-400' : score > 20 ? 'text-blue-400' : 'text-gray-400';

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-white font-semibold text-sm">Market Volatility</h3>
        <span className={`font-bold text-sm ${textColor}`}>{label}</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-3">
        <div
          className={`${color} h-3 rounded-full transition-all duration-500`}
          style={{ width: `${score}%` }}
        />
      </div>
      <div className="flex justify-between mt-1 text-xs text-gray-500">
        <span>0</span>
        <span className="font-mono">{score.toFixed(1)}</span>
        <span>100</span>
      </div>
    </div>
  );
}
