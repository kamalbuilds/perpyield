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
  fees?: FeeStructure;
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

export interface LivePosition {
  symbol: string;
  side: string;
  size: number;
  entry_price: number;
  entry_funding_rate?: number;
  cumulative_funding: number;
  mark_price?: string;
  current_funding?: number;
  unrealized_pnl?: number;
  open_time?: number;
}

export interface PositionsResponse {
  live_positions: LivePosition[];
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

// ---- Strategy Marketplace ----

export interface StrategyMarketplaceEntry {
  id: string;
  name: string;
  description: string;
  indicators: string[];
  risk_level: string;
  expected_apy: string;
}

export interface StrategyMarketplaceResponse {
  strategies: StrategyMarketplaceEntry[];
  total_count: number;
}

export async function fetchStrategyMarketplace(): Promise<StrategyMarketplaceResponse> {
  return apiFetch<StrategyMarketplaceResponse>("/api/strategies/marketplace");
}

export interface StrategyInfoResponse {
  id: string;
  name: string;
  description: string;
  indicators: string[];
  risk_level: string;
  expected_apy: string;
  config_defaults: Record<string, number | string>;
}

export async function fetchStrategyInfo(strategyId: string): Promise<StrategyInfoResponse> {
  return apiFetch<StrategyInfoResponse>(`/api/strategies/${encodeURIComponent(strategyId)}/info`);
}

// ---- Vault Marketplace ----

export interface FeaturedVault {
  vault_id: string;
  name: string;
  description: string;
  strategy_id: string;
  strategy_name: string;
  risk_level: string;
  expected_apy: string;
  total_deposited: number;
  depositor_count: number;
  clone_count: number;
  creator: string;
  performance_7d: string;
  performance_30d: string;
}

export interface VaultMarketplaceResponse {
  featured_vaults: FeaturedVault[];
  total_vaults: number;
  filters: {
    strategies: StrategyMarketplaceEntry[];
    risk_levels: string[];
  };
}

export async function fetchVaultMarketplace(): Promise<VaultMarketplaceResponse> {
  return apiFetch<VaultMarketplaceResponse>("/api/vault/marketplace");
}

export async function cloneVault(
  newVaultId: string,
  clonerAddress: string,
  customName?: string,
  customDescription?: string
): Promise<{ status: string; template: Record<string, unknown> }> {
  return apiFetch("/api/vault/clone", {
    method: "POST",
    body: JSON.stringify({
      new_vault_id: newVaultId,
      cloner_address: clonerAddress,
      custom_name: customName,
      custom_description: customDescription,
    }),
  });
}

export async function switchStrategy(
  strategyId: string,
  config?: Record<string, unknown>
): Promise<{ status: string; vault_id: string; strategy_id: string; strategy_name: string }> {
  return apiFetch("/api/vault/switch-strategy", {
    method: "POST",
    body: JSON.stringify({ strategy_id: strategyId, config }),
  });
}

export interface VaultStrategiesResponse {
  current_strategy_id: string;
  available_strategies: StrategyMarketplaceEntry[];
}

export async function fetchVaultStrategies(): Promise<VaultStrategiesResponse> {
  return apiFetch<VaultStrategiesResponse>("/api/vault/strategies");
}

// ---- Strategy Backtest ----

export interface StrategyBacktestRequest {
  strategy_id: string;
  symbol: string;
  days: number;
  config?: Record<string, unknown>;
}

export interface StrategyBacktestResponse {
  strategy_id: string;
  symbol: string;
  days: number;
  backtest: {
    total_return_pct: number;
    annualized_apy: number;
    sharpe_ratio: number;
    max_drawdown_pct: number;
    win_rate: number;
    total_trades: number;
    funding_earned: number;
    trading_fees: number;
    net_pnl: number;
  };
  equity_curve_sample: number[];
}

export async function fetchStrategyBacktest(req: StrategyBacktestRequest): Promise<StrategyBacktestResponse> {
  return apiFetch(`/api/strategies/${encodeURIComponent(req.strategy_id)}/backtest`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// ---- Leaderboard ----

export interface LeaderboardVault {
  rank: number;
  vault_id: string;
  name: string;
  creator: string;
  strategy_id: string;
  strategy_name: string;
  risk_level: string;
  tvl: number;
  return_7d: number;
  return_30d: number;
  sharpe_ratio: number;
  clone_count: number;
  follower_count: number;
  weekly_depositors: number;
}

export interface LeaderboardResponse {
  period: string;
  sort_by: string;
  vaults: LeaderboardVault[];
  total: number;
}

export async function fetchLeaderboard(
  period: string = "7d",
  sortBy: string = "return"
): Promise<LeaderboardResponse> {
  return apiFetch<LeaderboardResponse>(
    `/api/leaderboard/vaults?period=${period}&sort_by=${sortBy}`
  );
}

// ---- Top Traders ----

export interface TopTrader {
  rank: number;
  address: string;
  vault_count: number;
  total_tvl: number;
  best_return_7d: number;
  total_clones: number;
  total_followers: number;
}

export interface TopTradersResponse {
  traders: TopTrader[];
  total: number;
}

export async function fetchTopTraders(
  limit: number = 5
): Promise<TopTradersResponse> {
  return apiFetch<TopTradersResponse>(`/api/leaderboard/traders?limit=${limit}`);
}

// ---- Social ----

export interface FollowResponse {
  status: string;
  vault_id: string;
  follower_count: number;
}

export async function followVault(
  userAddress: string,
  vaultId: string
): Promise<FollowResponse> {
  return apiFetch("/api/social/follow-vault", {
    method: "POST",
    body: JSON.stringify({ user_address: userAddress, vault_id: vaultId }),
  });
}

export async function unfollowVault(
  userAddress: string,
  vaultId: string
): Promise<FollowResponse> {
  return apiFetch("/api/social/unfollow-vault", {
    method: "POST",
    body: JSON.stringify({ user_address: userAddress, vault_id: vaultId }),
  });
}

export interface FollowingVault {
  vault_id: string;
  follower_count: number;
  clone_count: number;
}

export interface FollowingResponse {
  user_address: string;
  following: FollowingVault[];
  total_following: number;
}

export async function fetchFollowing(
  userAddress: string
): Promise<FollowingResponse> {
  return apiFetch<FollowingResponse>(
    `/api/social/following?user_address=${encodeURIComponent(userAddress)}`
  );
}

export interface VaultSocialStatsResponse {
  vault_id: string;
  clone_count: number;
  follower_count: number;
  view_count: number;
  weekly_depositors: number;
}

export async function fetchVaultSocialStats(
  vaultId: string
): Promise<VaultSocialStatsResponse> {
  return apiFetch<VaultSocialStatsResponse>(
    `/api/social/vault-stats/${encodeURIComponent(vaultId)}`
  );
}

export async function trackVaultView(vaultId: string): Promise<{ status: string; view_count: number }> {
  return apiFetch("/api/social/track-view", {
    method: "POST",
    body: JSON.stringify({ vault_id: vaultId }),
  });
}

export interface ShareData {
  vault_id: string;
  name: string;
  pnl_pct: number;
  tvl: number;
  clone_count: number;
  follower_count: number;
  share_text: string;
  twitter_url: string;
}

export async function fetchShareData(vaultId: string): Promise<ShareData> {
  return apiFetch<ShareData>(
    `/api/social/share/${encodeURIComponent(vaultId)}`
  );
}

// ---- AI Advisor ----

export interface MarketAnalysisMetrics {
  avg_funding_rate: number;
  positive_funding_pct: number;
  volatility_index: number;
  trend_strength: number;
  range_bound_score: number;
  funding_rate_count: number;
}

export interface MarketAnalysisData {
  current_regime: "trending" | "ranging" | "volatile" | "neutral";
  recommended_strategy: string;
  confidence: number;
  reasoning: string;
  metrics: MarketAnalysisMetrics;
  top_funding_symbols: { symbol: string; funding_rate: number; apy: number; volume_24h: number }[];
  high_volatility_symbols: { symbol: string; volatility: number; trend_direction: string }[];
  trending_symbols: { symbol: string; trend_strength: number; trend_direction: string }[];
  regime_changed: boolean;
  previous_regime: string | null;
  timestamp: number;
}

export async function fetchMarketAnalysis(): Promise<MarketAnalysisData> {
  const res = await apiFetch<{ success: boolean; data: MarketAnalysisData }>("/api/ai/market-analysis");
  return res.data;
}

export interface StrategyRecommendation {
  strategy_id: string;
  strategy_name: string;
  score: number;
  confidence: number;
  reasoning: string;
  risk_level: string;
  expected_apy: string;
  regime_match: string;
}

export interface RecommendStrategyResponse {
  risk_profile: string;
  current_regime: string;
  recommendations: StrategyRecommendation[];
  metrics: MarketAnalysisMetrics;
  timestamp: number;
}

export async function fetchRecommendedStrategies(
  riskProfile: "conservative" | "moderate" | "aggressive" = "moderate"
): Promise<RecommendStrategyResponse> {
  const res = await apiFetch<{ success: boolean; data: RecommendStrategyResponse }>("/api/ai/recommend-strategy", {
    method: "POST",
    body: JSON.stringify({ risk_profile: riskProfile }),
  });
  return res.data;
}

export interface StrategySimulationData {
  strategy_id: string;
  strategy_name: string;
  amount: number;
  days: number;
  projected_return_pct: number;
  projected_return_usd: number;
  projected_apy: number;
  risk_adjusted_return: number;
  confidence: number;
  best_case: number;
  worst_case: number;
}

export interface SimulateResponse {
  simulation: StrategySimulationData;
  assumptions: string[];
}

export async function fetchStrategySimulation(
  strategyId: string,
  amount: number = 1000,
  days: number = 30
): Promise<SimulateResponse> {
  const res = await apiFetch<{ success: boolean; data: SimulateResponse }>("/api/ai/simulate", {
    method: "POST",
    body: JSON.stringify({ strategy_id: strategyId, amount, days }),
  });
  return res.data;
}

export interface AIAlert {
  type: string;
  severity: "low" | "medium" | "high" | "info";
  message: string;
  suggestion: string;
  timestamp: number;
}

export async function fetchAIAlerts(): Promise<AIAlert[]> {
  const res = await apiFetch<{ success: boolean; data: AIAlert[] }>("/api/ai/alerts");
  return res.data;
}

// ---- Risk Management ----

export interface RiskStatus {
  level: "ok" | "warning" | "violation";
  daily_pnl_pct: number;
  drawdown_pct: number;
  consecutive_losses: number;
  circuit_breaker_active: boolean;
  emergency_stop_active: boolean;
  emergency_stop_type: string | null;
  warnings: string[];
  violations: string[];
  position_usage_pct: number;
  sector_exposure: Record<string, number>;
  correlated_exposure: Record<string, number>;
  report: {
    emergency_stop_active: boolean;
    emergency_stop_type: string | null;
    circuit_breaker_active: boolean;
    circuit_breaker_reason: string | null;
    consecutive_losses: number;
    peak_value: number;
    daily_pnl: number;
    daily_trade_count: number;
    daily_win_rate: number;
    daily_winning_trades: number;
    daily_losing_trades: number;
    sector_exposure: Record<string, number>;
    correlated_exposure: Record<string, number>;
    config: {
      daily_loss_limit_pct: number;
      max_drawdown_pct: number;
      consecutive_losses_limit: number;
      max_position_size_pct: number;
      max_correlated_exposure: number;
      max_sector_exposure: number;
      position_sizing_method: string;
      fixed_risk_per_trade_pct: number;
      kelly_fraction: number;
      enable_circuit_breaker: boolean;
      funding_rate_flip_protection: boolean;
    };
  };
}

export async function fetchRiskStatus(): Promise<RiskStatus> {
  return apiFetch<RiskStatus>("/api/vault/risk/status");
}

export interface RiskConfigUpdate {
  daily_loss_limit_pct?: number;
  max_drawdown_pct?: number;
  consecutive_losses_limit?: number;
  max_position_size_pct?: number;
  max_correlated_exposure?: number;
  max_sector_exposure?: number;
  enable_circuit_breaker?: boolean;
  funding_rate_flip_protection?: boolean;
  fixed_risk_per_trade_pct?: number;
  position_sizing_method?: string;
  kelly_fraction?: number;
  volatility_adjust?: boolean;
}

export async function configureRisk(config: RiskConfigUpdate): Promise<{ status: string; config: Record<string, unknown> }> {
  return apiFetch("/api/vault/risk/configure", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function emergencyStop(stopType: "kill_switch" | "gradual_unwind" = "kill_switch"): Promise<{ status: string; stop_type: string; timestamp: number }> {
  return apiFetch("/api/vault/emergency-stop", {
    method: "POST",
    body: JSON.stringify({ stop_type: stopType }),
  });
}

export async function resumeTrading(): Promise<{ status: string; timestamp: number }> {
  return apiFetch("/api/vault/resume-trading", { method: "POST" });
}

// ---- Portfolio ----

export interface StrategyBreakdown {
  strategy_id: string;
  allocated_pct: number;
  current_pct: number;
  allocated_value: number;
  current_value: number;
  pnl: number;
  pnl_pct: number;
  active_positions: number;
  drift: number;
}

export interface PortfolioPnl {
  combined_pnl: number;
  combined_pnl_pct: number;
  total_value: number;
  total_allocated: number;
  strategy_breakdown: Record<string, StrategyBreakdown>;
}

export interface DriftEntry {
  strategy_id: string;
  target_pct: number;
  actual_pct: number;
  drift: number;
  needs_rebalance: boolean;
}

export interface PortfolioStatusResponse {
  portfolio_mode: boolean;
  message?: string;
  allocations?: Record<string, number>;
  combined_pnl?: PortfolioPnl;
  drift_report?: {
    needs_rebalance: boolean;
    threshold: number;
    drifts: Record<string, DriftEntry>;
  };
  portfolio_status?: {
    portfolio_mode: boolean;
    allocations: Record<string, number>;
    rebalance_threshold: number;
    strategy_count: number;
    strategies: Record<string, {
      allocated_pct: number;
      current_pct: number;
      pnl: number;
      pnl_pct: number;
      active_positions: number;
    }>;
  };
  per_strategy_performance?: Record<string, StrategyBreakdown>;
}

export async function fetchPortfolioStatus(): Promise<PortfolioStatusResponse> {
  return apiFetch<PortfolioStatusResponse>("/api/vault/portfolio/status");
}

export async function configurePortfolio(
  allocations: Record<string, number>,
  rebalanceThreshold: number = 0.05
): Promise<{ status: string; vault_id: string; portfolio_mode: boolean; allocations: Record<string, number>; rebalance_threshold: number }> {
  return apiFetch("/api/vault/portfolio/configure", {
    method: "POST",
    body: JSON.stringify({ allocations, rebalance_threshold: rebalanceThreshold }),
  });
}

export async function rebalancePortfolio(): Promise<{ status: string; adjustments: unknown[]; new_allocations: Record<string, number> }> {
  return apiFetch("/api/vault/portfolio/rebalance", {
    method: "POST",
  });
}

// ---- Fee System ----

export interface FeeStructure {
  management_fee_annual: number;
  management_fee_annual_pct: string;
  performance_fee: number;
  performance_fee_pct: string;
  protocol_fee: number;
  protocol_fee_pct: string;
}

export interface VaultFeesResponse {
  vault_id: string;
  fee_structure: FeeStructure;
  high_water_mark: number;
  last_fee_charge_time: number;
  accrued: {
    creator_management_fees: number;
    creator_performance_fees: number;
    creator_total_earned: number;
    creator_fees_withdrawn: number;
    creator_fees_claimable: number;
    protocol_fees_earned: number;
  };
}

export async function fetchVaultFees(): Promise<VaultFeesResponse> {
  return apiFetch<VaultFeesResponse>("/api/vault/fees");
}

export interface CreatorDashboard {
  creator_address: string;
  vault_id: string;
  vault_name: string;
  strategy_id: string;
  strategy_name: string;
  aum: number;
  depositor_count: number;
  total_deposited: number;
  fee_earnings: {
    management_fees_earned: number;
    performance_fees_earned: number;
    total_earned: number;
    claimable: number;
    withdrawn: number;
    daily_average: number;
  };
  protocol_fees: {
    total_earned: number;
    withdrawn: number;
  };
  fee_structure: FeeStructure;
  high_water_mark: number;
  recent_fee_charges: {
    timestamp: number;
    vault_value: number;
    days_charged: number;
    management_fee: number;
    performance_fee: number;
    protocol_fee: number;
    total_fee: number;
    high_water_mark: number;
  }[];
  vault_active: boolean;
}

export async function fetchCreatorDashboard(creatorAddress: string): Promise<CreatorDashboard> {
  return apiFetch<CreatorDashboard>(`/api/creator/dashboard?creator_address=${encodeURIComponent(creatorAddress)}`);
}

export async function withdrawCreatorFees(
  creatorAddress: string,
  amount?: number
): Promise<{ status: string; amount: number; remaining_claimable: number; total_earned: number; total_withdrawn: number }> {
  return apiFetch("/api/creator/withdraw-fees", {
    method: "POST",
    body: JSON.stringify({ creator_address: creatorAddress, amount }),
  });
}
