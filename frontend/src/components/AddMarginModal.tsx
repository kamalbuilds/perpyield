"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { EnrichedPosition } from "@/hooks/usePositions";

interface AddMarginModalProps {
  position: EnrichedPosition | null;
  open: boolean;
  onClose: () => void;
  onConfirm: (position: EnrichedPosition, amount: string, isolated: boolean) => Promise<void>;
}

export default function AddMarginModal({
  position,
  open,
  onClose,
  onConfirm,
}: AddMarginModalProps) {
  const [marginAmount, setMarginAmount] = useState("");
  const [isolated, setIsolated] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = useCallback(async () => {
    if (!position || !marginAmount || parseFloat(marginAmount) <= 0) return;
    setSubmitting(true);
    setError(null);
    try {
      await onConfirm(position, marginAmount, isolated);
      setMarginAmount("");
      setIsolated(false);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add margin");
    } finally {
      setSubmitting(false);
    }
  }, [position, marginAmount, isolated, onConfirm, onClose]);

  if (!position) return null;

  const currentMargin = Math.abs(position.size) * position.entry_price / position.leverage;
  const newMargin = currentMargin + (parseFloat(marginAmount) || 0);
  const newLeverage = position.notional_value / newMargin;
  const newLiqPriceLong = position.entry_price * (1 - 0.9 / Math.max(newLeverage, 1));
  const newLiqPriceShort = position.entry_price * (1 + 0.9 / Math.max(newLeverage, 1));
  const newLiqPrice = position.side === "long" ? newLiqPriceLong : newLiqPriceShort;

  const formatPrice = (n: number) =>
    n >= 1000
      ? n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : n.toFixed(4);

  const presetAmounts = [
    currentMargin * 0.25,
    currentMargin * 0.5,
    currentMargin * 1.0,
  ];

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
        >
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2 }}
            className="relative w-full max-w-md rounded-xl border border-card-border bg-card-bg p-6"
          >
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-semibold">Add Margin</h3>
              <button
                onClick={onClose}
                className="p-1 rounded hover:bg-white/5 text-muted hover:text-foreground transition-colors"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="flex items-center gap-3 mb-5 p-3 rounded-lg bg-white/[0.02] border border-card-border">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
                style={{
                  background: position.side === "long" ? "#00ff8820" : "#ff444420",
                  color: position.side === "long" ? "#00ff88" : "#ff4444",
                  border: `1px solid ${position.side === "long" ? "#00ff8840" : "#ff444440"}`,
                }}
              >
                {position.symbol[0]}
              </div>
              <div>
                <p className="font-mono font-semibold text-sm">{position.symbol}</p>
                <p className="text-xs text-muted">
                  {position.side.toUpperCase()} {Math.abs(position.size).toFixed(4)} @ ${formatPrice(position.entry_price)}
                </p>
              </div>
            </div>

            <div className="mb-4">
              <label className="text-xs text-muted mb-2 block">Margin Amount (USDC)</label>
              <input
                type="number"
                placeholder="0.00"
                value={marginAmount}
                onChange={(e) => setMarginAmount(e.target.value)}
                min="0"
                step="0.01"
                className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-card-border text-sm font-mono focus:outline-none focus:border-accent-green/30 transition-colors"
              />
              <div className="flex gap-1.5 mt-2">
                {presetAmounts.map((amt, i) => (
                  <button
                    key={i}
                    onClick={() => setMarginAmount(amt.toFixed(2))}
                    className={`flex-1 py-1.5 rounded text-[10px] font-medium transition-colors bg-white/5 text-muted hover:bg-white/10 hover:text-foreground`}
                  >
                    +{["25%", "50%", "100%"][i]}
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-4">
              <label className="text-xs text-muted mb-2 block">Margin Mode</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setIsolated(false)}
                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                    !isolated
                      ? "bg-accent-green/15 text-accent-green border border-accent-green/30"
                      : "bg-white/5 text-muted border border-card-border hover:bg-white/10"
                  }`}
                >
                  Cross
                </button>
                <button
                  onClick={() => setIsolated(true)}
                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                    isolated
                      ? "bg-accent-green/15 text-accent-green border border-accent-green/30"
                      : "bg-white/5 text-muted border border-card-border hover:bg-white/10"
                  }`}
                >
                  Isolated
                </button>
              </div>
            </div>

            {parseFloat(marginAmount) > 0 && (
              <div className="p-3 rounded-lg bg-white/[0.02] border border-card-border mb-4 space-y-1.5">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-muted">Current Margin</span>
                  <span className="font-mono text-sm">${currentMargin.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-muted">New Margin</span>
                  <span className="font-mono text-sm font-semibold text-accent-green">${newMargin.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-muted">New Leverage</span>
                  <span className="font-mono text-sm">{newLeverage.toFixed(2)}x</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-muted">New Liq. Price</span>
                  <span className="font-mono text-sm">${formatPrice(newLiqPrice)}</span>
                </div>
              </div>
            )}

            {error && (
              <div className="p-3 rounded-lg bg-accent-red/5 border border-accent-red/20 mb-4 text-xs text-accent-red">
                {error}
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="flex-1 py-2.5 rounded-lg text-sm font-medium bg-white/5 border border-card-border text-muted hover:bg-white/10 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={submitting || !marginAmount || parseFloat(marginAmount) <= 0}
                className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  submitting || !marginAmount || parseFloat(marginAmount) <= 0
                    ? "bg-accent-green/10 text-accent-green/40 cursor-not-allowed"
                    : "bg-accent-green/15 text-accent-green border border-accent-green/30 hover:bg-accent-green/25"
                }`}
              >
                {submitting ? "Adding..." : `Add $${marginAmount || "0"}`}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
