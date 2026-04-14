"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  type ReactNode,
} from "react";

export interface WsPriceData {
  symbol: string;
  mark: string;
  mid: string;
  oracle: string;
  funding: string;
  next_funding: string;
  open_interest: string;
  volume_24h: string;
  yesterday_price: string;
  timestamp: number;
}

interface WsMessage {
  type: string;
  timestamp: number;
  prices: WsPriceData[];
  funding_rates: unknown[];
}

export interface SymbolPrice {
  symbol: string;
  price: number;
  midPrice: number;
  oraclePrice: number;
  fundingRate: number;
  nextFundingRate: number;
  openInterest: number;
  volume24h: number;
  change24h: number;
  change24hPct: number;
  timestamp: number;
  bid: number;
  ask: number;
  spread: number;
  spreadPct: number;
}

interface PriceHistoryPoint {
  timestamp: number;
  price: number;
}

interface PriceState {
  prices: Record<string, SymbolPrice>;
  history: Record<string, PriceHistoryPoint[]>;
  connected: boolean;
  lastUpdate: number | null;
  error: string | null;
}

interface PriceContextValue extends PriceState {
  usePriceFeed: (symbol: string) => SymbolPrice | null;
}

const PriceContext = createContext<PriceContextValue | null>(null);

const WS_URL =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000") +
      "/ws/prices"
    : "";

const MAX_HISTORY_POINTS = 288;
const HISTORY_INTERVAL_MS = 5 * 60 * 1000;
const UI_THROTTLE_MS = 1000;

function parseNum(s: string | undefined | null): number {
  if (!s) return 0;
  const n = parseFloat(s);
  return Number.isFinite(n) ? n : 0;
}

function computeDerived(d: WsPriceData): SymbolPrice {
  const mark = parseNum(d.mark);
  const mid = parseNum(d.mid);
  const oracle = parseNum(d.oracle);
  const yesterday = parseNum(d.yesterday_price);
  const funding = parseNum(d.funding);
  const nextFunding = parseNum(d.next_funding);
  const oi = parseNum(d.open_interest);
  const vol = parseNum(d.volume_24h);
  const change24h = yesterday > 0 ? mark - yesterday : 0;
  const change24hPct = yesterday > 0 ? (change24h / yesterday) * 100 : 0;
  const halfSpread = Math.abs(mark - mid) / 2;
  const bid = mid > 0 ? mid - halfSpread : mark;
  const ask = mid > 0 ? mid + halfSpread : mark;
  const spread = ask - bid;
  const spreadPct = mid > 0 ? (spread / mid) * 100 : 0;

  return {
    symbol: d.symbol,
    price: mark,
    midPrice: mid,
    oraclePrice: oracle,
    fundingRate: funding,
    nextFundingRate: nextFunding,
    openInterest: oi,
    volume24h: vol,
    change24h,
    change24hPct,
    timestamp: d.timestamp,
    bid,
    ask,
    spread,
    spreadPct,
  };
}

function pruneHistory(
  points: PriceHistoryPoint[],
  now: number
): PriceHistoryPoint[] {
  const cutoff = now - 24 * 60 * 60 * 1000;
  return points.filter((p) => p.timestamp >= cutoff);
}

export function PriceProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PriceState>({
    prices: {},
    history: {},
    connected: false,
    lastUpdate: null,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);
  const lastUiUpdate = useRef(0);
  const pendingData = useRef<WsMessage | null>(null);
  const historyRef = useRef<Record<string, PriceHistoryPoint[]>>({});
  const mountedRef = useRef(true);

  const processMessage = useCallback((msg: WsMessage) => {
    if (msg.type !== "price_update" || !Array.isArray(msg.prices)) return;

    const now = Date.now();
    const newPrices: Record<string, SymbolPrice> = {};
    const history = historyRef.current;

    for (const p of msg.prices) {
      const derived = computeDerived(p);
      newPrices[derived.symbol] = derived;

      if (!history[derived.symbol]) {
        history[derived.symbol] = [];
      }
      const points = history[derived.symbol];
      const lastPoint = points[points.length - 1];
      if (
        !lastPoint ||
        derived.timestamp - lastPoint.timestamp >= HISTORY_INTERVAL_MS
      ) {
        points.push({ timestamp: derived.timestamp, price: derived.price });
        if (points.length > MAX_HISTORY_POINTS) {
          history[derived.symbol] = pruneHistory(
            points.slice(-MAX_HISTORY_POINTS),
            now
          );
        }
      }
    }

    setState((prev) => ({
      ...prev,
      prices: { ...prev.prices, ...newPrices },
      history: { ...history },
      lastUpdate: msg.timestamp,
      error: null,
    }));
  }, []);

  useEffect(() => {
    const throttleInterval = setInterval(() => {
      if (pendingData.current) {
        processMessage(pendingData.current);
        pendingData.current = null;
        lastUiUpdate.current = Date.now();
      }
    }, UI_THROTTLE_MS);

    return () => clearInterval(throttleInterval);
  }, [processMessage]);

  const connect = useCallback(() => {
    if (!WS_URL) return;
    try {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        reconnectAttempts.current = 0;
        setState((prev) => ({ ...prev, connected: true, error: null }));
      };

      ws.onclose = () => {
        setState((prev) => ({ ...prev, connected: false }));
        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttempts.current),
          30000
        );
        reconnectAttempts.current += 1;
        reconnectTimer.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        setState((prev) => ({
          ...prev,
          error: "WebSocket connection failed",
        }));
        ws.close();
      };

      ws.onmessage = (e) => {
        try {
          const msg: WsMessage = JSON.parse(e.data);
          pendingData.current = msg;
        } catch {
          // ignore malformed messages
        }
      };

      wsRef.current = ws;
    } catch {
      const delay = Math.min(
        1000 * Math.pow(2, reconnectAttempts.current),
        30000
      );
      reconnectAttempts.current += 1;
      reconnectTimer.current = setTimeout(connect, delay);
    }
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

  const usePriceFeed = useCallback(
    (symbol: string): SymbolPrice | null => {
      return state.prices[symbol] ?? null;
    },
    [state.prices]
  );

  return (
    <PriceContext.Provider
      value={{
        prices: state.prices,
        history: state.history,
        connected: state.connected,
        lastUpdate: state.lastUpdate,
        error: state.error,
        usePriceFeed,
      }}
    >
      {children}
    </PriceContext.Provider>
  );
}

export function usePrices(): PriceContextValue {
  const ctx = useContext(PriceContext);
  if (!ctx) {
    throw new Error("usePrices must be used within a PriceProvider");
  }
  return ctx;
}
