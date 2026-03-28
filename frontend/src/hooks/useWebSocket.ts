import { useState, useEffect, useRef, useCallback } from 'react';
import type { TriangularCycle } from '../types';

export function useWebSocket() {
  const [cycles, setCycles] = useState<TriangularCycle[]>([]);
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

  return { cycles, connected, lastMessage };
}
