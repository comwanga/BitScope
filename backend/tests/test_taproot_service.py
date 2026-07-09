import pytest

from app.errors import BitScopeError
from app.services.taproot_service import TaprootService


OUTPUT_KEY = "11" * 32
P2TR_SCRIPT = f"5120{OUTPUT_KEY}"


class FakeRpcClient:
    def __init__(self, valid_address: bool = True) -> None:
        self.valid_address = valid_address
        self.calls: list[tuple[str, list[object] | None]] = []

    def call(self, method: str, params: list[object] | None = None) -> object:
        self.calls.append((method, params))
        if method == "validateaddress":
            return {
                "isvalid": self.valid_address,
                "address": params[0] if params else "",
                "scriptPubKey": P2TR_SCRIPT,
                "iswitness": True,
                "witness_version": 1,
                "witness_program": OUTPUT_KEY,
            }
        if method == "decodescript":
            return {"asm": f"1 {OUTPUT_KEY}", "type": "witness_v1_taproot"}
        raise AssertionError(f"unexpected method {method}")


def test_inspect_taproot_script_identifies_output_key() -> None:
    rpc = FakeRpcClient()

    result = TaprootService(rpc).inspect(script_hex=P2TR_SCRIPT)  # type: ignore[arg-type]

    assert result["is_taproot"] is True
    assert result["witness_version"] == 1
    assert result["output_key"] == OUTPUT_KEY
    assert rpc.calls == [("decodescript", [P2TR_SCRIPT])]


def test_inspect_address_uses_validateaddress_and_decodes_script() -> None:
    rpc = FakeRpcClient()

    result = TaprootService(rpc).inspect(address="bcrt1ptaproot")  # type: ignore[arg-type]

    assert result["is_taproot"] is True
    assert result["script_hex"] == P2TR_SCRIPT
    assert rpc.calls == [
        ("validateaddress", ["bcrt1ptaproot"]),
        ("decodescript", [P2TR_SCRIPT]),
    ]


def test_inspect_rejects_invalid_address() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        TaprootService(FakeRpcClient(valid_address=False)).inspect(address="bad")  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_ADDRESS"


def test_inspect_requires_input() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        TaprootService(FakeRpcClient()).inspect()  # type: ignore[arg-type]

    assert exc_info.value.code == "TAPROOT_INPUT_REQUIRED"
