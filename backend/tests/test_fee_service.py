from app.services.fee_service import FeeService


class FakeRpcClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[int]]] = []

    def call(self, method: str, params: list[int]) -> dict[str, object]:
        self.calls.append((method, params))
        target = params[0]
        if target == 1:
            return {"feerate": 0.00021, "blocks": 2}
        return {"errors": ["Insufficient data or no feerate found"], "blocks": target}


def test_btc_per_kvb_to_sats_per_vbyte() -> None:
    assert FeeService.btc_per_kvb_to_sats_per_vbyte(0.00021) == 21.0


def test_fee_estimates_normalize_available_and_unavailable_results() -> None:
    rpc = FakeRpcClient()

    result = FeeService(rpc).estimates([1, 3])  # type: ignore[arg-type]

    assert result["estimates"][0]["available"] is True  # type: ignore[index]
    assert result["estimates"][0]["btc_per_kvb"] == 0.00021  # type: ignore[index]
    assert result["estimates"][0]["sats_per_vbyte"] == 21.0  # type: ignore[index]
    assert result["estimates"][1]["available"] is False  # type: ignore[index]
    assert result["estimates"][1]["errors"] == ["Insufficient data or no feerate found"]  # type: ignore[index]
    assert rpc.calls == [("estimatesmartfee", [1]), ("estimatesmartfee", [3])]
