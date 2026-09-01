import { useEffect, useRef, useState, useCallback } from 'react';
import { getAuthToken } from '@/lib/api';

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
// Remove /api/v1 since WebSocket is mounted at the root /ws
const WS_BASE = API_URL.replace('http://', 'ws://').replace('https://', 'wss://').replace('/api/v1', '');

export interface WSEvent {
  type: string;
  [key: string]: any;
}

export function useWebSocket(projectId: string | null, threadId?: string, onMessage?: (event: WSEvent) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (!projectId) return;
    
    // Don't reconnect if already connected
    if (ws.current?.readyState === WebSocket.OPEN) return;

    const token = getAuthToken();
    let url = `${WS_BASE}/ws/${projectId}`;
    const params = new URLSearchParams();
    if (threadId) params.append('thread_id', threadId);
    if (token) params.append('token', token);
    
    if (params.toString()) {
      url += `?${params.toString()}`;
    }

    try {
      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      };

      ws.current.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          setLastEvent(parsed);
          if (onMessage) onMessage(parsed);
        } catch (e) {
          console.error("Failed to parse WS message", e);
        }
      };

      ws.current.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        ws.current = null;
        // Auto-reconnect after 3 seconds
        reconnectTimeout.current = setTimeout(connect, 3000);
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error', error);
      };
    } catch (e) {
      console.error('WebSocket initialization error', e);
    }
  }, [projectId, threadId]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) {
        ws.current.close();
        ws.current = null;
      }
    };
  }, [connect]);

  return { isConnected, lastEvent };
}
