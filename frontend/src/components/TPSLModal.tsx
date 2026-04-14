"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { EnrichedPosition } from "@/hooks/usePositions";

interface TPSLModalProps {
  position: EnrichedPosition | null;
  open: boolean;
  onClose: () => void;
  onConfirm: (position: EnrichedPosition, tpPrice: string | null, slPrice: string | null) => Promise<void>;
}

export default function TPSLModal({
  position,
  open,
  onClose,
  onConfirm,
}: TPSLModalProps) {
  const [tpPrice, setTpPrice] = useState("");
  const [slPrice, setSlPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = useCallback(async () => {
    if (!position) return;
    if (!tpPrice && !slPrice) {
      setError("Set at least a Take Profit or Stop Loss price");
      return;
    }

    const tp = tpPrice ? parseFloat(tpPrice) : NaN;
    const sl = slPrice ? parseFloat(slPrice) : NaN;

    if (tpPrice && isNaN(tp)) {
      setError("Invalid Take Profit price");
      return;
    }
    if (slPrice && isNaN(sl)) {
      setError("Invalid Stop Loss price");
      return;
    }

    if (position.side === "long") {
      if (tpPrice && tp <= position.mark_price) {
        setError("Take Profit must be above current mark price for long");
        return;
      }
      if (slPrice && sl >= position.mark_price) {
        setError("Stop Loss must be below current mark price for long");
        return;
      }
    } else {
      if (tpPrice && tp >= position.mark_price) {
        setError("Take Profit must be below current mark price for short");
        return;
      }
      if (slPrice && sl <= position.mark_price) {
        setError("Stop Loss must be above current mark price for short");
        return;
      }
    }

    setSubmitting(true);
    setError(null);

    try {
      await onConfirm(
        position,
        tpPrice || null,
        slPrice || null,
      );
      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        setTpPrice("");
        setSlPrice("");
        onClose();
      }, 1200);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to set TP/SL");
    } finally {
      setSubmitting(false);
    }
  }, [position, tpPrice, slPrice, onConfirm, onClose]);

  const resetAndClose = useCallback(() => {
    setTpPrice("");
    setSlPrice("");
    setError(null);
    setSuccess(false);
    onClose();
  }, [onClose]);

  if (!position) return null;

  const formatPrice = (n: number) =>
    n >= 1000
      ? n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : n.toFixed(4);

  const isLong = position.side === "long";
  const sideColor = isLong ? "#00ff88" : "#ff4444";

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onClick={(e) => { if (e.target === e.currentTarget) resetAndClose(); }}
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
              <h3 className="text-base font-semibold">Set TP / SL</h3>
              <button
                onClick={resetAndClose}
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
                  background: `${sideColor}20`,
                  color: sideColor,
                  border: `1px solid ${sideColor}40`,
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
              <div className="ml-auto text-right">
                <p className="text-xs text-muted">Mark</p>
                <p className="font-mono text-sm font-semibold">${formatPrice(position.mark_price)}</p>
              </div>
            </div>

            <div className="space-y-4 mb-5">
              <div>
                <label className="text-xs text-muted mb-1.5 flex items-center gap-1.5">
                  <span className="inline-block w-2 h-2 rounded-full bg-accent-green" />
                  Take Profit Price
                  {isLong && <span className="text-muted/60">(above ${formatPrice(position.mark_price)})</span>}
                  {!isLong && <span className="text-muted/60">(below ${formatPrice(position.mark_price)})</span>}
                </label>
                <input
                  type="number"
                  step="any"
                  placeholder={formatPrice(position.mark_price * (isLong ? 1.05 : 0.95))}
                  value={tpPrice}
                  onChange={(e) => { setTpPrice(e.target.value); setError(null); }}
                  className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-card-border text-sm font-mono focus:outline-none focus:border-accent-green/30 transition-colors placeholder:text-muted/40"
                />
              </div>

              <div>
                <label className="text-xs text-muted mb-1.5 flex items-center gap-1.5">
                  <span className="inline-block w-2 h-2 rounded-full bg-accent-red" />
                  Stop Loss Price
                  {isLong && <span className="text-muted/60">(below ${formatPrice(position.mark_price)})</span>}
                  {!isLong && <span className="text-muted/60">(above ${formatPrice(position.mark_price)})</span>}
                </label>
                <input
                  type="number"
                  step="any"
                  placeholder={formatPrice(position.mark_price * (isLong ? 0.97 : 1.03))}
                  value={slPrice}
                  onChange={(e) => { setSlPrice(e.target.value); setError(null); }}
                  className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-card-border text-sm font-mono focus:outline-none focus:border-accent-red/30 transition-colors placeholder:text-muted/40"
                />
              </div>
            </div>

            {error && (
              <div className="mb-4 p-2.5 rounded-lg bg-accent-red/10 border border-accent-red/20 text-xs text-accent-red">
                {error}
              </div>
            )}

            {success && (
              <div className="mb-4 p-2.5 rounded-lg bg-accent-green/10 border border-accent-green/20 text-xs text-accent-green">
                TP/SL orders set successfully on Pacifica testnet
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={resetAndClose}
                disabled={submitting}
                className="flex-1 py-2.5 rounded-lg text-sm font-medium bg-white/5 border border-card-border text-muted hover:bg-white/10 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting || success}
                className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  submitting || success
                    ? "bg-accent-green/20 text-accent-green/50 cursor-not-allowed"
                    : "bg-accent-green/15 text-accent-green border border-accent-green/30 hover:bg-accent-green/25"
                }`}
              >
                {submitting ? "Setting..." : success ? "Set!" : "Confirm TP/SL"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
