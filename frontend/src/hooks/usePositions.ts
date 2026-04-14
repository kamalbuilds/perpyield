"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { fetchPositions, type PositionsResponse, type PositionEntry, type LivePosition } from "@/lib/api";
import { usePrices, type WsStatus } from "@/context/PriceContext";

export interface EnrichedPosition extends PositionEntry {
  mark_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  liquidation_price: number;
  leverage: number;
  notional_value: number;
}

export interface UsePositionsReturn {
  positions: EnrichedPosition[];
  rawResponse: PositionsResponse | null;
  loading: boolean;
  error: string | null;
  connected: boolean;
  wsStatus: WsStatus;
  totalUnrealizedPnl: number;
  totalFundingEarned: number;
  activeCount: number;
  refetch: () => void;
  exportCSV: () => string;
}

function enrichPosition(pos: PositionEntry, markPrice: number): EnrichedPosition {
  const size = Math.abs(pos.size);
  const notional = size * markPrice;
  const leverage = 5;
  const margin = notional / leverage;

  let unrealizedPnl: number;
  if (pos.side === "long") {
    unrealizedPnl = (markPrice - pos.entry_price) * size;
  } else {
    unrealizedPnl = (pos.entry_price - markPrice) * size;
  }

  const unrealizedPnlPct = margin > 0 ? (unrealizedPnl / margin) * 100 : 0;

  let liquidationPrice: number;
  if (pos.side === "long") {
    liquidationPrice = pos.entry_price * (1 - 0.9 / leverage);
  } else {
    liquidationPrice = pos.entry_price * (1 + 0.9 / leverage);
  }

  return {
    ...pos,
    mark_price: markPrice,
    unrealized_pnl: unrealizedPnl,
    unrealized_pnl_pct: unrealizedPnlPct,
    liquidation_price: liquidationPrice,
    leverage,
    notional_value: notional,
  };
}

export function usePositions(): UsePositionsReturn {
  const [rawResponse, setRawResponse] = useState<PositionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { prices, connected, wsStatus } = usePrices();

  const loadPositions = useCallback(async () => {
    try {
      const data = await fetchPositions();
      setRawResponse(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch positions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPositions();
    const interval = setInterval(loadPositions, 5000);
    return () => clearInterval(interval);
  }, [loadPositions]);

  // Map strategy positions
  const strategyPositions = (rawResponse?.strategy_positions?.positions ?? []).map((p: PositionEntry) => {
    const wsPrice = prices[p.symbol];
    const markPrice = wsPrice?.price ?? p.entry_price;
    return enrichPosition(p, markPrice);
  });

  // Map live positions from Pacifica
  const livePositions = (rawResponse?.live_positions ?? []).map((p: LivePosition) => {
    const wsPrice = prices[p.symbol];
    const fallbackPrice = p.mark_price ? parseFloat(p.mark_price) : 0;
    const markPrice = wsPrice?.price ?? fallbackPrice ?? p.entry_price;
    return enrichPosition(p as PositionEntry, markPrice);
  });

  // Combine both - prefer live positions if they exist
  const positions = livePositions.length > 0 ? livePositions : strategyPositions;

  const totalUnrealizedPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0);
  const totalFundingEarned = rawResponse?.strategy_positions?.total_funding_earned ?? 0;
  const activeCount = positions.length;

  const exportCSV = useCallback(() => {
    const header = "Symbol,Side,Size,Entry Price,Mark Price,Unrealized PnL,Funding Earned,Liquidation Price,Leverage\n";
    const rows = positions.map((p) =>
      `${p.symbol},${p.side},${p.size},${p.entry_price},${p.mark_price},${p.unrealized_pnl},${p.cumulative_funding},${p.liquidation_price},${p.leverage}`
    ).join("\n");
    return header + rows;
  }, [positions]);

  return {
    positions,
    rawResponse,
    loading,
    error,
    connected,
    wsStatus,
    totalUnrealizedPnl,
    totalFundingEarned,
    activeCount,
    refetch: loadPositions,
    exportCSV,
  };
}
