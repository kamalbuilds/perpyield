"use client";

import { useState, useCallback } from "react";
import { usePositions, type EnrichedPosition } from "@/hooks/usePositions";
import { closePosition, setTpsl } from "@/lib/api";
import PositionTable from "@/components/PositionTable";
import PositionCard from "@/components/PositionCard";
import ClosePositionModal from "@/components/ClosePositionModal";
import TPSLModal from "@/components/TPSLModal";

function formatCurrency(n: number | undefined | null): string {
  const v = n ?? 0;
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(2)}K`;
  return `$${v.toFixed(2)}`;
}

function Skeleton({ className }: { className?: string }) {
  return <div className={`skeleton ${className ?? ""}`} />;
}

function StatCard({
  label,
  value,
  accent,
  loading,
}: {
  label: string;
  value: string | null;
  accent?: "green" | "red";
  loading: boolean;
}) {
  const valueColor =
    accent === "green"
      ? "text-accent-green"
      : accent === "red"
      ? "text-accent-red"
      : "text-foreground";

  return (
    <div className="rounded-lg border border-card-border bg-card-bg p-5">
      <p className="text-xs text-muted uppercase tracking-wider mb-2">
        {label}
      </p>
      {loading ? (
        <div className="skeleton h-8 w-24" />
      ) : (
        <p className={`text-2xl font-bold tracking-tight font-mono ${valueColor}`}>
          {value}
        </p>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const {
    positions,
    rawResponse,
    loading,
    error,
    connected,
    wsStatus,
    totalUnrealizedPnl,
    totalFundingEarned,
    activeCount,
    refetch,
    exportCSV,
  } = usePositions();

  const [closeTarget, setCloseTarget] = useState<EnrichedPosition | null>(null);
  const [closeModalOpen, setCloseModalOpen] = useState(false);
  const [positionsCollapsed, setPositionsCollapsed] = useState(false);
  const [closeLoading, setCloseLoading] = useState(false);
  const [closeError, setCloseError] = useState<string | null>(null);
  const [tpslTarget, setTpslTarget] = useState<EnrichedPosition | null>(null);
  const [tpslModalOpen, setTpslModalOpen] = useState(false);

  const handleClose = useCallback((pos: EnrichedPosition) => {
    setCloseTarget(pos);
    setCloseError(null);
    setCloseModalOpen(true);
  }, []);

  const handleCloseConfirm = useCallback(
    async (position: EnrichedPosition, closePercent: number, orderType: "market" | "limit", limitPrice?: number) => {
      setCloseLoading(true);
      setCloseError(null);
      try {
        const closeSize = Math.abs(position.size) * (closePercent / 100);
        await closePosition(
          position.symbol,
          position.side,
          closeSize.toFixed(8),
          {
            close_percent: closePercent,
            order_type: orderType,
            limit_price: limitPrice?.toString(),
          }
        );
        setCloseModalOpen(false);
        setCloseTarget(null);
        refetch();
      } catch (e) {
        setCloseError(e instanceof Error ? e.message : "Failed to close position");
      } finally {
        setCloseLoading(false);
      }
    },
    [refetch]
  );

  const handleAddMargin = useCallback((pos: EnrichedPosition) => {
    console.log("Add margin:", pos.symbol, pos.side);
  }, []);

  const handleTpSl = useCallback((pos: EnrichedPosition) => {
    setTpslTarget(pos);
    setTpslModalOpen(true);
  }, []);

  const handleTpSlConfirm = useCallback(
    async (position: EnrichedPosition, tpPrice: string | null, slPrice: string | null) => {
      await setTpsl(position.symbol, position.side, {
        tp_price: tpPrice ?? undefined,
        sl_price: slPrice ?? undefined,
      });
      refetch();
    },
    [refetch]
  );

  const vaultValue = rawResponse?.strategy_positions ? undefined : undefined;
  const pnlIsPositive = totalUnrealizedPnl >= 0;

  return (
    <div className="space-y-6">
      {error && (
        <div className="p-4 rounded-lg border border-accent-red/30 bg-accent-red/5 text-sm text-accent-red">
          {error}. Make sure the backend is running at localhost:8000.
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Active Positions"
          value={loading ? null : `${activeCount}`}
          loading={loading}
        />
        <StatCard
          label="Unrealized PnL"
          value={
            loading
              ? null
              : `${pnlIsPositive ? "+" : ""}$${totalUnrealizedPnl.toFixed(2)}`
          }
          accent={pnlIsPositive ? "green" : "red"}
          loading={loading}
        />
        <StatCard
          label="Total Funding Earned"
          value={loading ? null : formatCurrency(totalFundingEarned)}
          accent="green"
          loading={loading}
        />
        <StatCard
          label="Price Feed"
          value={loading ? null : wsStatus === "connected" ? "Live" : wsStatus === "connecting" ? "Connecting" : "Offline"}
          accent={wsStatus === "connected" ? "green" : wsStatus === "connecting" ? "yellow" : "red"}
          loading={loading}
        />
      </div>

      <div className="rounded-lg border border-card-border bg-card-bg overflow-hidden">
        <button
          onClick={() => setPositionsCollapsed(!positionsCollapsed)}
          className="w-full px-5 py-4 border-b border-card-border flex items-center justify-between hover:bg-white/[0.01] transition-colors"
        >
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-semibold">Position Management</h3>
            {!loading && activeCount > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-accent-green/10 text-accent-green">
                {activeCount} active
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {activeCount > 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  const csv = exportCSV();
                  const blob = new Blob([csv], { type: "text/csv" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "positions.csv";
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="px-2 py-1 rounded text-[10px] font-medium bg-white/5 text-muted hover:bg-white/10 hover:text-foreground transition-colors"
              >
                Export CSV
              </button>
            )}
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className={`text-muted transition-transform ${positionsCollapsed ? "" : "rotate-180"}`}
            >
              <path d="M6 9l6 6 6-6" />
            </svg>
          </div>
        </button>

        {!positionsCollapsed && (
          <>
            <div className="hidden md:block">
              <PositionTable
                positions={positions}
                loading={loading}
                connected={connected}
                onClose={handleClose}
                onAddMargin={handleAddMargin}
                onTpSl={handleTpSl}
              />
            </div>
            <div className="md:hidden p-4 space-y-3">
              {loading ? (
                Array.from({ length: 2 }).map((_, i) => (
                  <Skeleton key={i} className="h-40 w-full" />
                ))
              ) : positions.length === 0 ? (
                <div className="py-12 text-center">
                  <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-4">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted">
                      <rect x="3" y="3" width="18" height="18" rx="2" />
                      <path d="M9 12h6M12 9v6" />
                    </svg>
                  </div>
                  <p className="text-muted text-sm mb-1">No open positions</p>
                  <p className="text-muted/60 text-xs">Start a strategy to begin earning funding yield</p>
                </div>
              ) : (
                positions.map((pos, i) => (
                  <PositionCard
                    key={`${pos.symbol}-${pos.side}-${i}`}
                    position={pos}
                    index={i}
                    onClose={handleClose}
                  />
                ))
              )}
            </div>
          </>
        )}
      </div>

      <ClosePositionModal
        position={closeTarget}
        open={closeModalOpen}
        loading={closeLoading}
        error={closeError}
        onClose={() => {
          setCloseModalOpen(false);
          setCloseTarget(null);
          setCloseError(null);
        }}
        onConfirm={handleCloseConfirm}
      />

      <TPSLModal
        position={tpslTarget}
        open={tpslModalOpen}
        onClose={() => {
          setTpslModalOpen(false);
          setTpslTarget(null);
        }}
        onConfirm={handleTpSlConfirm}
      />
    </div>
  );
}
