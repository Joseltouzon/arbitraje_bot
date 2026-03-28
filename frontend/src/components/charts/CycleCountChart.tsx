import { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { fetchProfitTimeseries } from '../../lib/api';
import type { TimeseriesPoint } from '../../types';

export function CycleCountChart() {
  const [data, setData] = useState<TimeseriesPoint[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetchProfitTimeseries(24);
        setData(res.timeseries || []);
      } catch {
        // ignore
      }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (ts: string) => {
    const d = new Date(ts);
    return `${d.getHours().toString().padStart(2, '0')}:00`;
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-4">
        Cycles Detected per Hour
      </h3>

      {data.length === 0 ? (
        <div className="text-center text-gray-500 py-10">
          <p>No data yet...</p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data}>
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
            />
            <Bar dataKey="count" fill="#6366F1" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
