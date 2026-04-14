"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { EnrichedPosition } from "@/hooks/usePositions";

const SYMBOL_ICONS: Record<string, { color: string; letter: string }> = {
  BTC: { color: "#f7931a", letter: "₿" },
  ETH: { color: "#627eea", letter: "Ξ" },
  SOL: { color: "#9945ff", letter: "S" },
  ARB: { color: "#28a0f0", letter: "A" },
  DOGE: { color: "#c3a634", letter: "D" },
  AVAX: { color: "#e84142", letter: "A" },
  MATIC: { color: "#8247e5", letter: "M" },
  OP: { color: "#ff0420", letter: "O" },
  LINK: { color: "#2a5ada", letter: "L" },
  ATOM: { color: "#2e3148", letter: "A" },
};

function formatPrice(n: number): string {
  if (n >= 1000) return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (n >= 1) return n.toFixed(4);
  return n.toFixed(6);
}

function formatPnl(n: number): string {
  const sign = n >= 0 ? "+" : "";
  if (Math.abs(n) >= 1000) return `${sign}$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `${sign}$${n.toFixed(2)}`;
}

function SymbolIcon({ symbol }: { symbol: string }) {
  const info = SYMBOL_ICONS[symbol] ?? { color: "#888", letter: symbol[0] };
  return (
    <div
      className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
      style={{ background: `${info.color}20`, color: info.color, border: `1px solid ${info.color}40` }}
    >
      {info.letter}
    </div>
  );
}

function SideBadge({ side }: { side: string }) {
  const isLong = side.toLowerCase() === "long";
  return (
    <span
      className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${
        isLong ? "bg-accent-green/15 text-accent-green" : "bg-accent-red/15 text-accent-red"
      }`}
    >
      {side.toUpperCase()}
    </span>
  );
}

function PnlCell({ value, pct }: { value: number; pct: number }) {
  const isPositive = value >= 0;
  const color = isPositive ? "text-accent-green" : "text-accent-red";
  return (
    <div className="text-right">
      <span className={`font-mono font-semibold text-sm ${color}`}>{formatPnl(value)}</span>
      <span className={`ml-1.5 text-[10px] font-mono ${color} opacity-70`}>
        {isPositive ? "+" : ""}{pct.toFixed(2)}%
      </span>
    </div>
  );
}

interface PositionTableProps {
  positions: EnrichedPosition[];
  loading: boolean;
  connected: boolean;
  onClose: (position: EnrichedPosition) => void;
  onAddMargin: (position: EnrichedPosition) => void;
  onTpSl: (position: EnrichedPosition) => void;
}

export default function PositionTable({
  positions,
  loading,
  connected,
  onClose,
  onAddMargin,
  onTpSl,
}: PositionTableProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-card-border bg-card-bg overflow-hidden">
        <div className="px-5 py-4 border-b border-card-border flex items-center justify-between">
          <h3 className="text-sm font-semibold">Active Positions</h3>
        </div>
        <div className="p-5 space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="skeleton h-12 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <div className="rounded-lg border border-card-border bg-card-bg overflow-hidden">
        <div className="px-5 py-4 border-b border-card-border flex items-center justify-between">
          <h3 className="text-sm font-semibold">Active Positions</h3>
        </div>
        <div className="p-12 text-center">
          <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-4">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M9 12h6M12 9v6" />
            </svg>
          </div>
          <p className="text-muted text-sm mb-1">No open positions</p>
          <p className="text-muted/60 text-xs">Start a strategy to begin earning funding yield</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-card-border bg-card-bg overflow-hidden">
      <div className="px-5 py-4 border-b border-card-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold">Active Positions</h3>
          <div className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-accent-green pulse-dot" : "bg-muted"}`} />
            <span className="text-[10px] text-muted font-mono">{connected ? "LIVE" : "OFFLINE"}</span>
          </div>
        </div>
        <span className="text-xs text-muted">{positions.length} position{positions.length !== 1 ? "s" : ""}</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-card-border text-[10px] text-muted uppercase tracking-wider">
              <th className="text-left px-5 py-3">Symbol</th>
              <th className="text-left px-3 py-3">Side</th>
              <th className="text-right px-3 py-3">Size</th>
              <th className="text-right px-3 py-3">Leverage</th>
              <th className="text-right px-3 py-3">Entry Price</th>
              <th className="text-right px-3 py-3">Mark Price</th>
              <th className="text-right px-3 py-3">Unrealized PnL</th>
              <th className="text-right px-3 py-3">Funding Earned</th>
              <th className="text-right px-3 py-3">Liq. Price</th>
              <th className="text-right px-5 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence>
              {positions.map((pos, i) => (
                <motion.tr
                  key={`${pos.symbol}-${pos.side}-${i}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.2, delay: i * 0.03 }}
                  className="border-b border-card-border/40 hover:bg-white/[0.02] transition-colors group"
                >
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2.5">
                      <SymbolIcon symbol={pos.symbol} />
                      <span className="font-mono font-semibold text-foreground">{pos.symbol}</span>
                    </div>
                  </td>
                  <td className="px-3 py-3.5">
                    <SideBadge side={pos.side} />
                  </td>
                  <td className="px-3 py-3.5 text-right font-mono">
                    {Math.abs(pos.size).toFixed(4)} <span className="text-muted text-xs">{pos.symbol}</span>
                  </td>
                  <td className="px-3 py-3.5 text-right font-mono text-muted">
                    {pos.leverage}x
                  </td>
                  <td className="px-3 py-3.5 text-right font-mono">
                    ${formatPrice(pos.entry_price)}
                  </td>
                  <td className="px-3 py-3.5 text-right font-mono font-semibold">
                    ${formatPrice(pos.mark_price)}
                  </td>
                  <td className="px-3 py-3.5">
                    <PnlCell value={pos.unrealized_pnl} pct={pos.unrealized_pnl_pct} />
                  </td>
                  <td className="px-3 py-3.5 text-right font-mono text-accent-green">
                    +${pos.cumulative_funding.toFixed(2)}
                  </td>
                  <td className="px-3 py-3.5 text-right font-mono text-muted">
                    ${formatPrice(pos.liquidation_price)}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => onClose(pos)}
                        className="px-2 py-1 rounded text-[10px] font-medium bg-accent-red/10 text-accent-red hover:bg-accent-red/20 transition-colors"
                      >
                        Close
                      </button>
                      <button
                        onClick={() => onAddMargin(pos)}
                        className="px-2 py-1 rounded text-[10px] font-medium bg-white/5 text-muted hover:bg-white/10 hover:text-foreground transition-colors"
                      >
                        + Margin
                      </button>
                      <button
                        onClick={() => onTpSl(pos)}
                        className="px-2 py-1 rounded text-[10px] font-medium bg-white/5 text-muted hover:bg-white/10 hover:text-foreground transition-colors"
                      >
                        TP/SL
                      </button>
                    </div>
                  </td>
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
    </div>
  );
}
