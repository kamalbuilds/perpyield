"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { usePrices, type SymbolPrice } from "@/context/PriceContext";
import { fetchFundingRates, type FundingRateEntry } from "@/lib/api";

const TICKER_SYMBOLS = [
  "BTC-PERP",
  "ETH-PERP",
  "SOL-PERP",
  "ARB-PERP",
  "DOGE-PERP",
  "AVAX-PERP",
];

const SYMBOL_LABELS: Record<string, string> = {
  "BTC-PERP": "BTC",
  "ETH-PERP": "ETH",
  "SOL-PERP": "SOL",
  "ARB-PERP": "ARB",
  "DOGE-PERP": "DOGE",
  "AVAX-PERP": "AVAX",
};

interface TickerItem {
  symbol: string;
  label: string;
  price: number;
  change24hPct: number;
  fundingRate: number;
}

function buildTickerItem(wsPrice: SymbolPrice | null, symbol: string): TickerItem {
  const label = SYMBOL_LABELS[symbol] ?? symbol.replace("-PERP", "");
  if (wsPrice) {
    return {
      symbol,
      label,
      price: wsPrice.price,
      change24hPct: wsPrice.change24hPct,
      fundingRate: wsPrice.fundingRate,
    };
  }
  const fallbackPrices: Record<string, number> = {
    "BTC-PERP": 67500,
    "ETH-PERP": 3420,
    "SOL-PERP": 145,
    "ARB-PERP": 1.2,
    "DOGE-PERP": 0.15,
    "AVAX-PERP": 35,
  };
  return {
    symbol,
    label,
    price: fallbackPrices[symbol] ?? 0,
    change24hPct: 0,
    fundingRate: 0,
  };
}

function TickerItem({ item }: { item: TickerItem }) {
  const isPositive = item.change24hPct >= 0;
  const prevPrice = useRef(item.price);
  const priceDirection =
    item.price > prevPrice.current
      ? "up"
      : item.price < prevPrice.current
      ? "down"
      : "none";

  useEffect(() => {
    prevPrice.current = item.price;
  }, [item.price]);

  const fundingPositive = item.fundingRate >= 0;

  return (
    <div className="flex items-center gap-4 px-5 py-2 border-r border-white/5 last:border-r-0 whitespace-nowrap">
      <span className="text-xs font-bold text-foreground/80 tracking-wide">
        {item.label}
      </span>
      <AnimatePresence mode="popLayout">
        <motion.span
          key={`${item.symbol}-${item.price.toFixed(2)}`}
          initial={{
            opacity: 0.5,
            y: priceDirection === "up" ? -4 : priceDirection === "down" ? 4 : 0,
          }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="text-sm font-mono font-semibold text-foreground"
        >
          $
          {item.price.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </motion.span>
      </AnimatePresence>
      <motion.span
        animate={{ color: isPositive ? "#00ff88" : "#ff4444" }}
        transition={{ duration: 0.3 }}
        className="text-xs font-mono font-medium"
      >
        {isPositive ? "+" : ""}
        {item.change24hPct.toFixed(2)}%
      </motion.span>
      <span
        className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
          fundingPositive
            ? "bg-accent-green/10 text-accent-green"
            : "bg-accent-red/10 text-accent-red"
        }`}
      >
        {(item.fundingRate * 100).toFixed(4)}%
      </span>
    </div>
  );
}

export default function PriceTicker() {
  const { prices, connected } = usePrices();
  const [fallbackRates, setFallbackRates] = useState<Record<string, FundingRateEntry>>({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let mounted = true;
    async function loadFallback() {
      try {
        const rates = await fetchFundingRates();
        if (!mounted) return;
        const map: Record<string, FundingRateEntry> = {};
        for (const r of rates) {
          map[r.symbol] = r;
        }
        setFallbackRates(map);
      } catch {
        // WS will provide data when connected
      } finally {
        if (mounted) setLoaded(true);
      }
    }
    loadFallback();
    return () => {
      mounted = false;
    };
  }, []);

  const items = TICKER_SYMBOLS.map((sym) => {
    const wsPrice = prices[sym] ?? null;
    const ticker = buildTickerItem(wsPrice, sym);
    if (!wsPrice && fallbackRates[sym]) {
      const rate = fallbackRates[sym];
      ticker.price = rate.mark_price;
      ticker.fundingRate = rate.funding_rate;
    }
    return ticker;
  });

  if (!loaded && !connected) {
    return (
      <div className="w-full h-10 bg-[#0d0d0d] border-b border-white/5 flex items-center px-4">
        <div className="skeleton h-4 w-full max-w-3xl" />
      </div>
    );
  }

  return (
    <div className="w-full overflow-hidden bg-[#0d0d0d] border-b border-white/5 relative">
      <div className="absolute left-0 top-0 bottom-0 w-12 bg-gradient-to-r from-[#0d0d0d] to-transparent z-10" />
      <div className="absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-[#0d0d0d] to-transparent z-10" />
      <div className="flex items-center justify-end px-4 py-0.5">
        <span className="flex items-center gap-1.5 text-[10px] text-muted">
          <span
            className={`inline-block w-1.5 h-1.5 rounded-full ${
              connected ? "bg-accent-green animate-pulse" : "bg-accent-red"
            }`}
          />
          {connected ? "LIVE" : "OFFLINE"}
        </span>
      </div>
      <div className="ticker-scroll flex items-center h-10 -mt-5">
        <div className="flex items-center">
          {items.map((item) => (
            <TickerItem key={item.symbol} item={item} />
          ))}
          {items.map((item) => (
            <TickerItem key={`${item.symbol}-dup`} item={item} />
          ))}
        </div>
      </div>
    </div>
  );
}
