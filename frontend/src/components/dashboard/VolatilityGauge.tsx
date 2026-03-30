import { useState, useEffect } from 'react';

export function VolatilityGauge() {
  const [score, setScore] = useState(0);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch('/health');
        const data = await res.json();
        if (data.volatility) {
          setScore(data.volatility.volatility_score || 0);
        }
        setLoaded(true);
      } catch {
        setLoaded(true);
      }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  const s = Math.min(score, 100);
  const color =
    s > 60
      ? 'bg-red-500'
      : s > 40
        ? 'bg-yellow-500'
        : s > 20
          ? 'bg-blue-500'
          : 'bg-gray-500';
  const label =
    s > 60 ? 'HIGH' : s > 40 ? 'ELEVATED' : s > 20 ? 'NORMAL' : 'LOW';
  const textColor =
    s > 60
      ? 'text-red-400'
      : s > 40
        ? 'text-yellow-400'
        : s > 20
          ? 'text-blue-400'
          : 'text-gray-400';

  if (!loaded) {
    return (
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <h3 className="text-white font-semibold text-sm">Market Volatility</h3>
        <p className="text-gray-500 text-xs mt-2">Loading...</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-white font-semibold text-sm">Market Volatility</h3>
        <span className={`font-bold text-sm ${textColor}`}>{label}</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-3">
        <div
          className={`${color} h-3 rounded-full transition-all duration-500`}
          style={{ width: `${s}%` }}
        />
      </div>
      <div className="flex justify-between mt-1 text-xs text-gray-500">
        <span>0</span>
        <span className="font-mono">{s.toFixed(1)}</span>
        <span>100</span>
      </div>
    </div>
  );
}
