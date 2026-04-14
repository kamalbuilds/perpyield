import os
from dotenv import load_dotenv

load_dotenv()

PACIFICA_PRIVATE_KEY = os.getenv("PACIFICA_PRIVATE_KEY", "")
PACIFICA_PUBLIC_KEY = os.getenv("PACIFICA_PUBLIC_KEY", "")
PACIFICA_AGENT_WALLET = os.getenv("PACIFICA_AGENT_WALLET")
PACIFICA_BUILDER_CODE = os.getenv("PACIFICA_BUILDER_CODE")
PACIFICA_TESTNET = os.getenv("PACIFICA_TESTNET", "true").lower() == "true"

if PACIFICA_TESTNET:
    REST_BASE_URL = "https://test-api.pacifica.fi/api/v1"
    WS_BASE_URL = "wss://test-ws.pacifica.fi/ws"
else:
    REST_BASE_URL = "https://api.pacifica.fi/api/v1"
    WS_BASE_URL = "wss://ws.pacifica.fi/ws"

MIN_FUNDING_RATE_THRESHOLD = float(os.getenv("MIN_FUNDING_RATE", "0.0001"))
MAX_LEVERAGE = int(os.getenv("MAX_LEVERAGE", "3"))
REBALANCE_INTERVAL_SECONDS = int(os.getenv("REBALANCE_INTERVAL", "300"))
DELTA_THRESHOLD_PERCENT = float(os.getenv("DELTA_THRESHOLD", "5.0"))
VAULT_MANAGEMENT_FEE = 0.02
VAULT_PERFORMANCE_FEE = 0.20
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
