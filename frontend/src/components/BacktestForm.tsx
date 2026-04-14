"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  fetchStrategyMarketplace,
  fetchStrategyInfo,
  type StrategyMarketplaceEntry,
  type StrategyInfoResponse,
} from "@/lib/api";

const STRATEGIES: { id: string; name: string; icon: string; desc: string }[] = [
  { id: "delta_neutral", name: "Delta Neutral", icon: "\u2696", desc: "Collect funding with zero directional exposure" },
  { id: "momentum_swing", name: "Momentum Swing", icon: "\u2191\u2193", desc: "Ride trends with EMA crossover signals" },
  { id: "mean_reversion", name: "Mean Reversion", icon: "\u21BA", desc: "Profit from price returning to mean" },
  { id: "volatility_breakout", name: "Volatility Breakout", icon: "\u26A1", desc: "Capture explosive ATR-based moves" },
];

const SYMBOLS = ["BTC", "ETH", "SOL", "DOGE", "ARB", "AVAX", "MATIC", "LINK", "UNI", "AAVE"];
const DAY_OPTIONS = [7, 30, 60, 90, 180];

export interface BacktestFormValues {
  strategyId: string;
  symbol: string;
  days: number;
  initialCapital: number;
  config: Record<string, unknown>;
}

interface BacktestFormProps {
  onSubmit: (values: BacktestFormValues) => void;
  loading: boolean;
  defaultValues?: Partial<BacktestFormValues>;
}

export default function BacktestForm({ onSubmit, loading, defaultValues }: BacktestFormProps) {
  const [strategyId, setStrategyId] = useState(defaultValues?.strategyId ?? "delta_neutral");
  const [symbol, setSymbol] = useState(defaultValues?.symbol ?? "BTC");
  const [days, setDays] = useState(defaultValues?.days ?? 30);
  const [initialCapital, setInitialCapital] = useState(defaultValues?.initialCapital ?? 10000);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [strategyInfo, setStrategyInfo] = useState<StrategyInfoResponse | null>(null);
  const [customSymbol, setCustomSymbol] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchStrategyInfo(strategyId)
      .then((info) => {
        if (!cancelled) {
          setStrategyInfo(info);
          setConfig(info.config_defaults ?? {});
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [strategyId]);

  const selectedStrategy = STRATEGIES.find((s) => s.id === strategyId);
  const activeSymbol = customSymbol || symbol;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({ strategyId, symbol: activeSymbol, days, initialCapital, config });
  }

  function updateConfig(key: string, value: unknown) {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label className="block text-xs text-muted uppercase tracking-wider mb-3 font-medium">Strategy</label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {STRATEGIES.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setStrategyId(s.id)}
              className={`flex items-center gap-3 p-3.5 rounded-lg border text-left transition-all ${
                strategyId === s.id
                  ? "border-accent-green/40 bg-accent-green/5 ring-1 ring-accent-green/20"
                  : "border-card-border bg-white/[0.02] hover:border-card-border/80 hover:bg-white/[0.04]"
              }`}
            >
              <span className="text-xl">{s.icon}</span>
              <div>
                <p className={`text-sm font-semibold ${strategyId === s.id ? "text-accent-green" : "text-foreground"}`}>{s.name}</p>
                <p className="text-[10px] text-muted leading-tight mt-0.5">{s.desc}</p>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-muted uppercase tracking-wider mb-2 font-medium">Symbol</label>
          <div className="flex gap-2">
            <select
              value={SYMBOLS.includes(symbol) ? symbol : "__custom"}
              onChange={(e) => {
                if (e.target.value !== "__custom") {
                  setSymbol(e.target.value);
                  setCustomSymbol("");
                }
              }}
              className="flex-1 bg-white/5 border border-card-border rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:border-accent-green/50 transition-colors appearance-none cursor-pointer"
            >
              {SYMBOLS.map((s) => (
                <option key={s} value={s}>{s}-PERP</option>
              ))}
              <option value="__custom">Custom...</option>
            </select>
            {(!SYMBOLS.includes(symbol) || symbol === "__custom") && (
              <input
                type="text"
                value={customSymbol}
                onChange={(e) => setCustomSymbol(e.target.value.toUpperCase())}
                placeholder="e.g. OP"
                className="w-24 bg-white/5 border border-card-border rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:border-accent-green/50 transition-colors placeholder:text-muted/50"
              />
            )}
          </div>
        </div>

        <div>
          <label className="block text-xs text-muted uppercase tracking-wider mb-2 font-medium">Period</label>
          <div className="flex gap-1.5">
            {DAY_OPTIONS.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDays(d)}
                className={`flex-1 py-2.5 rounded-lg text-xs font-mono font-medium transition-all ${
                  days === d
                    ? "bg-accent-green/15 text-accent-green border border-accent-green/30"
                    : "bg-white/5 text-muted border border-card-border hover:text-foreground"
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
      </div>

      <div>
        <label className="block text-xs text-muted uppercase tracking-wider mb-2 font-medium">Initial Capital (USDC)</label>
        <input
          type="number"
          value={initialCapital}
          onChange={(e) => setInitialCapital(Number(e.target.value))}
          min={100}
          step={100}
          className="w-full sm:w-64 bg-white/5 border border-card-border rounded-lg px-4 py-2.5 font-mono text-sm focus:outline-none focus:border-accent-green/50 transition-colors placeholder:text-muted/50"
        />
        <p className="text-[10px] text-muted mt-1">Starting capital for the simulation</p>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-2 text-xs text-muted hover:text-foreground transition-colors"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 16 16"
            className={`transition-transform ${showAdvanced ? "rotate-90" : ""}`}
          >
            <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="2" fill="none" />
          </svg>
          Advanced Configuration
        </button>

        <AnimatePresence>
          {showAdvanced && strategyInfo && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 pt-3 border-t border-card-border">
                {Object.entries(config).map(([key, value]) => (
                  <div key={key} className="rounded-lg border border-card-border/50 bg-white/[0.02] p-3">
                    <p className="text-[10px] text-muted uppercase tracking-wider mb-1.5">{key.replace(/_/g, " ")}</p>
                    <input
                      type={typeof value === "number" ? "number" : "text"}
                      value={String(config[key] ?? value)}
                      onChange={(e) => {
                        const v = typeof value === "number" ? Number(e.target.value) : e.target.value;
                        updateConfig(key, v);
                      }}
                      step={typeof value === "number" ? "0.1" : undefined}
                      className="w-full bg-white/5 border border-card-border rounded px-2.5 py-1.5 text-xs font-mono focus:outline-none focus:border-accent-green/50 transition-colors"
                    />
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full py-3 rounded-lg text-sm font-semibold bg-accent-green text-black hover:bg-accent-green/90 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Running Backtest...
          </>
        ) : (
          "Run Backtest"
        )}
      </button>
    </form>
  );
}
