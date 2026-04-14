"use client";

import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  fetchStrategyInfo,
  fetchStrategyBacktest,
  fetchVaultStatus,
  switchStrategy,
  type StrategyInfoResponse,
  type StrategyBacktestResponse,
  type VaultStatus,
} from "@/lib/api";

const STRATEGY_ICONS: Record<string, string> = {
  delta_neutral: "⚖",
  momentum_swing: "↗",
  mean_reversion: "↺",
  volatility_breakout: "⚡",
};

const RISK_COLORS: Record<string, string> = {
  Low: "text-accent-green",
  Medium: "text-yellow-400",
  High: "text-accent-red",
};

export default function VaultDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const vaultId = decodeURIComponent((params.id as string) || "");
  const strategyId = searchParams.get("strategy") || "delta_neutral";

  const [strategy, setStrategy] = useState<StrategyInfoResponse | null>(null);
  const [vault, setVault] = useState<VaultStatus | null>(null);
  const [backtest, setBacktest] = useState<StrategyBacktestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "backtest" | "config">("overview");
  const [switchLoading, setSwitchLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, [strategyId]);

  async function loadData() {
    setLoading(true);
    try {
      const [strategyData, vaultData] = await Promise.all([
        fetchStrategyInfo(strategyId),
        fetchVaultStatus(),
      ]);
      setStrategy(strategyData);
      setVault(vaultData);

      // Load backtest
      try {
        const backtestData = await fetchStrategyBacktest({
          strategy_id: strategyId,
          symbol: "BTC",
          days: 30,
        });
        setBacktest(backtestData);
      } catch {
        // Backtest might fail, that's ok
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load vault data");
    } finally {
      setLoading(false);
    }
  }

  async function handleSwitchStrategy() {
    setSwitchLoading(true);
    try {
      await switchStrategy(strategyId);
      await loadData();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Switch failed");
    } finally {
      setSwitchLoading(false);
    }
  }

  if (loading) {
    return <VaultDetailSkeleton />;
  }

  if (error || !strategy) {
    return (
      <div className="space-y-4">
        <div className="p-4 rounded-lg border border-accent-red/30 bg-accent-red/5 text-accent-red">
          {error || "Strategy not found"}
        </div>
        <Link href="/marketplace" className="text-accent-green hover:underline">
          ← Back to Marketplace
        </Link>
      </div>
    );
  }

  const icon = STRATEGY_ICONS[strategyId] || "📊";
  const riskColor = RISK_COLORS[strategy.risk_level] || "text-muted";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link href="/marketplace" className="text-xs text-muted hover:text-accent-green mb-2 block">
            ← Back to Marketplace
          </Link>
          <div className="flex items-center gap-3 mb-2">
            <span className="text-3xl">{icon}</span>
            <h1 className="text-2xl font-bold">{strategy.name}</h1>
          </div>
          <p className="text-sm text-muted max-w-2xl">{strategy.description}</p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/"
            className="px-4 py-2 rounded-lg text-sm font-medium border border-card-border bg-white/5 text-muted hover:text-foreground hover:border-accent-green/30 transition-colors"
          >
            View Dashboard
          </Link>
          <button
            onClick={handleSwitchStrategy}
            disabled={switchLoading}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-accent-green text-black hover:bg-accent-green/90 transition-colors disabled:opacity-40"
          >
            {switchLoading ? "Switching..." : "Activate Strategy"}
          </button>
        </div>
      </div>

      {/* Key Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Risk Level" value={strategy.risk_level} color={riskColor} />
        <StatCard label="Expected APY" value={strategy.expected_apy} color="text-accent-green" />
        <StatCard label="Indicators" value={strategy.indicators.length.toString()} valueLabel={strategy.indicators.join(", ")} />
        <StatCard
          label="Your Position"
          value={vault ? `$${vault.vault_value?.toFixed(2) || "0.00"}` : "--"}
          color="text-accent-green"
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-card-border">
        <div className="flex gap-4">
          {(["overview", "backtest", "config"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 text-sm font-medium capitalize transition-colors relative ${
                activeTab === tab ? "text-accent-green" : "text-muted hover:text-foreground"
              }`}
            >
              {tab}
              {activeTab === tab && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent-green rounded-full" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="min-h-[300px]">
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* Indicators */}
            <div className="rounded-lg border border-card-border bg-card-bg p-5">
              <h3 className="text-sm font-semibold mb-4">Technical Indicators</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {strategy.indicators.map((indicator) => (
                  <div
                    key={indicator}
                    className="px-3 py-2 rounded-md bg-white/5 border border-card-border text-xs text-center"
                  >
                    {indicator}
                  </div>
                ))}
              </div>
            </div>

            {/* Strategy Description */}
            <div className="rounded-lg border border-card-border bg-card-bg p-5">
              <h3 className="text-sm font-semibold mb-3">How This Strategy Works</h3>
              <div className="space-y-3 text-sm text-muted">
                <p>
                  This strategy automatically scans Pacifica markets for opportunities and executes
                  trades based on the configured technical indicators.
                </p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>Continuous market scanning for entry signals</li>
                  <li>Automatic position sizing based on risk parameters</li>
                  <li>Built-in stop-loss and take-profit management</li>
                  <li>24/7 automated execution via Pacifica SDK</li>
                </ul>
              </div>
            </div>

            {/* Deposit CTA */}
            <div className="rounded-lg border border-accent-green/30 bg-accent-green/5 p-5 text-center">
              <h3 className="text-base font-semibold mb-2">Ready to start earning?</h3>
              <p className="text-sm text-muted mb-4">
                Deposit into this vault to begin automated trading with {strategy.name}
              </p>
              <Link
                href="/"
                className="inline-block px-6 py-2.5 rounded-lg text-sm font-medium bg-accent-green text-black hover:bg-accent-green/90 transition-colors"
              >
                Deposit Now
              </Link>
            </div>
          </div>
        )}

        {activeTab === "backtest" && (
          <div className="space-y-4">
            {backtest ? (
              <>
                <div className="rounded-lg border border-card-border bg-card-bg p-5">
                  <h3 className="text-sm font-semibold mb-4">Backtest Results (BTC, 30 days)</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <BacktestStat label="Total Return" value={`${backtest.backtest.total_return_pct?.toFixed(2) || 0}%`} />
                    <BacktestStat
                      label="Annualized APY"
                      value={`${backtest.backtest.annualized_apy?.toFixed(2) || 0}%`}
                      highlight
                    />
                    <BacktestStat label="Sharpe Ratio" value={backtest.backtest.sharpe_ratio?.toFixed(2) || "0.00"} />
                    <BacktestStat label="Max Drawdown" value={`${backtest.backtest.max_drawdown_pct?.toFixed(2) || 0}%`} />
                    <BacktestStat label="Win Rate" value={`${backtest.backtest.win_rate?.toFixed(1) || 0}%`} />
                    <BacktestStat label="Total Trades" value={backtest.backtest.total_trades?.toString() || "0"} />
                    <BacktestStat label="Net PnL" value={`$${backtest.backtest.net_pnl?.toFixed(2) || 0}`} />
                    <BacktestStat label="Trading Fees" value={`$${backtest.backtest.trading_fees?.toFixed(2) || 0}`} />
                  </div>
                </div>

                {backtest.equity_curve_sample && backtest.equity_curve_sample.length > 0 && (
                  <div className="rounded-lg border border-card-border bg-card-bg p-5">
                    <h3 className="text-sm font-semibold mb-4">Equity Curve (Sample)</h3>
                    <div className="h-40 flex items-end gap-1">
                      {backtest.equity_curve_sample.map((point: any, i: number) => {
                        const value = typeof point === "number" ? point : point.equity;
                        const height = `${Math.min(100, Math.max(5, (value / 12000) * 100))}%`;
                        return (
                          <div
                            key={i}
                            className="flex-1 bg-accent-green/30 hover:bg-accent-green/50 transition-colors rounded-sm"
                            style={{ height }}
                            title={`$${value?.toFixed(2) || 0}`}
                          />
                        );
                      })}
                    </div>
                    <p className="text-xs text-muted mt-2 text-center">
                      Sample of equity curve over backtest period
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="py-12 text-center text-sm text-muted">
                Backtest data not available. Run a backtest to see historical performance.
              </div>
            )}
          </div>
        )}

        {activeTab === "config" && (
          <div className="rounded-lg border border-card-border bg-card-bg p-5">
            <h3 className="text-sm font-semibold mb-4">Default Configuration</h3>
            <div className="space-y-3">
              {Object.entries(strategy.config_defaults || {}).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between py-2 border-b border-card-border/50 last:border-0">
                  <span className="text-sm text-muted capitalize">{key.replace(/_/g, " ")}</span>
                  <span className="text-sm font-mono font-medium">{value}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted mt-4">
              These are the default parameters. When you activate this strategy, you can customize these values.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  valueLabel,
  color = "text-foreground",
}: {
  label: string;
  value: string;
  valueLabel?: string;
  color?: string;
}) {
  return (
    <div className="rounded-lg border border-card-border bg-card-bg p-4">
      <p className="text-[10px] text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-lg font-bold font-mono ${color}`}>{value}</p>
      {valueLabel && <p className="text-[10px] text-muted truncate">{valueLabel}</p>}
    </div>
  );
}

function BacktestStat({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="rounded-md border border-card-border/50 bg-white/[0.02] p-3">
      <p className="text-[10px] text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-sm font-bold font-mono ${highlight ? "text-accent-green" : "text-foreground"}`}>
        {value}
      </p>
    </div>
  );
}

function VaultDetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="h-4 w-32 skeleton" />
        <div className="h-8 w-64 skeleton" />
        <div className="h-4 w-full max-w-xl skeleton" />
      </div>
      <div className="grid grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-20 skeleton rounded-lg" />
        ))}
      </div>
      <div className="h-96 skeleton rounded-lg" />
    </div>
  );
}
