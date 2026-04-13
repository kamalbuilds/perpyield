const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ---- Vault ----

export interface VaultStatus {
  vault_id: string;
  is_active: boolean;
  created_at: number;
  total_deposited: number;
  vault_value: number;
  share_price: number;
  total_shares: number;
  net_pnl: number;
  pnl_pct: number;
  annualized_return: number;
  depositor_count: number;
  active_positions: number;
}

export async function fetchVaultStatus(): Promise<VaultStatus> {
  return apiFetch<VaultStatus>("/api/vault/status");
}

export async function depositVault(
  user_address: string,
  amount: number
): Promise<{ status: string }> {
  return apiFetch("/api/vault/deposit", {
    method: "POST",
    body: JSON.stringify({ user_address, amount }),
  });
}

export async function withdrawVault(
  user_address: string,
  shares: number
): Promise<{ status: string }> {
  return apiFetch("/api/vault/withdraw", {
    method: "POST",
    body: JSON.stringify({ user_address, shares }),
  });
}

// ---- Funding Rates ----

export interface FundingRateEntry {
  symbol: string;
  funding_rate: number;
  next_funding_rate: number;
  mark_price: number;
  oracle_price: number;
  open_interest: number;
  volume_24h: number;
  max_leverage: number;
  annualized_apy: number;
  trend: string;
}

export async function fetchFundingRates(): Promise<FundingRateEntry[]> {
  return apiFetch<FundingRateEntry[]>("/api/funding/rates");
}

// ---- Funding History ----

export interface FundingHistoryRate {
  timestamp: number;
  rate: number;
}

export interface FundingHistory {
  symbol: string;
  rates: FundingHistoryRate[];
  avg_rate_24h: number;
  avg_rate_7d: number;
  positive_rate_pct: number;
}

export async function fetchFundingHistory(symbol: string, hours: number = 168): Promise<FundingHistory> {
  return apiFetch<FundingHistory>(`/api/funding/history/${encodeURIComponent(symbol)}?hours=${hours}`);
}

// ---- Positions ----

export interface PositionEntry {
  symbol: string;
  side: string;
  size: number;
  entry_price: number;
  entry_funding_rate: number;
  cumulative_funding: number;
  held_since: number;
}

export interface PositionsResponse {
  live_positions: unknown[];
  strategy_positions: {
    active_positions: number;
    positions: PositionEntry[];
    total_funding_earned: number;
  };
}

export async function fetchPositions(): Promise<PositionsResponse> {
  return apiFetch<PositionsResponse>("/api/positions");
}

// ---- Backtest ----

export interface BacktestResult {
  strategy: string;
  pair: string;
  start_date: string;
  end_date: string;
  total_return_pct: number;
  annualized_apy: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  funding_earned: number;
  trading_fees: number;
  net_pnl: number;
  equity_curve: number[];
}

export async function fetchBacktest(symbol: string, days: number = 30): Promise<BacktestResult> {
  return apiFetch<BacktestResult>(`/api/backtest/${encodeURIComponent(symbol)}?days=${days}`);
}

// ---- Strategy Control ----

export interface StrategyStatus {
  active_positions: number;
  positions: PositionEntry[];
  total_funding_earned: number;
}

export async function fetchStrategyStatus(): Promise<StrategyStatus> {
  return apiFetch<StrategyStatus>("/api/strategy/status");
}

export async function startStrategy(): Promise<{ status: string; timestamp?: number }> {
  return apiFetch("/api/strategy/start", { method: "POST" });
}

export async function stopStrategy(): Promise<{ status: string; timestamp?: number }> {
  return apiFetch("/api/strategy/stop", { method: "POST" });
}

// ---- Delta Summary ----

export interface DeltaPosition {
  symbol: string;
  long_notional: string;
  short_notional: string;
  net_delta: string;
  delta_pct: string;
  needs_rebalance: boolean;
}

export interface DeltaSummary {
  positions_tracked: number;
  positions_needing_rebalance: number;
  total_rebalances_executed: number;
  positions: DeltaPosition[];
}

export async function fetchDeltaSummary(): Promise<DeltaSummary> {
  return apiFetch<DeltaSummary>("/api/delta/summary");
}
