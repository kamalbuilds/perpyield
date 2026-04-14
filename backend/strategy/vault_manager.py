import json
import time
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from pacifica.client import PacificaClient, sf
from strategy.delta_neutral import DeltaNeutralStrategy, StrategyConfig
from strategy.rebalancer import Rebalancer, RebalanceConfig

logger = logging.getLogger(__name__)


@dataclass
class Depositor:
    address: str
    shares: float
    deposited_amount: float
    deposit_time: int


@dataclass
class VaultState:
    vault_id: str
    total_shares: float = 0.0
    total_deposited: float = 0.0
    total_funding_earned: float = 0.0
    total_fees_paid: float = 0.0
    depositors: dict[str, Depositor] = field(default_factory=dict)
    created_at: int = 0
    updated_at: int = 0
    is_active: bool = True


class VaultManager:
    def __init__(
        self,
        client: PacificaClient,
        vault_id: str = "perpyield-v1",
        state_dir: str = "data",
        strategy_config: Optional[StrategyConfig] = None,
        rebalance_config: Optional[RebalanceConfig] = None,
    ):
        self.client = client
        self.vault_id = vault_id
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / f"{vault_id}.json"

        self.strategy = DeltaNeutralStrategy(client, strategy_config)
        self.rebalancer = Rebalancer(client, rebalance_config)

        self.state = self._load_state()

    def _load_state(self) -> VaultState:
        if self.state_file.exists():
            raw = json.loads(self.state_file.read_text())
            depositors = {}
            for addr, dep in raw.get("depositors", {}).items():
                depositors[addr] = Depositor(**dep)
            return VaultState(
                vault_id=raw["vault_id"],
                total_shares=raw["total_shares"],
                total_deposited=raw["total_deposited"],
                total_funding_earned=raw.get("total_funding_earned", 0.0),
                total_fees_paid=raw.get("total_fees_paid", 0.0),
                depositors=depositors,
                created_at=raw["created_at"],
                updated_at=raw["updated_at"],
                is_active=raw.get("is_active", True),
            )
        return VaultState(vault_id=self.vault_id)

    def _save_state(self):
        self.state.updated_at = int(time.time() * 1000)
        data = {
            "vault_id": self.state.vault_id,
            "total_shares": self.state.total_shares,
            "total_deposited": self.state.total_deposited,
            "total_funding_earned": self.state.total_funding_earned,
            "total_fees_paid": self.state.total_fees_paid,
            "depositors": {addr: asdict(dep) for addr, dep in self.state.depositors.items()},
            "created_at": self.state.created_at,
            "updated_at": self.state.updated_at,
            "is_active": self.state.is_active,
        }
        self.state_file.write_text(json.dumps(data, indent=2))

    def create_vault(self) -> dict:
        if self.state.created_at > 0:
            return {"status": "already_exists", "vault_id": self.vault_id}
        self.state.created_at = int(time.time() * 1000)
        self._save_state()
        logger.info(f"Vault {self.vault_id} created")
        return {"status": "created", "vault_id": self.vault_id, "created_at": self.state.created_at}

    async def get_total_vault_value(self) -> float:
        if not self.client.public_key:
            return self.state.total_deposited
        account = await self.client.get_account()
        equity = sf(account.account_equity)
        return equity if equity > 0 else self.state.total_deposited

    async def get_share_price(self) -> float:
        if self.state.total_shares <= 0:
            return 1.0
        vault_value = await self.get_total_vault_value()
        return vault_value / self.state.total_shares

    async def deposit(self, depositor_address: str, amount: float) -> dict:
        if not self.state.is_active:
            raise RuntimeError("Vault is not active")
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        share_price = await self.get_share_price()
        new_shares = amount / share_price

        if depositor_address in self.state.depositors:
            dep = self.state.depositors[depositor_address]
            dep.shares += new_shares
            dep.deposited_amount += amount
        else:
            self.state.depositors[depositor_address] = Depositor(
                address=depositor_address,
                shares=new_shares,
                deposited_amount=amount,
                deposit_time=int(time.time() * 1000),
            )

        self.state.total_shares += new_shares
        self.state.total_deposited += amount
        self._save_state()

        logger.info(f"Deposit: {depositor_address} deposited ${amount:.2f}, received {new_shares:.6f} shares")
        return {
            "depositor": depositor_address,
            "amount": amount,
            "shares_received": new_shares,
            "share_price": share_price,
            "total_shares": self.state.depositors[depositor_address].shares,
        }

    async def withdraw(self, depositor_address: str, shares_to_redeem: Optional[float] = None) -> dict:
        dep = self.state.depositors.get(depositor_address)
        if not dep:
            raise ValueError(f"No deposits found for {depositor_address}")

        if shares_to_redeem is None:
            shares_to_redeem = dep.shares

        if shares_to_redeem > dep.shares:
            raise ValueError(f"Insufficient shares: have {dep.shares}, requested {shares_to_redeem}")

        share_price = await self.get_share_price()
        withdrawal_amount = shares_to_redeem * share_price

        pct_of_vault = shares_to_redeem / self.state.total_shares if self.state.total_shares > 0 else 0
        if pct_of_vault > 0.1:
            await self._close_proportional_positions(pct_of_vault)

        dep.shares -= shares_to_redeem
        self.state.total_shares -= shares_to_redeem

        if dep.shares <= 0.000001:
            del self.state.depositors[depositor_address]

        self._save_state()

        logger.info(
            f"Withdrawal: {depositor_address} redeemed {shares_to_redeem:.6f} shares "
            f"for ${withdrawal_amount:.2f}"
        )
        return {
            "depositor": depositor_address,
            "shares_redeemed": shares_to_redeem,
            "amount_received": withdrawal_amount,
            "share_price": share_price,
            "remaining_shares": dep.shares if depositor_address in self.state.depositors else 0,
        }

    async def _close_proportional_positions(self, fraction: float):
        for symbol, pos in list(self.strategy.active_positions.items()):
            close_size = pos.size * fraction
            if close_size <= 0:
                continue
            try:
                close_side = "bid" if pos.side == "short" else "ask"
                await self.client.create_market_order(
                    symbol=symbol,
                    side=close_side,
                    amount=f"{close_size:.6f}",
                    slippage_percent="0.5",
                    reduce_only=True,
                )
                pos.size -= close_size
                logger.info(f"Closed {fraction*100:.1f}% of {symbol} position for withdrawal")
            except Exception as e:
                logger.error(f"Failed to close proportional position {symbol}: {e}")

    async def calculate_pnl(self) -> dict:
        vault_value = await self.get_total_vault_value()
        total_deposited = self.state.total_deposited

        strategy_status = self.strategy.get_status()
        funding_earned = strategy_status.get("total_funding_earned", 0.0)

        net_pnl = vault_value - total_deposited
        pnl_pct = (net_pnl / total_deposited * 100) if total_deposited > 0 else 0.0

        age_hours = 0.0
        if self.state.created_at > 0:
            age_hours = (time.time() * 1000 - self.state.created_at) / (3600 * 1000)
        annualized_return = (pnl_pct / age_hours * 8760) if age_hours > 1 else 0.0

        self.state.total_funding_earned = funding_earned
        self._save_state()

        share_price = await self.get_share_price()
        return {
            "vault_value": vault_value,
            "total_deposited": total_deposited,
            "net_pnl": net_pnl,
            "pnl_pct": pnl_pct,
            "funding_earned": funding_earned,
            "fees_paid": self.state.total_fees_paid,
            "annualized_return": annualized_return,
            "share_price": share_price,
            "total_shares": self.state.total_shares,
            "depositor_count": len(self.state.depositors),
            "age_hours": age_hours,
        }

    async def run_strategy_cycle(self) -> dict:
        strategy_result = await self.strategy.run_cycle()
        rebalance_result = await self.rebalancer.run_check()
        pnl = await self.calculate_pnl()
        return {
            "strategy": strategy_result,
            "rebalances": rebalance_result,
            "pnl": pnl,
            "timestamp": int(time.time() * 1000),
        }

    async def get_vault_info(self) -> dict:
        pnl = await self.calculate_pnl()
        return {
            "vault_id": self.vault_id,
            "is_active": self.state.is_active,
            "created_at": self.state.created_at,
            "total_deposited": self.state.total_deposited,
            "vault_value": pnl["vault_value"],
            "share_price": pnl["share_price"],
            "total_shares": self.state.total_shares,
            "net_pnl": pnl["net_pnl"],
            "pnl_pct": pnl["pnl_pct"],
            "annualized_return": pnl["annualized_return"],
            "depositor_count": len(self.state.depositors),
            "active_positions": len(self.strategy.active_positions),
        }
