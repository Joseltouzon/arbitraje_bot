import { useState, useEffect, useRef } from 'react';

interface LogEntry {
  time: string;
  type: 'scan' | 'cycle' | 'spot_futures' | 'error' | 'info';
  message: string;
}

export function ActivityLog() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const disconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logCountRef = useRef(0);
  const wasConnectedRef = useRef(false);

  const addLog = (type: LogEntry['type'], message: string) => {
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
    setLogs((prev) => [...prev.slice(-49), { time, type, message }]);
  };

  useEffect(() => {
    const connect = () => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
        wsRef.current = ws;

        ws.onopen = () => {
          // Only log if this is a real reconnect (was disconnected for >5s)
          if (wasConnectedRef.current) {
            // Don't log reconnects from brief disconnects
          } else {
            addLog('info', 'Connected to server');
          }
          wasConnectedRef.current = true;
          // Cancel pending disconnect log
          if (disconnectTimerRef.current) {
            clearTimeout(disconnectTimerRef.current);
            disconnectTimerRef.current = null;
          }
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            logCountRef.current++;

            if (data.type === 'cycles' && Array.isArray(data.data)) {
              if (data.data.length > 0) {
                const best = data.data[0];
                addLog('cycle', `Cycle: ${best.currencies.join('→')} +${best.net_profit_pct.toFixed(3)}%`);
              }
            }
            if (data.type === 'spot_futures' && data.data) {
              const opp = data.data;
              addLog('spot_futures', `Premium: ${opp.symbol} ${opp.premium_pct.toFixed(3)}% net=${opp.net_profit_pct.toFixed(3)}%`);
            }
            if (data.type === 'paper_trade' && data.data) {
              const t = data.data;
              addLog('cycle', `Paper: ${t.currencies.join('→')} ${t.profit_usdt >= 0 ? '+' : ''}$${t.profit_usdt.toFixed(4)}`);
            }
            if (data.type === 'live_trade' && data.data) {
              const t = data.data;
              addLog('cycle', `LIVE: ${t.currencies.join('→')} ${t.profit_usdt >= 0 ? '+' : ''}$${t.profit_usdt.toFixed(4)} [${t.status}]`);
            }
            if (data.type === 'sf_trade' && data.data) {
              addLog('spot_futures', `Executed: ${data.data.symbol} [${data.data.status}]`);
            }
          } catch {
            // ignore
          }
        };

        ws.onclose = () => {
          // Delay disconnect log by 5s to avoid spam from brief drops
          if (!disconnectTimerRef.current) {
            disconnectTimerRef.current = setTimeout(() => {
              if (wasConnectedRef.current) {
                addLog('info', 'Connection lost, reconnecting...');
              }
              disconnectTimerRef.current = null;
            }, 5000);
          }
          wasConnectedRef.current = false;
          reconnectRef.current = setTimeout(connect, 3000);
        };

        ws.onerror = () => ws.close();
      } catch {
        reconnectRef.current = setTimeout(connect, 3000);
      }
    };

    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (disconnectTimerRef.current) clearTimeout(disconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, []);

  const typeColors: Record<string, string> = {
    scan: 'text-gray-500',
    cycle: 'text-green-400',
    spot_futures: 'text-blue-400',
    error: 'text-red-400',
    info: 'text-gray-400',
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <h3 className="text-white font-semibold mb-2">Activity Log</h3>
      <div className="h-40 overflow-y-auto font-mono text-xs space-y-0.5">
        {logs.length === 0 ? (
          <p className="text-gray-600">Waiting for activity...</p>
        ) : (
          logs.map((log, idx) => (
            <div key={idx} className="flex gap-2">
              <span className="text-gray-600 shrink-0">{log.time}</span>
              <span className={`${typeColors[log.type]} shrink-0`}>
                [{log.type}]
              </span>
              <span className="text-gray-300">{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
