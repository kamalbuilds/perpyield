"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { EnrichedPosition } from "@/hooks/usePositions";

interface ClosePositionModalProps {
  position: EnrichedPosition | null;
  open: boolean;
  onClose: () => void;
  onConfirm: (position: EnrichedPosition, closePercent: number, orderType: "market" | "limit", limitPrice?: number) => void;
}

export default function ClosePositionModal({
  position,
  open,
  onClose,
  onConfirm,
}: ClosePositionModalProps) {
  const [closePercent, setClosePercent] = useState(100);
  const [orderType, setOrderType] = useState<"market" | "limit">("market");
  const [limitPrice, setLimitPrice] = useState("");
  const [confirming, setConfirming] = useState(false);

  const handleConfirm = useCallback(() => {
    if (!position) return;
    setConfirming(true);
    const lp = orderType === "limit" && limitPrice ? parseFloat(limitPrice) : undefined;
    onConfirm(position, closePercent, orderType, lp);
    setTimeout(() => {
      setConfirming(false);
      setClosePercent(100);
      setOrderType("market");
      setLimitPrice("");
      onClose();
    }, 500);
  }, [position, closePercent, orderType, limitPrice, onConfirm, onClose]);

  if (!position) return null;

  const closeSize = Math.abs(position.size) * (closePercent / 100);
  const estimatedPnl = position.unrealized_pnl * (closePercent / 100);
  const isPositive = estimatedPnl >= 0;
  const pnlColor = isPositive ? "text-accent-green" : "text-accent-red";

  const formatPrice = (n: number) =>
    n >= 1000
      ? n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : n.toFixed(4);

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
              <h3 className="text-base font-semibold">Close Position</h3>
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

            <div className="mb-5">
              <label className="text-xs text-muted mb-2 block">Close Size: {closePercent}%</label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={10}
                  max={100}
                  step={10}
                  value={closePercent}
                  onChange={(e) => setClosePercent(parseInt(e.target.value))}
                  className="flex-1 h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent-green [&::-webkit-slider-thumb]:cursor-pointer"
                />
                <span className="text-sm font-mono font-semibold w-12 text-right">
                  {closeSize.toFixed(4)}
                </span>
              </div>
              <div className="flex gap-1.5 mt-2">
                {[25, 50, 75, 100].map((pct) => (
                  <button
                    key={pct}
                    onClick={() => setClosePercent(pct)}
                    className={`flex-1 py-1 rounded text-[10px] font-medium transition-colors ${
                      closePercent === pct
                        ? "bg-accent-green/15 text-accent-green"
                        : "bg-white/5 text-muted hover:bg-white/10"
                    }`}
                  >
                    {pct}%
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-5">
              <label className="text-xs text-muted mb-2 block">Order Type</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setOrderType("market")}
                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                    orderType === "market"
                      ? "bg-accent-green/15 text-accent-green border border-accent-green/30"
                      : "bg-white/5 text-muted border border-card-border hover:bg-white/10"
                  }`}
                >
                  Market
                </button>
                <button
                  onClick={() => setOrderType("limit")}
                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                    orderType === "limit"
                      ? "bg-accent-green/15 text-accent-green border border-accent-green/30"
                      : "bg-white/5 text-muted border border-card-border hover:bg-white/10"
                  }`}
                >
                  Limit
                </button>
              </div>
              {orderType === "limit" && (
                <input
                  type="number"
                  placeholder="Limit price"
                  value={limitPrice}
                  onChange={(e) => setLimitPrice(e.target.value)}
                  className="w-full mt-2 px-3 py-2 rounded-lg bg-white/5 border border-card-border text-sm font-mono focus:outline-none focus:border-accent-green/30 transition-colors"
                />
              )}
            </div>

            <div className="p-3 rounded-lg bg-white/[0.02] border border-card-border mb-5">
              <div className="flex justify-between items-center">
                <span className="text-xs text-muted">Estimated PnL</span>
                <span className={`font-mono font-semibold text-sm ${pnlColor}`}>
                  {isPositive ? "+" : ""}${estimatedPnl.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between items-center mt-1.5">
                <span className="text-xs text-muted">Funding Earned</span>
                <span className="font-mono text-sm text-accent-green">
                  +${(position.cumulative_funding * (closePercent / 100)).toFixed(2)}
                </span>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="flex-1 py-2.5 rounded-lg text-sm font-medium bg-white/5 border border-card-border text-muted hover:bg-white/10 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={confirming}
                className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  confirming
                    ? "bg-accent-red/20 text-accent-red/50 cursor-not-allowed"
                    : "bg-accent-red/15 text-accent-red border border-accent-red/30 hover:bg-accent-red/25"
                }`}
              >
                {confirming ? "Closing..." : `Close ${closePercent}%`}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
