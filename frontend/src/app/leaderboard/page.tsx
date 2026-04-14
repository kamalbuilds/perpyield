"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { fetchLeaderboard, type LeaderboardVault } from "@/lib/api";

const PERIODS = [
  { value: "7d", label: "7 Days" },
  { value: "30d", label: "30 Days" },
  { value: "all", label: "All Time" },
];

const SORT_OPTIONS = [
  { value: "return", label: "Return" },
  { value: "sharpe", label: "Sharpe Ratio" },
  { value: "tvl", label: "TVL" },
  { value: "clones", label: "Clones" },
];

function Skeleton({ className }: { className?: string }) {
  return <div className={`skeleton ${className ?? ""}`} />;
}

function RiskBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    Low: "bg-accent-green/15 text-accent-green border-accent-green/30",
    Medium: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
    High: "bg-accent-red/15 text-accent-red border-accent-red/30",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded text-[10px] font-medium border ${
        colors[level] ?? colors.Medium
      }`}
    >
      {level}
    </span>
  );
}

export default function LeaderboardPage() {
  const [vaults, setVaults] = useState<LeaderboardVault[]>([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("7d");
  const [sortBy, setSortBy] = useState("return");
  const [error, setError] = useState<string | null>(null);

  const loadLeaderboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchLeaderboard(period, sortBy);
      setVaults(data.vaults);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load leaderboard");
    } finally {
      setLoading(false);
    }
  }, [period, sortBy]);

  useEffect(() => {
    loadLeaderboard();
  }, [loadLeaderboard]);

  const getReturnValue = (vault: LeaderboardVault) => {
    if (period === "7d") return vault.return_7d;
    if (period === "30d") return vault.return_30d;
    return vault.return_30d;
  };

  return (
    <div className="space-y-6">
      <div>
        <motion.h2
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-2xl font-bold"
        >
          Leaderboard
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="text-sm text-muted mt-1"
        >
          Top performing vaults ranked by returns, risk-adjusted metrics, and popularity.
        </motion.p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted uppercase tracking-wider">Period</span>
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  period === p.value
                    ? "bg-accent-green text-black"
                    : "bg-white/5 text-muted hover:text-foreground border border-card-border"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted uppercase tracking-wider">Sort By</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-white/5 border border-card-border rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-accent-green/50"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={loadLeaderboard}
          disabled={loading}
          className="ml-auto px-4 py-1.5 rounded-lg text-xs font-medium bg-accent-green text-black hover:bg-accent-green/90 transition-colors disabled:opacity-40"
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {/* Error State */}
      {error && (
        <div className="p-4 rounded-lg border border-accent-red/30 bg-accent-red/5 text-sm text-accent-red">
          {error}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="rounded-lg border border-card-border bg-card-bg p-4">
              <div className="flex items-center gap-4">
                <Skeleton className="h-8 w-8 rounded" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-32" />
                </div>
                <Skeleton className="h-8 w-24" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && vaults.length === 0 && (
        <div className="rounded-lg border border-card-border bg-card-bg p-12 text-center">
          <div className="text-4xl mb-3 opacity-30">&#127942;</div>
          <p className="text-sm text-muted">No vaults on the leaderboard yet</p>
          <p className="text-xs text-muted/60 mt-1">
            Vaults will appear here once they have performance data
          </p>
        </div>
      )}

      {/* Vault List */}
      {!loading && !error && vaults.length > 0 && (
        <div className="space-y-3">
          {vaults.map((vault, index) => {
            const returnVal = getReturnValue(vault);
            const isPositive = returnVal >= 0;

            return (
              <motion.div
                key={vault.vault_id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                className="rounded-lg border border-card-border bg-card-bg p-4 hover:border-accent-green/30 transition-colors"
              >
                <div className="flex items-center gap-4">
                  {/* Rank */}
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm ${
                      vault.rank <= 3
                        ? "bg-accent-green/20 text-accent-green"
                        : "bg-white/5 text-muted"
                    }`}
                  >
                    {vault.rank}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold truncate">{vault.name}</h3>
                      <RiskBadge level={vault.risk_level} />
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted mt-1">
                      <span className="font-mono">{vault.strategy_name}</span>
                      <span>by {vault.creator.slice(0, 6)}...{vault.creator.slice(-4)}</span>
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="hidden md:flex items-center gap-6 text-right">
                    <div>
                      <p className="text-[10px] text-muted uppercase tracking-wider">Return</p>
                      <p
                        className={`text-sm font-bold font-mono ${
                          isPositive ? "text-accent-green" : "text-accent-red"
                        }`}
                      >
                        {isPositive ? "+" : ""}
                        {returnVal.toFixed(2)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-muted uppercase tracking-wider">Sharpe</p>
                      <p className="text-sm font-bold font-mono">{vault.sharpe_ratio.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-muted uppercase tracking-wider">TVL</p>
                      <p className="text-sm font-bold font-mono">${(vault.tvl / 1000).toFixed(1)}K</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-muted uppercase tracking-wider">Clones</p>
                      <p className="text-sm font-bold font-mono">{vault.clone_count}</p>
                    </div>
                  </div>

                  {/* Action */}
                  <button className="px-4 py-2 rounded-lg text-xs font-medium bg-white/5 text-muted hover:text-foreground hover:border-accent-green/30 border border-card-border transition-colors">
                    View
                  </button>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
