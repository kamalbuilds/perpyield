"use client";

import { motion } from "framer-motion";
import type { EnrichedPosition } from "@/hooks/usePositions";

const SYMBOL_COLORS: Record<string, string> = {
  BTC: "#f7931a",
  ETH: "#627eea",
  SOL: "#9945ff",
  ARB: "#28a0f0",
  DOGE: "#c3a634",
  AVAX: "#e84142",
  MATIC: "#8247e5",
  OP: "#ff0420",
  LINK: "#2a5ada",
};

function formatPrice(n: number): string {
  if (n >= 1000) return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (n >= 1) return n.toFixed(4);
  return n.toFixed(6);
}

interface PositionCardProps {
  position: EnrichedPosition;
  index: number;
  onClose: (position: EnrichedPosition) => void;
}

export default function PositionCard({ position: pos, index, onClose }: PositionCardProps) {
  const isLong = pos.side.toLowerCase() === "long";
  const isPositive = pos.unrealized_pnl >= 0;
  const sideColor = isLong ? "#00ff88" : "#ff4444";
  const pnlColor = isPositive ? "text-accent-green" : "text-accent-red";
  const symbolColor = SYMBOL_COLORS[pos.symbol] ?? "#888";

  const priceChangeDirection = pos.mark_price > pos.entry_price ? "up" : pos.mark_price < pos.entry_price ? "down" : "none";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.05 }}
      className="rounded-xl border border-card-border bg-card-bg p-4 hover:border-card-border/80 transition-colors"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
            style={{ background: `${symbolColor}20`, color: symbolColor, border: `1px solid ${symbolColor}40` }}
          >
            {pos.symbol[0]}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-semibold text-sm">{pos.symbol}</span>
              <span
                className="px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wider"
                style={{ background: `${sideColor}15`, color: sideColor }}
              >
                {pos.side.toUpperCase()}
              </span>
              <span className="text-[10px] text-muted font-mono">{pos.leverage}x</span>
            </div>
            <p className="text-[10px] text-muted mt-0.5">
              {Math.abs(pos.size).toFixed(4)} {pos.symbol}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className={`font-mono font-semibold text-sm ${pnlColor}`}>
            {isPositive ? "+" : ""}${pos.unrealized_pnl.toFixed(2)}
          </p>
          <p className={`text-[10px] font-mono ${pnlColor} opacity-70`}>
            {isPositive ? "+" : ""}{pos.unrealized_pnl_pct.toFixed(2)}%
          </p>
        </div>
      </div>

      <div className="flex items-center gap-1.5 text-xs mb-3">
        <span className="font-mono text-muted">${formatPrice(pos.entry_price)}</span>
        <svg width="12" height="12" viewBox="0 0 16 16" className={`inline ${priceChangeDirection === "up" ? "text-accent-green" : priceChangeDirection === "down" ? "text-accent-red" : "text-muted"}`}>
          <path
            d={priceChangeDirection === "down" ? "M8 12L3 6h10L8 12Z" : "M8 4L13 10H3L8 4Z"}
            fill="currentColor"
          />
        </svg>
        <span className="font-mono font-semibold">${formatPrice(pos.mark_price)}</span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-[10px] mb-3">
        <div className="p-2 rounded bg-white/[0.02]">
          <p className="text-muted mb-0.5">Funding Earned</p>
          <p className="font-mono text-accent-green">+${pos.cumulative_funding.toFixed(2)}</p>
        </div>
        <div className="p-2 rounded bg-white/[0.02]">
          <p className="text-muted mb-0.5">Liq. Price</p>
          <p className="font-mono">${formatPrice(pos.liquidation_price)}</p>
        </div>
      </div>

      <button
        onClick={() => onClose(pos)}
        className="w-full py-2 rounded-lg text-xs font-medium bg-accent-red/10 text-accent-red border border-accent-red/20 hover:bg-accent-red/20 transition-colors"
      >
        Close Position
      </button>
    </motion.div>
  );
}
