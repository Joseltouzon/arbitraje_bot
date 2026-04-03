import { useState, useEffect, useRef, useCallback } from 'react';
import type { TriangularCycle } from '../types';

interface SpotFuturesOpportunity {
  symbol: string;
  spot_price: number;
  futures_price: number;
  premium_pct: number;
  net_profit_pct: number;
  direction: string;
  funding_rate: number;
}

export interface LogEntry {
  time: string;
  type: 'scan' | 'cycle' | 'spot_futures' | 'error' | 'info';
  message: string;
}

export function useWebSocket() {
  const [cycles, setCycles] = useState<TriangularCycle[]>([]);
  const [spotFutures, setSpotFutures] = useState<SpotFuturesOpportunity[]>([]);
  const [connected, setConnected] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const msgCountRef = useRef(0);

  const addLog = useCallback(
    (type: LogEntry['type'], message: string) => {
      const now = new Date();
      const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
      setLogs((prev) => [...prev.slice(-49), { time, type, message }]);
    },
    []
  );

  const connect = useCallback(() => {
    try {
      const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        addLog('info', 'Connected');
        try { ws.send('ping'); } catch { /* ignore */ }
      };

      ws.onerror = (error) => {
        console.log('WebSocket error:', error);
        addLog('error', 'WS connection error');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          msgCountRef.current++;

          if (data.type === 'cycles' && Array.isArray(data.data)) {
            setCycles(data.data);
            if (data.data.length > 0) {
              const best = data.data[0];
              addLog('cycle', `${best.currencies.join('→')} +${best.net_profit_pct.toFixed(3)}%`);
            }
          }
          if (data.type === 'spot_futures' && data.data) {
            const opp = data.data;
            setSpotFutures((prev) => {
              const filtered = prev.filter((p) => p.symbol !== opp.symbol);
              return [opp, ...filtered].slice(0, 10);
            });
            addLog('spot_futures', `${opp.symbol} ${opp.premium_pct.toFixed(3)}% net=${opp.net_profit_pct.toFixed(3)}%`);
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
        setConnected(false);
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      reconnectTimeoutRef.current = setTimeout(connect, 3000);
    }
  }, [addLog]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return { cycles, spotFutures, connected, logs };
}
