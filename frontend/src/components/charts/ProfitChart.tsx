import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { fetchProfitTimeseries } from '../../lib/api';
import type { TimeseriesPoint } from '../../types';

export function ProfitChart() {
  const [data, setData] = useState<TimeseriesPoint[]>([]);
  const [hours, setHours] = useState(24);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetchProfitTimeseries(hours);
        setData(res.timeseries || []);
      } catch {
        // ignore
      }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [hours]);

  const formatTime = (ts: string) => {
    const d = new Date(ts);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-white font-semibold">Profit Over Time</h3>
        <div className="flex gap-2">
          {[6, 12, 24].map((h) => (
            <button
              key={h}
              onClick={() => setHours(h)}
              className={`px-3 py-1 rounded text-xs ${
                hours === h
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
              }`}
            >
              {h}h
            </button>
          ))}
        </div>
      </div>

      {data.length === 0 ? (
        <div className="text-center text-gray-500 py-10">
          <p>No data yet. Waiting for cycles...</p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatTime}
              stroke="#6B7280"
              fontSize={11}
            />
            <YAxis stroke="#6B7280" fontSize={11} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '8px',
                color: '#F3F4F6',
              }}
              labelFormatter={(label) => new Date(label).toLocaleString()}
            />
            <Line
              type="monotone"
              dataKey="max_profit_pct"
              stroke="#10B981"
              strokeWidth={2}
              dot={false}
              name="Max Profit %"
            />
            <Line
              type="monotone"
              dataKey="avg_profit_pct"
              stroke="#3B82F6"
              strokeWidth={2}
              dot={false}
              name="Avg Profit %"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
