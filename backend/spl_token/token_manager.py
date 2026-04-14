"""
SPL Token Manager for PerpYield Vault Shares

This module handles the creation and management of SPL tokens that represent
vault shares. These tokens are composable across Solana DeFi.

For the hackathon demo, some functions are mocked but show the full implementation
structure. In production, these would use solana-py and real RPC calls.
"""

import logging
import time
from typing import Optional, Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Information about a vault share token."""
    mint_address: str
    vault_id: str
    name: str
    symbol: str
    decimals: int = 6
    total_supply: float = 0.0
    holders: Dict[str, float] = field(default_factory=dict)


@dataclass
class TokenTransaction:
    """Record of a token transaction."""
    tx_hash: str
    type: str  # mint, burn, transfer
    from_address: Optional[str]
    to_address: Optional[str]
    amount: float
    timestamp: int


class SPLTokenManager:
    """
    Manages SPL tokens for vault shares.

    Each vault gets its own SPL token mint. When users deposit, they receive
    SPL tokens representing their share of the vault. These tokens can be:
    - Transferred to other users (secondary market)
    - Used as collateral in lending protocols
    - Lend on platforms like Kamino
    - Traded on DEXs
    """

    # Mock token database for demo
    _tokens: Dict[str, TokenInfo] = {}
    _transactions: List[TokenTransaction] = []
    _mock_counter: int = 0

    def __init__(self, rpc_url: Optional[str] = None, network: str = "testnet"):
        self.rpc_url = rpc_url or "https://api.testnet.solana.com"
        self.network = network
        self._load_mock_data()

    def _load_mock_data(self):
        """Load any existing token data (mock for demo)."""
        # In production, this would load from a database or on-chain
        pass

    def _generate_mock_address(self, prefix: str = "token") -> str:
        """Generate a mock Solana address for demo purposes."""
        self._mock_counter += 1
        # Real Solana addresses are base58-encoded 32-byte arrays
        # This creates a realistic-looking mock address
        return f"{prefix}{self._mock_counter}{'x' * (32 - len(prefix) - len(str(self._mock_counter)))}"

    def _generate_mock_tx_hash(self) -> str:
        """Generate a mock transaction hash."""
        import hashlib
        data = f"tx{time.time()}{self._mock_counter}"
        return hashlib.sha256(data.encode()).hexdigest()[:44]  # Solana sig length

    async def create_share_token(
        self,
        vault_id: str,
        vault_name: str,
        creator_address: str
    ) -> Dict:
        """
        Create a new SPL token mint for vault shares.

        In production, this would:
        1. Create a new SPL token mint using spl-token program
        2. Set mint authority to the vault program
        3. Initialize metadata (name, symbol, decimals)
        4. Store the mint address in the vault state

        For demo, returns mock data showing the structure.
        """
        logger.info(f"Creating SPL token for vault {vault_id}")

        # Generate mock mint address
        mint_address = self._generate_mock_address("PYIELD")

        # Create token info
        token_info = TokenInfo(
            mint_address=mint_address,
            vault_id=vault_id,
            name=f"PerpYield {vault_name}",
            symbol=f"PY{vault_id[:4].upper()}",
            decimals=6,
            total_supply=0.0,
            holders={}
        )

        self._tokens[vault_id] = token_info

        # Mock transaction hash
        tx_hash = self._generate_mock_tx_hash()

        return {
            "success": True,
            "mint_address": mint_address,
            "vault_id": vault_id,
            "name": token_info.name,
            "symbol": token_info.symbol,
            "decimals": token_info.decimals,
            "tx_hash": tx_hash,
            "explorer_url": f"https://explorer.solana.com/tx/{tx_hash}?cluster={self.network}",
            "note": "Demo mode - SPL token creation simulated. In production, this creates a real SPL token on Solana."
        }

    async def mint_shares(
        self,
        vault_id: str,
        to_address: str,
        amount: float
    ) -> Dict:
        """
        Mint vault share tokens to a depositor.

        Called when a user deposits into the vault. Mints new SPL tokens
        representing their share of the vault.

        In production, this would:
        1. Call spl-token mint-to instruction
        2. Update the recipient's token account balance
        3. Increase total supply
        """
        logger.info(f"Minting {amount} shares for vault {vault_id} to {to_address}")

        token = self._tokens.get(vault_id)
        if not token:
            return {
                "success": False,
                "error": f"Token for vault {vault_id} not found. Create token first."
            }

        # Update holder balance
        current_balance = token.holders.get(to_address, 0.0)
        token.holders[to_address] = current_balance + amount
        token.total_supply += amount

        # Record transaction
        tx = TokenTransaction(
            tx_hash=self._generate_mock_tx_hash(),
            type="mint",
            from_address=None,
            to_address=to_address,
            amount=amount,
            timestamp=int(time.time() * 1000)
        )
        self._transactions.append(tx)

        return {
            "success": True,
            "vault_id": vault_id,
            "to_address": to_address,
            "amount": amount,
            "total_balance": token.holders[to_address],
            "tx_hash": tx.tx_hash,
            "mint_address": token.mint_address,
            "note": "Demo mode - minting simulated. In production, this mints real SPL tokens."
        }

    async def burn_shares(
        self,
        vault_id: str,
        from_address: str,
        amount: float
    ) -> Dict:
        """
        Burn vault share tokens on withdrawal.

        Called when a user withdraws from the vault. Burns their SPL tokens
        and returns the underlying assets.

        In production, this would:
        1. Call spl-token burn instruction
        2. Decrease the sender's token account balance
        3. Decrease total supply
        """
        logger.info(f"Burning {amount} shares for vault {vault_id} from {from_address}")

        token = self._tokens.get(vault_id)
        if not token:
            return {
                "success": False,
                "error": f"Token for vault {vault_id} not found."
            }

        current_balance = token.holders.get(from_address, 0.0)
        if current_balance < amount:
            return {
                "success": False,
                "error": f"Insufficient balance: {current_balance} < {amount}"
            }

        # Update holder balance
        token.holders[from_address] = current_balance - amount
        token.total_supply -= amount

        # Record transaction
        tx = TokenTransaction(
            tx_hash=self._generate_mock_tx_hash(),
            type="burn",
            from_address=from_address,
            to_address=None,
            amount=amount,
            timestamp=int(time.time() * 1000)
        )
        self._transactions.append(tx)

        return {
            "success": True,
            "vault_id": vault_id,
            "from_address": from_address,
            "amount": amount,
            "remaining_balance": token.holders[from_address],
            "tx_hash": tx.tx_hash,
            "note": "Demo mode - burning simulated. In production, this burns real SPL tokens."
        }

    async def transfer_shares(
        self,
        vault_id: str,
        from_address: str,
        to_address: str,
        amount: float
    ) -> Dict:
        """
        Transfer vault shares between users (secondary market).

        Enables P2P trading of vault positions without withdrawing from the vault.

        In production, this would:
        1. Call spl-token transfer instruction
        2. Decrease sender's balance, increase recipient's balance
        3. Total supply remains unchanged
        """
        logger.info(f"Transferring {amount} shares from {from_address} to {to_address}")

        token = self._tokens.get(vault_id)
        if not token:
            return {
                "success": False,
                "error": f"Token for vault {vault_id} not found."
            }

        # Check sender balance
        sender_balance = token.holders.get(from_address, 0.0)
        if sender_balance < amount:
            return {
                "success": False,
                "error": f"Insufficient balance: {sender_balance} < {amount}"
            }

        # Update balances
        token.holders[from_address] = sender_balance - amount
        recipient_balance = token.holders.get(to_address, 0.0)
        token.holders[to_address] = recipient_balance + amount

        # Record transaction
        tx = TokenTransaction(
            tx_hash=self._generate_mock_tx_hash(),
            type="transfer",
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            timestamp=int(time.time() * 1000)
        )
        self._transactions.append(tx)

        return {
            "success": True,
            "vault_id": vault_id,
            "from_address": from_address,
            "to_address": to_address,
            "amount": amount,
            "tx_hash": tx.tx_hash,
            "note": "Demo mode - transfer simulated. In production, this transfers real SPL tokens."
        }

    async def get_token_balance(
        self,
        vault_id: str,
        address: str
    ) -> Dict:
        """Get SPL token balance for a specific address."""
        token = self._tokens.get(vault_id)
        if not token:
            return {
                "success": False,
                "error": f"Token for vault {vault_id} not found."
            }

        balance = token.holders.get(address, 0.0)
        share_of_vault = (balance / token.total_supply * 100) if token.total_supply > 0 else 0

        return {
            "success": True,
            "vault_id": vault_id,
            "address": address,
            "token_balance": balance,
            "mint_address": token.mint_address,
            "symbol": token.symbol,
            "decimals": token.decimals,
            "share_of_vault_pct": round(share_of_vault, 4),
            "total_supply": token.total_supply,
        }

    async def get_token_info(self, vault_id: str) -> Optional[Dict]:
        """Get information about a vault's share token."""
        token = self._tokens.get(vault_id)
        if not token:
            return None

        return {
            "mint_address": token.mint_address,
            "vault_id": token.vault_id,
            "name": token.name,
            "symbol": token.symbol,
            "decimals": token.decimals,
            "total_supply": token.total_supply,
            "holder_count": len(token.holders),
            "network": self.network,
        }

    async def get_all_balances(self, vault_id: str) -> Dict:
        """Get all token holder balances for a vault."""
        token = self._tokens.get(vault_id)
        if not token:
            return {
                "success": False,
                "error": f"Token for vault {vault_id} not found."
            }

        return {
            "success": True,
            "vault_id": vault_id,
            "mint_address": token.mint_address,
            "total_supply": token.total_supply,
            "holder_count": len(token.holders),
            "holders": token.holders,
        }

    async def get_transaction_history(
        self,
        vault_id: Optional[str] = None,
        address: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get token transaction history, optionally filtered."""
        filtered = self._transactions

        if vault_id:
            # Filter by vault would require storing vault_id in transaction
            pass

        if address:
            filtered = [tx for tx in filtered
                       if tx.from_address == address or tx.to_address == address]

        # Sort by timestamp descending and limit
        sorted_txs = sorted(filtered, key=lambda x: x.timestamp, reverse=True)[:limit]

        return [
            {
                "tx_hash": tx.tx_hash,
                "type": tx.type,
                "from": tx.from_address,
                "to": tx.to_address,
                "amount": tx.amount,
                "timestamp": tx.timestamp,
            }
            for tx in sorted_txs
        ]

    # ===== Composability Features =====

    async def prepare_collateral_deposit(
        self,
        vault_id: str,
        lending_protocol: str,  # e.g., "kamino", "solend", "marginfi"
        amount: float
    ) -> Dict:
        """
        Prepare to use vault shares as collateral in a lending protocol.

        This is a simulation showing how composability would work. In production,
        this would interact with the lending protocol's deposit instructions.
        """
        return {
            "success": True,
            "action": "prepare_collateral",
            "vault_id": vault_id,
            "lending_protocol": lending_protocol,
            "amount": amount,
            "steps": [
                "1. Transfer shares to lending protocol's custody account",
                "2. Lending protocol mints receipt tokens representing collateral",
                "3. User can now borrow against their vault share collateral",
                "4. Yield continues accruing to the collateralized shares",
            ],
            "note": "Demo mode - collateral preparation simulated. In production, this would interact with Solana lending protocols.",
        }

    async def get_composability_options(self, vault_id: str) -> Dict:
        """Get available DeFi composability options for vault shares."""
        token = self._tokens.get(vault_id)
        if not token:
            return {"success": False, "error": "Token not found"}

        return {
            "success": True,
            "vault_id": vault_id,
            "token_symbol": token.symbol,
            "composability_options": [
                {
                    "protocol": "Kamino",
                    "action": "Lend shares to earn additional yield",
                    "apy_boost": "+2-5%",
                    "available": True,
                },
                {
                    "protocol": "Solend",
                    "action": "Use as collateral for borrowing",
                    "ltv": "Up to 70%",
                    "available": True,
                },
                {
                    "protocol": "Drift",
                    "action": "Trade perpetuals using share collateral",
                    "leverage": "Up to 5x",
                    "available": True,
                },
                {
                    "protocol": "Jupiter",
                    "action": "Swap shares for other tokens",
                    "route": "Direct or via USDC",
                    "available": True,
                },
            ],
            "note": "These are example integrations. Real integrations require protocol partnerships."
        }
