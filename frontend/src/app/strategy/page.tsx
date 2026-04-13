"use client";

import { useState, useEffect, useCallback } from "react";
import {
  fetchStrategyStatus,
  startStrategy,
  stopStrategy,
  depositVault,
  withdrawVault,
  fetchDeltaSummary,
  type StrategyStatus,
  type DeltaSummary,
} from "@/lib/api";

function Skeleton({ className }: { className?: string }) {
  return <div className={`skeleton ${className ?? ""}`} />;
}

export default function StrategyPage() {
  const [status, setStatus] = useState<StrategyStatus | null>(null);
  const [deltaSummary, setDeltaSummary] = useState<DeltaSummary | null>(null);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Deposit/Withdraw state
  const [depositAmount, setDepositAmount] = useState("");
  const [withdrawShares, setWithdrawShares] = useState("");
  const [depositLoading, setDepositLoading] = useState(false);
  const [withdrawLoading, setWithdrawLoading] = useState(false);
  const [txMessage, setTxMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [statusData, deltaData] = await Promise.allSettled([
        fetchStrategyStatus(),
        fetchDeltaSummary(),
      ]);
      if (statusData.status === "fulfilled") {
        setStatus(statusData.value);
        setRunning(statusData.value.active_positions > 0);
      }
      if (deltaData.status === "fulfilled") {
        setDeltaSummary(deltaData.value);
      }
    } catch {
      // Silently handle errors on status poll
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  async function handleStart() {
    setActionLoading(true);
    setActionMessage(null);
    try {
      const result = await startStrategy();
      setRunning(true);
      setActionMessage({
        type: "success",
        text: `Strategy started. Status: ${result.status}`,
      });
    } catch (e) {
      setActionMessage({
        type: "error",
        text: e instanceof Error ? e.message : "Failed to start strategy",
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleStop() {
    setActionLoading(true);
    setActionMessage(null);
    try {
      const result = await stopStrategy();
      setRunning(false);
      setActionMessage({
        type: "success",
        text: `Strategy stopped. Status: ${result.status}`,
      });
    } catch (e) {
      setActionMessage({
        type: "error",
        text: e instanceof Error ? e.message : "Failed to stop strategy",
      });
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDeposit() {
    const amount = parseFloat(depositAmount);
    if (isNaN(amount) || amount <= 0) return;
    setDepositLoading(true);
    setTxMessage(null);
    try {
      await depositVault("demo", amount);
      setTxMessage({
        type: "success",
        text: `Deposited ${amount} USDC successfully`,
      });
      setDepositAmount("");
    } catch (e) {
      setTxMessage({
        type: "error",
        text: e instanceof Error ? e.message : "Deposit failed",
      });
    } finally {
      setDepositLoading(false);
    }
  }

  async function handleWithdraw() {
    const shares = parseFloat(withdrawShares);
    if (isNaN(shares) || shares <= 0) return;
    setWithdrawLoading(true);
    setTxMessage(null);
    try {
      await withdrawVault("demo", shares);
      setTxMessage({
        type: "success",
        text: `Withdrew ${shares} shares successfully`,
      });
      setWithdrawShares("");
    } catch (e) {
      setTxMessage({
        type: "error",
        text: e instanceof Error ? e.message : "Withdraw failed",
      });
    } finally {
      setWithdrawLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Strategy</h2>
        <p className="text-sm text-muted mt-1">
          Manage vault strategy and deposits
        </p>
      </div>

      {/* Vault Controls */}
      <div className="rounded-lg border border-card-border bg-card-bg p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold">Vault Controls</h3>
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs ${
              running
                ? "bg-accent-green/10 text-accent-green"
                : "bg-white/5 text-muted"
            }`}
          >
            <div
              className={`w-2 h-2 rounded-full ${
                running ? "bg-accent-green animate-pulse" : "bg-muted"
              }`}
            />
            {running ? "Running" : "Stopped"}
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={handleStart}
            disabled={actionLoading || running}
            className="px-6 py-2.5 rounded-lg text-sm font-medium bg-accent-green text-black hover:bg-accent-green/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {actionLoading && !running ? "Starting..." : "Start Vault"}
          </button>
          <button
            onClick={handleStop}
            disabled={actionLoading || !running}
            className="px-6 py-2.5 rounded-lg text-sm font-medium bg-accent-red text-white hover:bg-accent-red/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {actionLoading && running ? "Stopping..." : "Stop Vault"}
          </button>
        </div>

        {actionMessage && (
          <div
            className={`mt-3 p-3 rounded-lg text-xs ${
              actionMessage.type === "success"
                ? "bg-accent-green/10 text-accent-green border border-accent-green/20"
                : "bg-accent-red/10 text-accent-red border border-accent-red/20"
            }`}
          >
            {actionMessage.text}
          </div>
        )}
      </div>

      {/* Deposit / Withdraw */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-card-border bg-card-bg p-5">
          <h3 className="text-sm font-semibold mb-3">Deposit USDC</h3>
          <div className="flex gap-2">
            <input
              type="number"
              value={depositAmount}
              onChange={(e) => setDepositAmount(e.target.value)}
              placeholder="Amount in USDC"
              min="0"
              step="0.01"
              className="flex-1 bg-white/5 border border-card-border rounded-lg px-4 py-2.5 font-mono text-sm focus:outline-none focus:border-accent-green/50 transition-colors placeholder:text-muted/50"
            />
            <button
              onClick={handleDeposit}
              disabled={depositLoading || !depositAmount}
              className="px-5 py-2.5 rounded-lg text-sm font-medium bg-accent-green text-black hover:bg-accent-green/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {depositLoading ? "..." : "Deposit"}
            </button>
          </div>
        </div>
        <div className="rounded-lg border border-card-border bg-card-bg p-5">
          <h3 className="text-sm font-semibold mb-3">Withdraw Shares</h3>
          <div className="flex gap-2">
            <input
              type="number"
              value={withdrawShares}
              onChange={(e) => setWithdrawShares(e.target.value)}
              placeholder="Number of shares"
              min="0"
              step="0.01"
              className="flex-1 bg-white/5 border border-card-border rounded-lg px-4 py-2.5 font-mono text-sm focus:outline-none focus:border-accent-green/50 transition-colors placeholder:text-muted/50"
            />
            <button
              onClick={handleWithdraw}
              disabled={withdrawLoading || !withdrawShares}
              className="px-5 py-2.5 rounded-lg text-sm font-medium bg-accent-red text-white hover:bg-accent-red/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {withdrawLoading ? "..." : "Withdraw"}
            </button>
          </div>
        </div>
      </div>

      {txMessage && (
        <div
          className={`p-3 rounded-lg text-xs ${
            txMessage.type === "success"
              ? "bg-accent-green/10 text-accent-green border border-accent-green/20"
              : "bg-accent-red/10 text-accent-red border border-accent-red/20"
          }`}
        >
          {txMessage.text}
        </div>
      )}

      {/* Strategy Configuration (read-only) */}
      <div className="rounded-lg border border-card-border bg-card-bg p-5">
        <h3 className="text-sm font-semibold mb-4">
          Strategy Configuration
          <span className="ml-2 text-xs text-muted font-normal">(read-only)</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <ConfigItem label="Min Funding Threshold" value="0.01%" />
          <ConfigItem label="Max Leverage" value="3x" />
          <ConfigItem label="Rebalance Interval" value="5 min" />
        </div>
      </div>

      {/* Delta Summary */}
      <div className="rounded-lg border border-card-border bg-card-bg p-5">
        <h3 className="text-sm font-semibold mb-4">Delta Summary</h3>
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : deltaSummary === null ? (
          <div className="py-6 text-center text-sm text-muted">
            No delta data available. Start the strategy to see delta exposure.
          </div>
        ) : deltaSummary.positions.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted">
            No positions tracked. Delta is neutral.
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <DeltaStatCard
                label="Positions Tracked"
                value={`${deltaSummary.positions_tracked}`}
              />
              <DeltaStatCard
                label="Needing Rebalance"
                value={`${deltaSummary.positions_needing_rebalance}`}
                highlight={deltaSummary.positions_needing_rebalance > 0}
              />
              <DeltaStatCard
                label="Total Rebalances"
                value={`${deltaSummary.total_rebalances_executed}`}
              />
              <DeltaStatCard
                label="Active Strategy Positions"
                value={`${status?.active_positions ?? 0}`}
              />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-card-border text-xs text-muted uppercase tracking-wider">
                    <th className="text-left px-4 py-3">Symbol</th>
                    <th className="text-right px-4 py-3">Long Exposure</th>
                    <th className="text-right px-4 py-3">Short Exposure</th>
                    <th className="text-right px-4 py-3">Net Delta</th>
                    <th className="text-right px-4 py-3">Delta %</th>
                    <th className="text-center px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {deltaSummary.positions.map((pos) => (
                    <tr
                      key={pos.symbol}
                      className="border-b border-card-border/40 hover:bg-white/[0.02] transition-colors"
                    >
                      <td className="px-4 py-3 font-mono font-semibold">
                        {pos.symbol}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-accent-green">
                        {pos.long_notional}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-accent-red">
                        {pos.short_notional}
                      </td>
                      <td className="px-4 py-3 text-right font-mono">
                        {pos.net_delta}
                      </td>
                      <td className="px-4 py-3 text-right font-mono">
                        {pos.delta_pct}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {pos.needs_rebalance ? (
                          <span className="px-2 py-0.5 rounded text-xs bg-accent-red/10 text-accent-red">
                            Needs Rebalance
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-xs bg-accent-green/10 text-accent-green">
                            Balanced
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function ConfigItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-card-border/50 bg-white/[0.02] p-3">
      <p className="text-[10px] text-muted uppercase tracking-wider mb-1">
        {label}
      </p>
      <p className="text-sm font-mono font-semibold">{value}</p>
    </div>
  );
}

function DeltaStatCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-lg border border-card-border/50 bg-white/[0.02] p-3">
      <p className="text-[10px] text-muted uppercase tracking-wider mb-1">
        {label}
      </p>
      <p
        className={`text-lg font-bold font-mono ${
          highlight ? "text-accent-red" : "text-foreground"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
