"use client";

import { motion } from "framer-motion";
import type { VaultStatus, PositionsResponse } from "@/lib/api";

function formatCurrency(n: number): string {
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(2)}K`;
  return `$${n.toFixed(2)}`;
}

interface CardData {
  label: string;
  value: string;
  accent?: "green" | "red" | "blue" | "purple";
  icon: React.ReactNode;
  subtext?: string;
  trend?: number;
}

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.08, duration: 0.4, ease: "easeOut" as const },
  }),
};

function TrendArrow({ value }: { value: number }) {
  if (value > 0) {
    return (
      <motion.svg width="14" height="14" viewBox="0 0 16 16" initial={{ rotate: 0 }} animate={{ rotate: 0 }}>
        <path d="M8 2L14 10H2L8 2Z" fill="#00ff88" />
      </motion.svg>
    );
  }
  if (value < 0) {
    return (
      <motion.svg width="14" height="14" viewBox="0 0 16 16" initial={{ rotate: 180 }} animate={{ rotate: 180 }}>
        <path d="M8 2L14 10H2L8 2Z" fill="#ff4444" />
      </motion.svg>
    );
  }
  return null;
}

function PortfolioCard({ card, index }: { card: CardData; index: number }) {
  const accentColors = {
    green: "from-accent-green/10 to-transparent border-accent-green/20",
    red: "from-accent-red/10 to-transparent border-accent-red/20",
    blue: "from-blue-500/10 to-transparent border-blue-500/20",
    purple: "from-purple-500/10 to-transparent border-purple-500/20",
  };
  const gradient = card.accent ? accentColors[card.accent] : "from-white/5 to-transparent border-card-border";
  const valueColor = card.accent === "green"
    ? "text-accent-green"
    : card.accent === "red"
    ? "text-accent-red"
    : card.accent === "blue"
    ? "text-blue-400"
    : card.accent === "purple"
    ? "text-purple-400"
    : "text-foreground";

  return (
    <motion.div
      custom={index}
      variants={cardVariants}
      initial="hidden"
      animate="visible"
      className={`relative rounded-xl border bg-gradient-to-br p-5 overflow-hidden ${gradient}`}
    >
      <div className="absolute top-0 right-0 w-20 h-20 bg-gradient-to-bl from-white/[0.03] to-transparent rounded-bl-full" />
      <div className="flex items-start justify-between mb-3">
        <div className="p-2 rounded-lg bg-white/5">{card.icon}</div>
        {card.trend !== undefined && <TrendArrow value={card.trend} />}
      </div>
      <p className="text-[11px] text-muted uppercase tracking-wider font-medium mb-1">{card.label}</p>
      <p className={`text-2xl font-bold tracking-tight font-mono ${valueColor}`}>{card.value}</p>
      {card.subtext && <p className="text-xs text-muted mt-1">{card.subtext}</p>}
    </motion.div>
  );
}

interface PortfolioCardsProps {
  vault: VaultStatus | null;
  positions: PositionsResponse | null;
  loading: boolean;
}

export default function PortfolioCards({ vault, positions, loading }: PortfolioCardsProps) {
  const totalFunding = positions?.strategy_positions?.total_funding_earned ?? 0;
  const activePositions = vault?.active_positions ?? 0;
  const pnlPct = vault?.pnl_pct ?? 0;
  const vaultValue = vault?.vault_value ?? 0;

  const cards: CardData[] = [
    {
      label: "Total Value",
      value: loading ? "..." : formatCurrency(vaultValue),
      accent: vaultValue > 0 ? "green" : undefined,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="#00ff88" />
          <path d="M2 17l10 5 10-5" stroke="#00ff88" />
          <path d="M2 12l10 5 10-5" stroke="#00ff88" />
        </svg>
      ),
      subtext: loading ? "" : vault ? `${vault.depositor_count} depositors` : undefined,
      trend: pnlPct > 0 ? 1 : pnlPct < 0 ? -1 : 0,
    },
    {
      label: "24h PnL",
      value: loading ? "..." : vault ? `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%` : "0.00%",
      accent: pnlPct >= 0 ? "green" : "red",
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" stroke={pnlPct >= 0 ? "#00ff88" : "#ff4444"} />
          <polyline points="17 6 23 6 23 12" stroke={pnlPct >= 0 ? "#00ff88" : "#ff4444"} />
        </svg>
      ),
      subtext: loading ? "" : vault ? formatCurrency(vault.net_pnl) : undefined,
      trend: pnlPct,
    },
    {
      label: "Active Strategies",
      value: loading ? "..." : `${activePositions}`,
      accent: activePositions > 0 ? "blue" : undefined,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="3" stroke="#4488ff" />
          <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" stroke="#4488ff" />
        </svg>
      ),
    },
    {
      label: "Yield This Week",
      value: loading ? "..." : formatCurrency(totalFunding),
      accent: totalFunding > 0 ? "purple" : undefined,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" stroke="#a855f7" />
        </svg>
      ),
      subtext: loading ? "" : positions ? `Total funding earned` : undefined,
      trend: totalFunding > 0 ? 1 : 0,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, i) => (
        <PortfolioCard key={card.label} card={card} index={i} />
      ))}
    </div>
  );
}
