import os
import uuid
from collections.abc import Generator

import pytest

from app.config import Settings
from app.rpc.client import BitcoinRpcClient


@pytest.fixture(scope="session")
def live_rpc_client() -> Generator[BitcoinRpcClient, None, None]:
    if os.getenv("BITSCOPE_LIVE_RPC_TESTS") != "1":
        pytest.skip("Set BITSCOPE_LIVE_RPC_TESTS=1 to run live Bitcoin Core RPC tests.")

    settings = Settings()
    if settings.bitcoin_network != "regtest":
        pytest.fail("Live RPC tests were enabled but BITCOIN_NETWORK is not regtest.")

    with BitcoinRpcClient(settings=settings) as client:
        chain = client.call("getblockchaininfo")
        if not isinstance(chain, dict) or chain.get("chain") != "regtest":
            pytest.fail("Live RPC tests were enabled but the connected Bitcoin Core node is not on regtest.")
        yield client


@pytest.fixture()
def isolated_wallet(live_rpc_client: BitcoinRpcClient) -> Generator[str, None, None]:
    wallet_name = f"bitscope-test-{uuid.uuid4().hex[:12]}"
    live_rpc_client.call("createwallet", [wallet_name, False, False, "", False, False, True])
    try:
        yield wallet_name
    finally:
        live_rpc_client.call("unloadwallet", [], wallet_name=wallet_name)


@pytest.fixture()
def mature_wallet(live_rpc_client: BitcoinRpcClient, isolated_wallet: str) -> str:
    ensure_mature_balance(live_rpc_client, isolated_wallet, minimum_btc=1.0)
    return isolated_wallet


def ensure_mature_balance(client: BitcoinRpcClient, wallet_name: str, minimum_btc: float) -> None:
    balances = client.call("getbalances", [], wallet_name=wallet_name)
    trusted = _wallet_balance(balances, "trusted")
    if trusted >= minimum_btc:
        return

    address = client.call("getnewaddress", ["bitscope-test-maturity", "bech32"], wallet_name=wallet_name)
    assert isinstance(address, str)
    client.call("generatetoaddress", [101, address])

    balances = client.call("getbalances", [], wallet_name=wallet_name)
    trusted = _wallet_balance(balances, "trusted")
    assert trusted >= minimum_btc, (
        "Test wallet still has insufficient mature balance after mining. "
        f"trusted={trusted}, required={minimum_btc}"
    )


def _wallet_balance(value: object, key: str) -> float:
    if not isinstance(value, dict):
        return 0.0
    mine = value.get("mine")
    if not isinstance(mine, dict):
        return 0.0
    balance = mine.get(key)
    return float(balance) if isinstance(balance, int | float) and not isinstance(balance, bool) else 0.0
