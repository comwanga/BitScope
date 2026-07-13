import pytest

from app.errors import BitScopeError
from app.services.wallet_service import WalletService


class FakeSettings:
    def __init__(self) -> None:
        self.bitcoin_rpc_wallet = ""
        self.bitcoin_network = "regtest"


class FakeRpcClient:
    def __init__(self, responses: dict[tuple[str, str | None], object] | dict[str, object]) -> None:
        self.settings = FakeSettings()
        self.responses = responses
        self.calls: list[tuple[str, list[object] | None, str | None]] = []

    def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
        if method == "getblockchaininfo":
            return {"chain": "regtest"}
        self.calls.append((method, params, wallet_name))
        keyed = self.responses.get((method, wallet_name)) if all(isinstance(key, tuple) for key in self.responses) else None
        if keyed is not None:
            return keyed
        return self.responses[method]  # type: ignore[index]


def test_summary_lists_loaded_and_available_wallets() -> None:
    rpc = FakeRpcClient(
        {
            "listwallets": ["demo"],
            "listwalletdir": {
                "wallets": [
                    {
                        "name": "demo",
                        "private_keys_enabled": True,
                        "descriptors": True,
                        "blank": False,
                    },
                    {"name": "cold", "private_keys_enabled": False},
                ]
            },
        }
    )
    rpc.settings.bitcoin_rpc_wallet = "demo"

    result = WalletService(rpc).summary()  # type: ignore[arg-type]

    assert result["loaded_wallets"] == ["demo"]
    assert result["configured_wallet"] == "demo"
    assert result["available_wallets"][0]["wallet_name"] == "demo"  # type: ignore[index]
    assert result["available_wallets"][0]["loaded"] is True  # type: ignore[index]
    assert result["available_wallets"][1]["loaded"] is False  # type: ignore[index]


def test_create_wallet_returns_warning_and_commands() -> None:
    rpc = FakeRpcClient({"createwallet": {"name": "demo", "warning": "passphrase disabled"}})

    result = WalletService(rpc).create_wallet(" demo ")  # type: ignore[arg-type]

    assert result["wallet_name"] == "demo"
    assert result["warning"] == "passphrase disabled"
    assert rpc.calls == [("createwallet", ["demo"], None)]


def test_balance_uses_wallet_specific_rpc_and_sums_mine_balances() -> None:
    rpc = FakeRpcClient(
        {
            ("getbalances", "demo"): {
                "mine": {
                    "trusted": 1.5,
                    "untrusted_pending": 0.25,
                    "immature": 50,
                }
            }
        }
    )

    result = WalletService(rpc).balance("demo")  # type: ignore[arg-type]

    assert result["trusted_btc"] == 1.5
    assert result["untrusted_pending_btc"] == 0.25
    assert result["immature_btc"] == 50.0
    assert result["total_btc"] == 51.75
    assert rpc.calls == [("getbalances", None, "demo")]


def test_new_address_validates_address_type() -> None:
    rpc = FakeRpcClient({})

    with pytest.raises(BitScopeError) as exc_info:
        WalletService(rpc).new_address("demo", "", "nested")  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_ADDRESS_TYPE"


def test_new_address_returns_address_from_wallet() -> None:
    rpc = FakeRpcClient({("getnewaddress", "demo"): "bcrt1qexample"})

    result = WalletService(rpc).new_address("demo", "lab", "bech32")  # type: ignore[arg-type]

    assert result["address"] == "bcrt1qexample"
    assert rpc.calls == [("getnewaddress", ["lab", "bech32"], "demo")]


def test_utxos_and_transactions_are_normalized() -> None:
    rpc = FakeRpcClient(
        {
            ("listunspent", "demo"): [
                {
                    "txid": "11" * 32,
                    "vout": 0,
                    "address": "bcrt1qexample",
                    "label": "lab",
                    "amount": 2.0,
                    "confirmations": 6,
                    "spendable": True,
                    "solvable": True,
                    "safe": True,
                }
            ],
            ("listtransactions", "demo"): [
                {
                    "txid": "22" * 32,
                    "category": "receive",
                    "address": "bcrt1qexample",
                    "amount": 2.0,
                    "confirmations": 6,
                    "time": 123,
                    "trusted": True,
                }
            ],
        }
    )

    utxos = WalletService(rpc).utxos("demo")  # type: ignore[arg-type]
    transactions = WalletService(rpc).transactions("demo", 10)  # type: ignore[arg-type]

    assert utxos["total_btc"] == 2.0
    assert utxos["utxos"][0]["address"] == "bcrt1qexample"  # type: ignore[index]
    assert transactions["transactions"][0]["category"] == "receive"  # type: ignore[index]
    assert rpc.calls == [
        ("listunspent", [0, 9999999], "demo"),
        ("listtransactions", ["*", 10, 0, True], "demo"),
    ]
