"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import StrategyChart from "@/components/StrategyChart";
import PerformanceCompare from "@/components/PerformanceCompare";
import BacktestChart from "@/components/BacktestChart";
import FundingChart from "@/components/FundingChart";
import {
  fetchVaultStatus,
  fetchFundingRates,
  fetchBacktest,
  type VaultStatus,
  type FundingRateEntry,
  type BacktestResult,
} from "@/lib/api";

function Skeleton({ className }: { className?: string }) {
  return <div className={`skeleton ${className ?? ""}`} />;
}

export default function AnalyticsPage() {
  const [vault, setVault] = useState<VaultStatus | null>(null);
  const [rates, setRates] = useState<FundingRateEntry[]>([]);
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const dashboardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function load() {
      try {
        const results = await Promise.allSettled([
          fetchVaultStatus(),
          fetchFundingRates(),
        ]);
        if (results[0].status === "fulfilled") setVault(results[0].value);
        if (results[1].status === "fulfilled") setRates(results[1].value);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleExportAll = useCallback(() => {
    const el = dashboardRef.current;
    if (!el) return;
    const svgs = el.querySelectorAll("svg");
    if (svgs.length === 0) return;

    const svg = svgs[0];
    const svgData = new XMLSerializer().serializeToString(svg);
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      canvas.width = img.width * 2;
      canvas.height = img.height * 2;
      ctx.scale(2, 2);
      ctx.fillStyle = "#0a0a0a";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      const a = document.createElement("a");
      a.download = "perpyield-analytics.png";
      a.href = canvas.toDataURL("image/png");
      a.click();
    };
    img.src =
      "data:image/svg+xml;base64," +
      btoa(unescape(encodeURIComponent(svgData)));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">Analytics</h2>
          <p className="text-sm text-muted mt-1">
            Strategy performance, backtesting, and funding rate analytics
          </p>
        </div>
        <button
          onClick={handleExportAll}
          className="px-4 py-2 rounded-lg text-sm font-medium border border-card-border bg-white/5 text-muted hover:text-foreground hover:border-accent-green/30 transition-colors flex items-center gap-2"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
          </svg>
          Export All PNG
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-lg border border-accent-red/30 bg-accent-red/5 text-sm text-accent-red">
          {error}
        </div>
      )}

      <div ref={dashboardRef} className="space-y-6">
        <StrategyChart vault={vault} loading={loading} />

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <PerformanceCompare />
          <FundingChart rates={rates} loading={loading} />
        </div>

        <BacktestChart backtest={backtest} loading={loading} />
      </div>
    </div>
  );
}
