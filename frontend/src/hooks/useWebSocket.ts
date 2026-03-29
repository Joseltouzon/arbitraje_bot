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

export function useWebSocket() {
  const [cycles, setCycles] = useState<TriangularCycle[]>([]);
  const [spotFutures, setSpotFutures] = useState<SpotFuturesOpportunity[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

      ws.onopen = () => {
        setConnected(true);
        ws.send('ping');
      };

      ws.onmessage = (event) => {
        setLastMessage(event.data);
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'cycles' && Array.isArray(data.data)) {
            setCycles(data.data);
          }
          if (data.type === 'spot_futures' && data.data) {
            setSpotFutures((prev) => {
              const filtered = prev.filter(
                (p) => p.symbol !== data.data.symbol
              );
              return [data.data, ...filtered].slice(0, 10);
            });
          }
        } catch {
          // ignore non-JSON messages
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
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return { cycles, spotFutures, connected, lastMessage };
}
