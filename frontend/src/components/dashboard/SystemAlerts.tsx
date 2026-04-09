import { useEffect, useState } from 'react';
import type { Alert, AlertsResponse } from '../../types';
import { clearAlerts, fetchAlerts } from '../../lib/api';

export function SystemAlerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [count, setCount] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);

  const loadAlerts = async () => {
    try {
      const data: AlertsResponse = await fetchAlerts(50, filter || undefined);
      setAlerts(data.alerts);
      setCount(data.count);
    } catch (e) {
      console.error('Failed to load alerts:', e);
    }
  };

  useEffect(() => {
    loadAlerts();
    const interval = setInterval(loadAlerts, 5000);
    return () => clearInterval(interval);
  }, [filter]);

  const handleClear = async () => {
    setLoading(true);
    await clearAlerts();
    await loadAlerts();
    setLoading(false);
  };

  const typeConfig: Record<string, { color: string; bg: string; label: string }> = {
    error: { color: 'text-red-400', bg: 'bg-red-900/30', label: 'ERROR' },
    warning: { color: 'text-yellow-400', bg: 'bg-yellow-900/30', label: 'WARN' },
    circuit_breaker: { color: 'text-orange-400', bg: 'bg-orange-900/30', label: 'CB' },
    trade_failed: { color: 'text-red-400', bg: 'bg-red-900/30', label: 'FAIL' },
    trade_success: { color: 'text-green-400', bg: 'bg-green-900/30', label: 'OK' },
    info: { color: 'text-blue-400', bg: 'bg-blue-900/30', label: 'INFO' },
  };

  const filterOptions = [
    { value: null, label: 'All' },
    { value: 'error', label: 'Errors' },
    { value: 'warning', label: 'Warnings' },
    { value: 'circuit_breaker', label: 'Circuit Breaker' },
    { value: 'trade_failed', label: 'Trade Failed' },
    { value: 'trade_success', label: 'Trade Success' },
  ];

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          System Alerts
          {count.error + count.trade_failed + count.circuit_breaker > 0 && (
            <span className="bg-red-600 text-white text-xs px-2 py-0.5 rounded-full">
              {count.error + count.trade_failed + count.circuit_breaker}
            </span>
          )}
        </h3>
        <div className="flex items-center gap-2">
          <select
            value={filter || ''}
            onChange={(e) => setFilter(e.target.value || null)}
            className="bg-gray-700 text-gray-300 text-xs rounded px-2 py-1 border border-gray-600"
          >
            {filterOptions.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value || ''}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleClear}
            disabled={loading}
            className="text-xs text-gray-400 hover:text-white px-2 py-1 border border-gray-600 rounded hover:bg-gray-700 disabled:opacity-50"
          >
            Clear
          </button>
        </div>
      </div>

      {count.error > 0 && (
        <div className="flex gap-4 text-xs mb-2">
          {count.error > 0 && <span className="text-red-400">Errors: {count.error}</span>}
          {count.warning > 0 && <span className="text-yellow-400">Warnings: {count.warning}</span>}
          {count.circuit_breaker > 0 && <span className="text-orange-400">Circuit Breaker: {count.circuit_breaker}</span>}
        </div>
      )}

      <div className="h-48 overflow-y-auto space-y-1">
        {alerts.length === 0 ? (
          <p className="text-gray-600 text-sm">No alerts</p>
        ) : (
          alerts.map((alert) => {
            const config = typeConfig[alert.type] || typeConfig.info;
            return (
              <div
                key={alert.id}
                className={`flex items-start gap-2 p-2 rounded text-xs ${config.bg}`}
              >
                <span className={`${config.color} font-mono shrink-0 w-10`}>
                  {config.label}
                </span>
                <span className="text-gray-500 shrink-0">
                  {new Date(alert.timestamp).toLocaleTimeString()}
                </span>
                <span className="text-gray-300">{alert.message}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
