"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { usePrices, type SymbolPrice } from "@/context/PriceContext";

export interface UsePriceFeedResult {
  price: SymbolPrice | null;
  history: { timestamp: number; price: number }[];
  connected: boolean;
  error: string | null;
}

export function usePriceFeed(symbol: string): UsePriceFeedResult {
  const { prices, history, connected, error } = usePrices();

  const price = prices[symbol] ?? null;
  const priceHistory = history[symbol] ?? [];

  return { price, history: priceHistory, connected, error };
}

interface WebSocketOptions {
  url: string;
  onMessage?: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnect?: boolean;
  maxReconnectAttempts?: number;
}

export function useWebSocket(options: WebSocketOptions) {
  const {
    url,
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnect = true,
    maxReconnectAttempts = 10,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!url || !mountedRef.current) return;

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        reconnectAttempts.current = 0;
        setConnected(true);
        setError(null);
        onOpen?.();
      };

      ws.onclose = () => {
        setConnected(false);
        onClose?.();
        if (reconnect && mountedRef.current) {
          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttempts.current),
            30000
          );
          if (reconnectAttempts.current < maxReconnectAttempts) {
            reconnectAttempts.current += 1;
            reconnectTimer.current = setTimeout(connect, delay);
          } else {
            setError("Max reconnection attempts reached");
          }
        }
      };

      ws.onerror = (e) => {
        setError("WebSocket error");
        onError?.(e);
      };

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          onMessage?.(data);
        } catch {
          // ignore malformed
        }
      };

      wsRef.current = ws;
    } catch {
      setError("Failed to create WebSocket");
      if (reconnect && mountedRef.current) {
        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttempts.current),
          30000
        );
        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current += 1;
          reconnectTimer.current = setTimeout(connect, delay);
        }
      }
    }
  }, [url, reconnect, maxReconnectAttempts, onMessage, onOpen, onClose, onError]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    wsRef.current?.close();
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected, error, send, disconnect };
}
