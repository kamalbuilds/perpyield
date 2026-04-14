"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchTradeHistory, type TradeRecord } from "@/lib/api";

export interface UseTradeHistoryReturn {
  trades: TradeRecord[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  loadMore: () => void;
  refetch: () => void;
}

export function useTradeHistory(address?: string): UseTradeHistoryReturn {
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTrades = useCallback(async (cur?: string, append = false) => {
    try {
      setLoading(true);
      const res = await fetchTradeHistory(address, 50, cur);
      setTrades((prev) => (append ? [...prev, ...res.data] : res.data));
      setCursor(res.next_cursor);
      setHasMore(res.has_more);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch trade history");
    } finally {
      setLoading(false);
    }
  }, [address]);

  useEffect(() => {
    loadTrades();
  }, [loadTrades]);

  const loadMore = useCallback(() => {
    if (cursor && hasMore) loadTrades(cursor, true);
  }, [cursor, hasMore, loadTrades]);

  const refetch = useCallback(() => {
    setCursor(null);
    loadTrades();
  }, [loadTrades]);

  return { trades, loading, error, hasMore, loadMore, refetch };
}
