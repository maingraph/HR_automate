import { useEffect, useRef, useState, useCallback } from 'react';

type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface UseWebSocketOptions {
  onMessage?: (data: any) => void;
  onError?: (error: Event) => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
  heartbeatInterval?: number;
}

interface UseWebSocketReturn<T> {
  data: T | null;
  status: WebSocketStatus;
  error: string | null;
  send: (data: any) => void;
  reconnect: () => void;
}

/**
 * Custom hook for WebSocket connections with automatic reconnection and error handling.
 * 
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Heartbeat/ping-pong to keep connection alive
 * - Graceful error handling with fallback
 * - Connection status tracking
 * 
 * @param url - WebSocket URL (e.g., "/ws/jobs/123")
 * @param options - Configuration options
 */
export function useWebSocket<T = any>(
  url: string | null,
  options: UseWebSocketOptions = {}
): UseWebSocketReturn<T> {
  const {
    onMessage,
    onError,
    reconnectAttempts = 5,
    reconnectInterval = 1000,
    heartbeatInterval = 25000,
  } = options;

  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const shouldReconnectRef = useRef(true);

  const clearTimeouts = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current);
      heartbeatTimeoutRef.current = null;
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    clearTimeouts();
    heartbeatTimeoutRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, heartbeatInterval);
  }, [heartbeatInterval, clearTimeouts]);

  const connect = useCallback(() => {
    if (!url) return;

    try {
      // Determine WebSocket URL
      let wsUrl: string;
      
      if (url.startsWith('ws://') || url.startsWith('wss://')) {
        // Already a full WebSocket URL
        wsUrl = url;
      } else if (url.startsWith('/')) {
        // Path like /ws/jobs/123 - connect to backend (port 8000)
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const wsProtocol = apiUrl.startsWith('https') ? 'wss:' : 'ws:';
        const wsHost = apiUrl.replace(/^https?:\/\//, '');
        wsUrl = `${wsProtocol}//${wsHost}${url}`;
      } else {
        // Room format like "job:123" - convert to path
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const wsProtocol = apiUrl.startsWith('https') ? 'wss:' : 'ws:';
        const wsHost = apiUrl.replace(/^https?:\/\//, '');
        wsUrl = `${wsProtocol}//${wsHost}/ws/${url.replace(':', '/')}`;
      }

      setStatus('connecting');
      setError(null);

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log(`WebSocket connected: ${url}`);
        setStatus('connected');
        setError(null);
        reconnectCountRef.current = 0;
        startHeartbeat();
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          // Handle system messages
          if (message.type === 'pong' || message.type === 'heartbeat') {
            return;
          }
          
          if (message.type === 'connected') {
            console.log(`WebSocket room joined: ${message.room}`);
            return;
          }

          // Handle data updates - pass the full message, not just message.data
          setData(message);
          onMessage?.(message);
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (event) => {
        console.error('WebSocket error:', event);
        setStatus('error');
        setError('WebSocket connection error');
        onError?.(event);
      };

      ws.onclose = (event) => {
        console.log(`WebSocket closed: ${url} (code: ${event.code})`);
        setStatus('disconnected');
        clearTimeouts();

        // Attempt reconnection if not manually closed
        if (shouldReconnectRef.current && reconnectCountRef.current < reconnectAttempts) {
          const delay = reconnectInterval * Math.pow(2, reconnectCountRef.current);
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectCountRef.current + 1}/${reconnectAttempts})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectCountRef.current++;
            connect();
          }, delay);
        } else if (reconnectCountRef.current >= reconnectAttempts) {
          setError('Max reconnection attempts reached. Falling back to polling.');
        }
      };
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setStatus('error');
      setError('Failed to create WebSocket connection');
    }
  }, [url, reconnectAttempts, reconnectInterval, startHeartbeat, clearTimeouts, onMessage, onError]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    clearTimeouts();
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setStatus('disconnected');
  }, [clearTimeouts]);

  const reconnect = useCallback(() => {
    disconnect();
    reconnectCountRef.current = 0;
    shouldReconnectRef.current = true;
    connect();
  }, [connect, disconnect]);

  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data));
    } else {
      console.warn('WebSocket is not connected. Cannot send message.');
    }
  }, []);

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    if (url) {
      shouldReconnectRef.current = true;
      connect();
    }

    return () => {
      disconnect();
    };
  }, [url, connect, disconnect]);

  return {
    data,
    status,
    error,
    send,
    reconnect,
  };
}
