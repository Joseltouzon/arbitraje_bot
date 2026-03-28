import { useState, useEffect } from 'react';
import { fetchHealth } from '../../lib/api';
import { formatTime } from '../../lib/utils';
import type { ScannerStats } from '../../types';

interface HeaderProps {
  connected: boolean;
}

export function Header({ connected }: HeaderProps) {
  const [stats, setStats] = useState<ScannerStats | null>(null);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const data = await fetchHealth();
        setStats(data.scanner);
      } catch {
        // ignore
      }
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="bg-gray-900 border-b border-gray-700 px-6 py-4 flex items-center justify-between">
      <div>
        <h1 className="text-xl font-bold text-white">
          Triangular Arbitrage
        </h1>
        <p className="text-gray-400 text-sm">Binance • Detection Mode</p>
      </div>
      <div className="flex items-center gap-6 text-sm">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              connected ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="text-gray-300">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        {stats && (
          <>
            <div className="text-gray-400">
              Scans: <span className="text-white">{stats.scan_count}</span>
            </div>
            <div className="text-gray-400">
              Last:{' '}
              <span className="text-white">
                {formatTime(stats.last_scan)}
              </span>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
