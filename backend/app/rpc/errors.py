from typing import Any

from app.errors import BitScopeError


BITCOIN_CORE_ERROR_MAP = {
    -28: (
        "BITCOIN_CORE_IN_WARMUP",
        "Bitcoin Core is starting up and not ready to answer RPC requests yet.",
        503,
    ),
    -18: (
        "WALLET_NOT_LOADED",
        "The wallet is not loaded. Load a wallet first from the Wallet page.",
        404,
    ),
    -13: (
        "WALLET_UNLOCK_NEEDED",
        "The wallet needs to be unlocked before this operation can continue.",
        400,
    ),
    -8: (
        "INVALID_RPC_PARAMETER",
        "Bitcoin Core rejected one or more RPC parameters.",
        400,
    ),
    -5: (
        "BITCOIN_CORE_NOT_FOUND",
        "Bitcoin Core could not find the requested block, transaction, address, or wallet item.",
        404,
    ),
}


class RpcError(BitScopeError):
    pass


def map_rpc_error(method: str, error: dict[str, Any]) -> RpcError:
    code = error.get("code")
    message = str(error.get("message") or "Bitcoin Core returned an RPC error.")
    app_code, friendly_message, status_code = BITCOIN_CORE_ERROR_MAP.get(
        code,
        ("BITCOIN_CORE_RPC_ERROR", "Bitcoin Core returned an RPC error.", 502),
    )

    return RpcError(
        code=app_code,
        message=friendly_message,
        status_code=status_code,
        details={
            "rpc_method": method,
            "rpc_code": code,
            "rpc_message": message,
        },
    )
