"use client";

import { useState, useEffect, useCallback } from "react";
import {
  fetchCreatorDashboard,
  withdrawCreatorFees,
  type CreatorDashboard,
} from "@/lib/api";

function Skeleton({ className }: { className?: string }) {
  return <div className={`skeleton ${className ?? ""}`} />;
}

const DEFAULT_ADDRESS = "creator_demo";

export default function CreatorDashboardPage() {
  const [creatorAddress, setCreatorAddress] = useState(DEFAULT_ADDRESS);
  const [inputAddress, setInputAddress] = useState(DEFAULT_ADDRESS);
  const [data, setData] = useState<CreatorDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [withdrawLoading, setWithdrawLoading] = useState(false);
  const [withdrawMessage, setWithdrawMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchCreatorDashboard(creatorAddress);
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load creator dashboard");
    } finally {
      setLoading(false);
    }
  }, [creatorAddress]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleWithdraw() {
    if (!data || data.fee_earnings.claimable <= 0) return;
    setWithdrawLoading(true);
    setWithdrawMessage(null);
    try {
      const result = await withdrawCreatorFees(creatorAddress);
      setWithdrawMessage({
        type: "success",
        text: `Withdrawn $${result.amount.toFixed(6)}. Remaining claimable: $${result.remaining_claimable.toFixed(6)}`,
      });
      await loadData();
    } catch (e) {
      setWithdrawMessage({
        type: "error",
        text: e instanceof Error ? e.message : "Withdrawal failed",
      });
    } finally {
      setWithdrawLoading(false);
    }
  }

  function handleAddressSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (inputAddress.trim()) {
      setCreatorAddress(inputAddress.trim());
    }
  }

  if (loading && !data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">Creator Dashboard</h2>
          <p className="text-sm text-muted mt-1">
            Track your vault earnings, AUM, and fee income.
          </p>
        </div>
        <form onSubmit={handleAddressSubmit} className="flex gap-2">
          <input
            type="text"
            value={inputAddress}
            onChange={(e) => setInputAddress(e.target.value)}
            placeholder="Creator address"
            className="px-3 py-2 rounded-lg text-sm bg-white/5 border border-card-border text-foreground placeholder-muted focus:outline-none focus:border-accent-green/50"
          />
          <button
            type="submit"
            className="px-4 py-2 rounded-lg text-sm font-medium border border-card-border bg-white/5 text-muted hover:text-foreground hover:border-accent-green/30 transition-colors"
          >
            Load
          </button>
        </form>
      </div>

      {error && (
        <div className="p-4 rounded-lg border border-accent-red/30 bg-accent-red/5 text-sm text-accent-red">
          {error}. Make sure the backend is running.
        </div>
      )}

      {withdrawMessage && (
        <div
          className={`p-3 rounded-lg text-xs ${
            withdrawMessage.type === "success"
              ? "bg-accent-green/10 text-accent-green border border-accent-green/20"
              : "bg-accent-red/10 text-accent-red border border-accent-red/20"
          }`}
        >
          {withdrawMessage.text}
        </div>
      )}

      {data && (
        <>
          {/* Key Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <CreatorStatCard
              label="AUM"
              value={`$${data.aum.toFixed(2)}`}
              sublabel="Assets Under Management"
            />
            <CreatorStatCard
              label="Depositors"
              value={data.depositor_count.toString()}
              sublabel="Unique depositors"
            />
            <CreatorStatCard
              label="Total Fees Earned"
              value={`$${data.fee_earnings.total_earned.toFixed(6)}`}
              sublabel={`$${data.fee_earnings.daily_average.toFixed(4)}/day avg`}
              highlight
            />
            <CreatorStatCard
              label="Claimable"
              value={`$${data.fee_earnings.claimable.toFixed(6)}`}
              sublabel={`$${data.fee_earnings.withdrawn.toFixed(4)} withdrawn`}
              highlight={data.fee_earnings.claimable > 0}
            />
          </div>

          {/* Fee Breakdown */}
          <div className="rounded-lg border border-card-border bg-card-bg p-5">
            <h3 className="text-sm font-semibold mb-4">Fee Earnings Breakdown</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <FeeBreakdownCard
                label="Management Fees"
                earned={data.fee_earnings.management_fees_earned}
                rate={data.fee_structure.management_fee_annual_pct}
                description="0.5% annually, charged daily"
              />
              <FeeBreakdownCard
                label="Performance Fees"
                earned={data.fee_earnings.performance_fees_earned}
                rate={data.fee_structure.performance_fee_pct}
                description="10% of profits above HWM"
              />
              <FeeBreakdownCard
                label="Protocol Fees"
                earned={data.protocol_fees.total_earned}
                rate={data.fee_structure.protocol_fee_pct}
                description="0.5% of total fees to treasury"
              />
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-card-border">
              <div>
                <p className="text-xs text-muted">High Water Mark</p>
                <p className="text-sm font-mono font-bold">
                  ${data.high_water_mark.toFixed(2)}
                </p>
              </div>
              <button
                onClick={handleWithdraw}
                disabled={withdrawLoading || data.fee_earnings.claimable <= 0}
                className="px-6 py-2.5 rounded-lg text-sm font-medium bg-accent-green text-black hover:bg-accent-green/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {withdrawLoading ? "Withdrawing..." : `Claim $${data.fee_earnings.claimable.toFixed(6)}`}
              </button>
            </div>
          </div>

          {/* Vault Info */}
          <div className="rounded-lg border border-card-border bg-card-bg p-5">
            <h3 className="text-sm font-semibold mb-4">Vault Info</h3>
            <div className="space-y-3">
              <InfoRow label="Vault" value={data.vault_name} />
              <InfoRow label="Strategy" value={`${data.strategy_name} (${data.strategy_id})`} />
              <InfoRow label="Total Deposited" value={`$${data.total_deposited.toFixed(2)}`} />
              <InfoRow label="Status" value={data.vault_active ? "Active" : "Inactive"} />
            </div>
          </div>

          {/* Recent Fee Charges */}
          <div className="rounded-lg border border-card-border bg-card-bg p-5">
            <h3 className="text-sm font-semibold mb-4">Recent Fee Charges</h3>
            {data.recent_fee_charges.length === 0 ? (
              <p className="text-xs text-muted text-center py-4">
                No fee charges yet. Fees are charged daily during strategy cycles.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-card-border">
                      <th className="text-left py-2 text-muted font-medium">Time</th>
                      <th className="text-right py-2 text-muted font-medium">Vault Value</th>
                      <th className="text-right py-2 text-muted font-medium">Days</th>
                      <th className="text-right py-2 text-muted font-medium">Mgmt Fee</th>
                      <th className="text-right py-2 text-muted font-medium">Perf Fee</th>
                      <th className="text-right py-2 text-muted font-medium">Protocol</th>
                      <th className="text-right py-2 text-muted font-medium">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_fee_charges.slice(-10).reverse().map((charge, i) => (
                      <tr key={i} className="border-b border-card-border/30">
                        <td className="py-2 text-muted">
                          {new Date(charge.timestamp).toLocaleDateString()}
                        </td>
                        <td className="py-2 text-right font-mono">${charge.vault_value.toFixed(2)}</td>
                        <td className="py-2 text-right font-mono">{charge.days_charged.toFixed(1)}</td>
                        <td className="py-2 text-right font-mono">${charge.management_fee.toFixed(6)}</td>
                        <td className="py-2 text-right font-mono">${charge.performance_fee.toFixed(6)}</td>
                        <td className="py-2 text-right font-mono">${charge.protocol_fee.toFixed(6)}</td>
                        <td className="py-2 text-right font-mono font-bold">${charge.total_fee.toFixed(6)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function CreatorStatCard({
  label,
  value,
  sublabel,
  highlight = false,
}: {
  label: string;
  value: string;
  sublabel?: string;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-lg border border-card-border bg-card-bg p-4">
      <p className="text-[10px] text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-lg font-bold font-mono ${highlight ? "text-accent-green" : "text-foreground"}`}>
        {value}
      </p>
      {sublabel && <p className="text-[10px] text-muted">{sublabel}</p>}
    </div>
  );
}

function FeeBreakdownCard({
  label,
  earned,
  rate,
  description,
}: {
  label: string;
  earned: number;
  rate: string;
  description: string;
}) {
  return (
    <div className="rounded-md border border-card-border/50 bg-white/[0.02] p-3">
      <p className="text-[10px] text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className="text-base font-bold font-mono text-accent-green">${earned.toFixed(6)}</p>
      <p className="text-[10px] text-muted mt-1">{rate} rate</p>
      <p className="text-[10px] text-muted">{description}</p>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-card-border/50 last:border-0">
      <span className="text-sm text-muted">{label}</span>
      <span className="text-sm font-mono font-medium">{value}</span>
    </div>
  );
}
