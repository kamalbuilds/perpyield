"use client";

import { useState, useEffect, useCallback } from "react";
import {
  fetchVaultStatus,
  fetchFundingRates,
  fetchPositions,
  type VaultStatus,
  type FundingRateEntry,
  type PositionsResponse,
} from "@/lib/api";

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

export default function DashboardPage() {
  const [vault, setVault] = useState<VaultStatus | null>(null);
  const [rates, setRates] = useState<FundingRateEntry[]>([]);
  const [positions, setPositions] = useState<PositionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [vaultData, ratesData, posData] = await Promise.allSettled([
        fetchVaultStatus(),
        fetchFundingRates(),
        fetchPositions(),
      ]);
      if (vaultData.status === "fulfilled") setVault(vaultData.value);
      if (ratesData.status === "fulfilled") setRates(ratesData.value);
      if (posData.status === "fulfilled") setPositions(posData.value);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Sort rates by APY descending, take top 20
  const sortedRates = [...rates]
    .sort((a, b) => Math.abs(b.annualized_apy) - Math.abs(a.annualized_apy))
    .slice(0, 20);

  const strategyPositions = positions?.strategy_positions?.positions ?? [];

  return (
    <div className="space-y-6">
      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-lg border border-accent-red/30 bg-accent-red/5 text-sm text-accent-red">
          {error}. Make sure the backend is running at localhost:8000.
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Value Locked"
          value={
            loading ? null : vault ? formatCurrency(vault.vault_value) : "$0.00"
          }
          loading={loading}
        />
        <StatCard
          label="Current APY"
          value={
            loading
              ? null
              : vault
              ? `${vault.annualized_return.toFixed(2)}%`
              : "0.00%"
          }
          accent={
            vault && vault.annualized_return >= 0 ? "green" : "red"
          }
          loading={loading}
        />
        <StatCard
          label="Total Funding Earned"
          value={
            loading
              ? null
              : positions
              ? formatCurrency(
                  positions.strategy_positions?.total_funding_earned ?? 0
                )
              : "$0.00"
          }
          accent="green"
          loading={loading}
        />
        <StatCard
          label="Active Positions"
          value={
            loading
              ? null
              : vault
              ? `${vault.active_positions}`
              : "0"
          }
          loading={loading}
        />
      </div>

      {/* Funding Rate Opportunities */}
      <div className="rounded-lg border border-card-border bg-card-bg overflow-hidden">
        <div className="px-5 py-4 border-b border-card-border flex items-center justify-between">
          <h3 className="text-sm font-semibold">Funding Rate Opportunities</h3>
          <span className="text-xs text-muted">
            {sortedRates.length} pairs shown
          </span>
        </div>
        {loading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : sortedRates.length === 0 ? (
          <div className="p-8 text-center text-muted text-sm">
            No funding rate data available. Ensure the backend is running.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-card-border text-xs text-muted uppercase tracking-wider">
                  <th className="text-left px-5 py-3">Symbol</th>
                  <th className="text-right px-4 py-3">Funding Rate</th>
                  <th className="text-right px-4 py-3">APY</th>
                  <th className="text-right px-4 py-3">Mark Price</th>
                  <th className="text-right px-4 py-3">Open Interest</th>
                  <th className="text-right px-4 py-3">Volume 24h</th>
                  <th className="text-right px-5 py-3">Max Leverage</th>
                </tr>
              </thead>
              <tbody>
                {sortedRates.map((r) => {
                  const isPositive = r.funding_rate >= 0;
                  const color = isPositive
                    ? "text-accent-green"
                    : "text-accent-red";
                  return (
                    <tr
                      key={r.symbol}
                      className="border-b border-card-border/40 hover:bg-white/[0.02] transition-colors"
                    >
                      <td className="px-5 py-3 font-mono font-semibold">
                        {r.symbol}
                      </td>
                      <td className={`px-4 py-3 text-right font-mono ${color}`}>
                        {isPositive ? "+" : ""}
                        {(r.funding_rate * 100).toFixed(4)}%
                      </td>
                      <td
                        className={`px-4 py-3 text-right font-mono font-semibold ${color}`}
                      >
                        {isPositive ? "+" : ""}
                        {r.annualized_apy.toFixed(2)}%
                      </td>
                      <td className="px-4 py-3 text-right font-mono">
                        $
                        {r.mark_price.toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 4,
                        })}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-muted">
                        {formatCurrency(r.open_interest)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-muted">
                        {formatCurrency(r.volume_24h)}
                      </td>
                      <td className="px-5 py-3 text-right font-mono text-muted">
                        {r.max_leverage}x
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Active Positions */}
      <div className="rounded-lg border border-card-border bg-card-bg overflow-hidden">
        <div className="px-5 py-4 border-b border-card-border">
          <h3 className="text-sm font-semibold">Active Positions</h3>
        </div>
        {loading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : strategyPositions.length === 0 ? (
          <div className="p-8 text-center text-muted text-sm">
            No active positions
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-card-border text-xs text-muted uppercase tracking-wider">
                  <th className="text-left px-5 py-3">Symbol</th>
                  <th className="text-left px-4 py-3">Side</th>
                  <th className="text-right px-4 py-3">Size</th>
                  <th className="text-right px-4 py-3">Entry Price</th>
                  <th className="text-right px-4 py-3">Entry Funding</th>
                  <th className="text-right px-5 py-3">Funding Earned</th>
                </tr>
              </thead>
              <tbody>
                {strategyPositions.map((p, i) => (
                  <tr
                    key={`${p.symbol}-${p.side}-${i}`}
                    className="border-b border-card-border/40 hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="px-5 py-3 font-mono font-semibold">
                      {p.symbol}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          p.side === "long"
                            ? "bg-accent-green/10 text-accent-green"
                            : "bg-accent-red/10 text-accent-red"
                        }`}
                      >
                        {p.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {p.size.toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      ${p.entry_price.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-muted">
                      {(p.entry_funding_rate * 100).toFixed(4)}%
                    </td>
                    <td className="px-5 py-3 text-right font-mono text-accent-green">
                      +${p.cumulative_funding.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
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
