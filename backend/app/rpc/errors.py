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
    -6: (
        "RPC_INSUFFICIENT_FUNDS",
        "The wallet does not have enough spendable Bitcoin Core balance for this transaction.",
        400,
    ),
    -4: (
        "BITCOIN_CORE_WALLET_ERROR",
        "Bitcoin Core could not complete this wallet operation.",
        400,
    ),
    -5: (
        "BITCOIN_CORE_NOT_FOUND",
        "Bitcoin Core could not find the requested block, transaction, address, or wallet item.",
        404,
    ),
    -26: (
        "TRANSACTION_REJECTED_BY_POLICY",
        "Bitcoin Core rejected this transaction by consensus or mempool policy.",
        400,
    ),
    -25: (
        "TRANSACTION_REJECTED",
        "Bitcoin Core rejected or could not verify this transaction.",
        400,
    ),
}


class RpcError(BitScopeError):
    pass


def map_rpc_error(method: str, error: dict[str, Any]) -> RpcError:
    code = error.get("code")
    message = str(error.get("message") or "Bitcoin Core returned an RPC error.")
    message_lower = message.lower()
    app_code, friendly_message, status_code = BITCOIN_CORE_ERROR_MAP.get(
        code,
        ("BITCOIN_CORE_RPC_ERROR", "Bitcoin Core returned an RPC error.", 502),
    )
    if code in {-4, -6} and "insufficient funds" in message_lower:
        app_code = "RPC_INSUFFICIENT_FUNDS"
        friendly_message = (
            "The wallet does not have enough spendable balance. On regtest, mine enough blocks to the sending wallet "
            "and wait for coinbase rewards to reach 101 confirmations before spending them."
        )
        status_code = 400
    elif code == -4 and ("immature" in message_lower or "mature" in message_lower):
        app_code = "RPC_IMMATURE_COINBASE"
        friendly_message = (
            "The wallet is trying to spend immature coinbase rewards. Mine additional regtest blocks until the rewards "
            "have 101 confirmations, then retry."
        )
        status_code = 400
    elif code == -5 and ("invalid address" in message_lower or "invalid bitcoin address" in message_lower):
        app_code = "RPC_INVALID_ADDRESS_OR_KEY"
        friendly_message = (
            "Bitcoin Core rejected the address or key. Regtest addresses from an old node reset are stale; generate a fresh address "
            "from the current wallet and try again."
        )
        status_code = 400

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
