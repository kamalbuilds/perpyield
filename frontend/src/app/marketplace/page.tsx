"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useWallet } from "@solana/wallet-adapter-react";
import {
  fetchVaultMarketplace,
  cloneVault,
  type FeaturedVault,
  type VaultMarketplaceResponse,
} from "@/lib/api";

function Skeleton({ className }: { className?: string }) {
  return <div className={`skeleton ${className ?? ""}`} />;
}

const RISK_COLORS: Record<string, string> = {
  Low: "bg-accent-green/15 text-accent-green border-accent-green/30",
  Medium: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  High: "bg-accent-red/15 text-accent-red border-accent-red/30",
};

const RISK_ICONS: Record<string, string> = {
  Low: "\u25CF",
  Medium: "\u25CF\u25CF",
  High: "\u25CF\u25CF\u25CF",
};

const STRATEGY_ICONS: Record<string, string> = {
  delta_neutral: "\u2696",
  momentum_swing: "\u2191\u2193",
  mean_reversion: "\u21BA",
  volatility_breakout: "\u26A1",
};

export default function MarketplacePage() {
  const { publicKey } = useWallet();
  const [data, setData] = useState<VaultMarketplaceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterRisk, setFilterRisk] = useState<string>("All");
  const [cloneLoading, setCloneLoading] = useState<string | null>(null);
  const [cloneMessage, setCloneMessage] = useState<{
    vaultId: string;
    type: "success" | "error";
    text: string;
  } | null>(null);

  const loadData = useCallback(async () => {
    try {
      const result = await fetchVaultMarketplace();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load marketplace");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const vaults = data?.featured_vaults ?? [];
  const filtered = filterRisk === "All" ? vaults : vaults.filter((v) => v.risk_level === filterRisk);

  async function handleClone(vault: FeaturedVault) {
    if (!publicKey) {
      setCloneMessage({ vaultId: vault.vault_id, type: "error", text: "Connect your wallet to clone" });
      return;
    }
    setCloneLoading(vault.vault_id);
    setCloneMessage(null);
    try {
      const result = await cloneVault(
        `${vault.vault_id}-clone-${Date.now()}`,
        publicKey.toBase58(),
        `My ${vault.name}`,
        vault.description
      );
      setCloneMessage({
        vaultId: vault.vault_id,
        type: "success",
        text: `Vault cloned! New vault: ${result.template?.vault_id ?? "created"}`,
      });
    } catch (e) {
      setCloneMessage({
        vaultId: vault.vault_id,
        type: "error",
        text: e instanceof Error ? e.message : "Clone failed",
      });
    } finally {
      setCloneLoading(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Strategy Marketplace</h2>
        <p className="text-sm text-muted mt-1">
          Browse featured vaults. Clone one to get started instantly.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-lg border border-accent-red/30 bg-accent-red/5 text-sm text-accent-red">
          {error}. Make sure the backend is running at localhost:8000.
        </div>
      )}

      {cloneMessage && (
        <div
          className={`p-3 rounded-lg text-xs ${
            cloneMessage.type === "success"
              ? "bg-accent-green/10 text-accent-green border border-accent-green/20"
              : "bg-accent-red/10 text-accent-red border border-accent-red/20"
          }`}
        >
          {cloneMessage.text}
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted uppercase tracking-wider mr-2">Risk Level:</span>
        {["All", "Low", "Medium", "High"].map((level) => (
          <button
            key={level}
            onClick={() => setFilterRisk(level)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filterRisk === level
                ? "bg-accent-green/15 text-accent-green border border-accent-green/30"
                : "bg-white/5 text-muted border border-card-border hover:text-foreground"
            }`}
          >
            {level}
          </button>
        ))}
        <span className="ml-auto text-xs text-muted">
          {filtered.length} vault{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Vault Cards Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-lg border border-card-border bg-card-bg p-5">
              <Skeleton className="h-6 w-48 mb-3" />
              <Skeleton className="h-4 w-full mb-2" />
              <Skeleton className="h-4 w-3/4 mb-4" />
              <div className="flex gap-2">
                <Skeleton className="h-8 w-24" />
                <Skeleton className="h-8 w-28" />
              </div>
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-12 text-center text-sm text-muted">
          No vaults found for the selected risk level.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((vault) => (
            <VaultCard
              key={vault.vault_id}
              vault={vault}
              onClone={handleClone}
              cloneLoading={cloneLoading === vault.vault_id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function VaultCard({
  vault,
  onClone,
  cloneLoading,
}: {
  vault: FeaturedVault;
  onClone: (v: FeaturedVault) => void;
  cloneLoading: boolean;
}) {
  const riskColor = RISK_COLORS[vault.risk_level] ?? RISK_COLORS.Medium;
  const riskIcon = RISK_ICONS[vault.risk_level] ?? "\u25CF";
  const strategyIcon = STRATEGY_ICONS[vault.strategy_id] ?? "\u25A0";

  return (
    <div className="rounded-lg border border-card-border bg-card-bg p-5 hover:border-card-border/80 transition-colors group">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{strategyIcon}</span>
          <h3 className="text-base font-bold">{vault.name}</h3>
        </div>
        <span className={`px-2.5 py-1 rounded-md text-[10px] font-semibold border ${riskColor}`}>
          {riskIcon} {vault.risk_level}
        </span>
      </div>

      <p className="text-xs text-muted mb-3">{vault.description}</p>

      <div className="flex items-center gap-2 mb-3">
        <span className="px-2 py-0.5 rounded text-[10px] bg-white/5 text-muted border border-card-border">
          {vault.strategy_name}
        </span>
        <span className="px-2 py-0.5 rounded text-[10px] bg-accent-green/10 text-accent-green border border-accent-green/20">
          10% perf, 0.5% mgmt
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="rounded-md border border-card-border/50 bg-white/[0.02] p-2.5">
          <p className="text-[10px] text-muted uppercase tracking-wider mb-0.5">APY Range</p>
          <p className="text-sm font-bold font-mono text-accent-green">{vault.expected_apy}</p>
        </div>
        <div className="rounded-md border border-card-border/50 bg-white/[0.02] p-2.5">
          <p className="text-[10px] text-muted uppercase tracking-wider mb-0.5">7d Perf</p>
          <p className="text-sm font-bold font-mono text-foreground">{vault.performance_7d}</p>
        </div>
        <div className="rounded-md border border-card-border/50 bg-white/[0.02] p-2.5">
          <p className="text-[10px] text-muted uppercase tracking-wider mb-0.5">30d Perf</p>
          <p className="text-sm font-bold font-mono text-foreground">{vault.performance_30d}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 text-[10px] text-muted mb-4">
        <span>by {vault.creator}</span>
        <span className="mx-1">|</span>
        <span>{vault.clone_count} clones</span>
      </div>

      <div className="flex gap-2">
        <Link
          href={`/vault/${encodeURIComponent(vault.vault_id)}?strategy=${vault.strategy_id}`}
          className="px-4 py-2 rounded-lg text-xs font-medium border border-card-border bg-white/5 text-muted hover:text-foreground hover:border-accent-green/30 transition-colors"
        >
          View Details
        </Link>
        <Link
          href={`/backtest?strategy=${vault.strategy_id}&symbol=BTC`}
          className="px-4 py-2 rounded-lg text-xs font-medium border border-accent-green/30 bg-accent-green/5 text-accent-green hover:bg-accent-green/10 transition-colors"
        >
          Backtest
        </Link>
        <button
          onClick={() => onClone(vault)}
          disabled={cloneLoading}
          className="px-4 py-2 rounded-lg text-xs font-medium bg-accent-green text-black hover:bg-accent-green/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {cloneLoading ? "Cloning..." : "Clone Vault"}
        </button>
      </div>
    </div>
  );
}
