"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { useBacktest } from "@/hooks/useBacktest";
import BacktestForm, { type BacktestFormValues } from "@/components/BacktestForm";
import BacktestResults from "@/components/BacktestResults";
import BacktestComparison from "@/components/BacktestComparison";

function BacktestPageContent() {
  const searchParams = useSearchParams();
  const { results, loading, error, runBacktest, clearResults, exportJSON, exportCSV } = useBacktest();
  const [showComparison, setShowComparison] = useState(false);

  const defaultStrategy = searchParams.get("strategy") ?? undefined;
  const defaultSymbol = searchParams.get("symbol") ?? undefined;

  async function handleSubmit(values: BacktestFormValues) {
    try {
      await runBacktest({
        strategy_id: values.strategyId,
        symbol: values.symbol,
        days: values.days,
        config: Object.keys(values.config).length > 0 ? values.config : undefined,
      });
    } catch {}
  }

  function handleCompare() {
    if (results.length >= 2) {
      setShowComparison(true);
    }
  }

  function handleSave() {
    exportJSON();
  }

  return (
    <div className="space-y-6">
      <div>
        <motion.h2
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-2xl font-bold"
        >
          Strategy Backtesting
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="text-sm text-muted mt-1"
        >
          Simulate how strategies would have performed using historical data. Compare returns, risk metrics, and equity curves before deploying capital.
        </motion.p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <div className="rounded-lg border border-card-border bg-card-bg p-5 sticky top-20">
            <h3 className="text-sm font-semibold mb-4">Configure Backtest</h3>
            <BacktestForm
              onSubmit={handleSubmit}
              loading={loading}
              defaultValues={{
                strategyId: defaultStrategy,
                symbol: defaultSymbol,
              }}
            />
          </div>
        </div>

        <div className="lg:col-span-2 space-y-5">
          {error && (
            <div className="p-4 rounded-lg border border-accent-red/30 bg-accent-red/5 text-sm text-accent-red">
              {error}
            </div>
          )}

          {loading && (
            <div className="rounded-lg border border-card-border bg-card-bg p-8">
              <div className="flex flex-col items-center justify-center gap-4">
                <div className="relative">
                  <div className="w-16 h-16 rounded-full border-2 border-card-border" />
                  <div className="absolute inset-0 w-16 h-16 rounded-full border-2 border-accent-green border-t-transparent animate-spin" />
                </div>
                <div className="text-center">
                  <p className="text-sm font-medium">Running Simulation</p>
                  <p className="text-xs text-muted mt-1">Fetching historical data and calculating strategy performance</p>
                </div>
              </div>
            </div>
          )}

          {!loading && results.length === 0 && !error && (
            <div className="rounded-lg border border-card-border bg-card-bg p-12 text-center">
              <div className="text-4xl mb-3 opacity-30">&#x1F4CA;</div>
              <p className="text-sm text-muted">Configure parameters and run a backtest to see results</p>
              <p className="text-xs text-muted/60 mt-1">Select a strategy, symbol, and time period to get started</p>
            </div>
          )}

          <AnimatePresence>
            {results.length > 0 && !loading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-5"
              >
                {results.map((result) => (
                  <BacktestResults
                    key={`${result.strategy_id}-${result.symbol}-${result.days}`}
                    result={result}
                    onSave={handleSave}
                    onCompare={handleCompare}
                  />
                ))}

                {results.length >= 2 && (
                  <div className="flex items-center gap-3 pt-2">
                    <button
                      onClick={() => setShowComparison(!showComparison)}
                      className={`px-4 py-2 rounded-lg text-xs font-medium transition-colors ${
                        showComparison
                          ? "bg-accent-green/15 text-accent-green border border-accent-green/30"
                          : "bg-white/5 text-muted border border-card-border hover:text-foreground"
                      }`}
                    >
                      {showComparison ? "Hide Comparison" : "Compare Strategies"}
                    </button>
                    <button
                      onClick={exportCSV}
                      className="px-4 py-2 rounded-lg text-xs font-medium border border-card-border bg-white/5 text-muted hover:text-foreground hover:border-accent-green/30 transition-colors"
                    >
                      Export CSV
                    </button>
                    <button
                      onClick={exportJSON}
                      className="px-4 py-2 rounded-lg text-xs font-medium border border-card-border bg-white/5 text-muted hover:text-foreground hover:border-accent-green/30 transition-colors"
                    >
                      Export JSON
                    </button>
                    <button
                      onClick={clearResults}
                      className="px-4 py-2 rounded-lg text-xs font-medium border border-accent-red/20 bg-accent-red/5 text-accent-red/70 hover:text-accent-red hover:border-accent-red/40 transition-colors ml-auto"
                    >
                      Clear Results
                    </button>
                  </div>
                )}

                {showComparison && results.length >= 2 && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <BacktestComparison results={results} />
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

export default function BacktestPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-6">
          <div className="skeleton h-8 w-56" />
          <div className="skeleton h-4 w-96" />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="skeleton h-96 rounded-lg" />
            <div className="lg:col-span-2 skeleton h-64 rounded-lg" />
          </div>
        </div>
      }
    >
      <BacktestPageContent />
    </Suspense>
  );
}
