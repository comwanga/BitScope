import pytest

from app.errors import BitScopeError
from app.services.descriptor_service import DescriptorService


class FakeRpcClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object] | None, str | None]] = []

    def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
        self.calls.append((method, params, wallet_name))
        if method == "getdescriptorinfo":
            descriptor = params[0] if params else ""
            return {
                "descriptor": descriptor,
                "checksum": "abcd1234",
                "isrange": "*" in str(descriptor),
                "issolvable": True,
                "hasprivatekeys": False,
            }
        if method == "deriveaddresses":
            return ["bcrt1qone", "bcrt1qtwo"]
        if method == "listdescriptors":
            return {
                "wallet_name": "demo",
                "descriptors": [
                    {
                        "desc": "wpkh([abcd/84h/1h/0h]xpub/0/*)#12345678",
                        "active": True,
                        "internal": False,
                        "range": [0, 999],
                        "next": 4,
                        "timestamp": "now",
                    }
                ],
            }
        raise AssertionError(f"unexpected method {method}")


def test_analyze_descriptor_normalizes_without_derivation() -> None:
    rpc = FakeRpcClient()

    result = DescriptorService(rpc).analyze("raw(51)")  # type: ignore[arg-type]

    assert result["checksum"] == "abcd1234"
    assert result["is_range"] is False
    assert result["derived_addresses"] == []
    assert rpc.calls == [("getdescriptorinfo", ["raw(51)"], None)]


def test_analyze_ranged_descriptor_derives_addresses() -> None:
    rpc = FakeRpcClient()

    result = DescriptorService(rpc).analyze("wpkh(xpub/0/*)", 0, 1)  # type: ignore[arg-type]

    assert result["is_range"] is True
    assert result["derived_addresses"] == ["bcrt1qone", "bcrt1qtwo"]
    assert rpc.calls == [
        ("getdescriptorinfo", ["wpkh(xpub/0/*)"], None),
        ("deriveaddresses", ["wpkh(xpub/0/*)", [0, 1]], None),
    ]


def test_analyze_rejects_range_for_non_ranged_descriptor() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        DescriptorService(FakeRpcClient()).analyze("raw(51)", 0, 1)  # type: ignore[arg-type]

    assert exc_info.value.code == "DESCRIPTOR_NOT_RANGE"


def test_analyze_rejects_large_derivation_range() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        DescriptorService(FakeRpcClient()).analyze("wpkh(xpub/0/*)", 0, 50)  # type: ignore[arg-type]

    assert exc_info.value.code == "DESCRIPTOR_RANGE_TOO_LARGE"


def test_wallet_descriptors_lists_public_descriptors() -> None:
    rpc = FakeRpcClient()

    result = DescriptorService(rpc).wallet_descriptors("demo")  # type: ignore[arg-type]

    assert result["wallet_name"] == "demo"
    assert result["descriptors"][0]["active"] is True  # type: ignore[index]
    assert result["descriptors"][0]["range"] == [0, 999]  # type: ignore[index]
    assert rpc.calls == [("listdescriptors", [False], "demo")]
