from app.errors import error_payload


def test_error_payload_uses_consistent_shape() -> None:
    payload = error_payload(
        code="BITCOIN_CORE_OFFLINE",
        message="Bitcoin Core is not reachable.",
        details={"hint": "Start bitcoind."},
    )

    assert payload == {
        "error": True,
        "code": "BITCOIN_CORE_OFFLINE",
        "message": "Bitcoin Core is not reachable.",
        "details": {"hint": "Start bitcoind."},
    }
