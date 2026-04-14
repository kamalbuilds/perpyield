import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from pacifica.client import PacificaClient
import config


def get_test_client() -> PacificaClient:
    return PacificaClient(
        private_key=config.PACIFICA_PRIVATE_KEY,
        testnet=config.PACIFICA_TESTNET,
        builder_code=config.PACIFICA_BUILDER_CODE,
        agent_wallet_key=config.PACIFICA_AGENT_WALLET,
    )


def has_wallet() -> bool:
    return bool(config.PACIFICA_PRIVATE_KEY and config.PACIFICA_PRIVATE_KEY.strip())


import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "requires_wallet: test needs PACIFICA_PRIVATE_KEY")


def pytest_collection_modifyitems(items):
    if has_wallet():
        return
    skip_wallet = pytest.mark.skip(reason="PACIFICA_PRIVATE_KEY not set")
    for item in items:
        if "requires_wallet" in item.keywords:
            item.add_marker(skip_wallet)
