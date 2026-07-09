import pytest

from app.errors import BitScopeError
from app.rpc.errors import RpcError
from app.services.address_service import ADDRESS_LIMITATION, AddressService


class FakeSettings:
    def __init__(self) -> None:
        self.bitcoin_network = "regtest"
        self.bitcoin_rpc_wallet = ""


class FakeRpcClient:
    def __init__(self, responses: dict[str, object], failing_methods: set[str] | None = None) -> None:
        self.settings = FakeSettings()
        self.responses = responses
        self.failing_methods = failing_methods or set()
        self.calls: list[tuple[str, list[object]]] = []

    def call(self, method: str, params: list[object]) -> object:
        self.calls.append((method, params))
        if method in self.failing_methods:
            raise RpcError(
                code="WALLET_NOT_LOADED",
                message="Wallet RPC unavailable.",
                status_code=404,
                details={"rpc_method": method},
            )
        return self.responses[method]


def test_valid_non_wallet_address_returns_validation_and_limitation() -> None:
    rpc = FakeRpcClient(
        responses={
            "validateaddress": {
                "isvalid": True,
                "address": "bcrt1qexample",
                "scriptPubKey": "0014abcd",
                "iswitness": True,
                "witness_version": 0,
                "witness_program": "abcd",
            },
        },
        failing_methods={"getaddressinfo", "listunspent", "getreceivedbyaddress"},
    )

    result = AddressService(rpc).get_address(" bcrt1qexample ")  # type: ignore[arg-type]

    assert result["address"] == "bcrt1qexample"
    assert result["is_valid"] is True
    assert result["address_type"] == "witness_v0"
    assert result["script_pub_key"] == "0014abcd"
    assert result["utxos"] == []
    assert result["received_btc"] is None
    assert result["limitation"] == ADDRESS_LIMITATION


def test_invalid_address_is_rejected() -> None:
    rpc = FakeRpcClient(responses={"validateaddress": {"isvalid": False}})

    with pytest.raises(BitScopeError) as exc_info:
        AddressService(rpc).get_address("not-an-address")  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_ADDRESS"
    assert exc_info.value.status_code == 400


def test_wallet_owned_address_includes_received_amount_and_utxos() -> None:
    rpc = FakeRpcClient(
        responses={
            "validateaddress": {
                "isvalid": True,
                "scriptPubKey": "0014abcd",
                "iswitness": True,
                "witness_version": 0,
            },
            "getaddressinfo": {
                "scriptPubKey": "0014abcd",
                "ismine": True,
                "iswatchonly": False,
                "solvable": True,
                "desc": "wpkh([abcd/84h/1h/0h]02abcd)#test",
            },
            "listunspent": [
                {
                    "txid": "00" * 32,
                    "vout": 1,
                    "amount": 1.25,
                    "confirmations": 101,
                    "spendable": True,
                    "solvable": True,
                    "safe": True,
                    "desc": "wpkh(02abcd)#test",
                }
            ],
            "getreceivedbyaddress": 1.25,
        },
    )
    rpc.settings.bitcoin_rpc_wallet = "test-wallet"

    result = AddressService(rpc).get_address("bcrt1qmine")  # type: ignore[arg-type]

    assert result["is_mine"] is True
    assert result["wallet_name"] == "test-wallet"
    assert result["received_btc"] == 1.25
    assert result["limitation"] is None
    assert result["utxos"] == [
        {
            "txid": "00" * 32,
            "vout": 1,
            "amount_btc": 1.25,
            "confirmations": 101,
            "spendable": True,
            "solvable": True,
            "safe": True,
            "descriptor": "wpkh(02abcd)#test",
        }
    ]
