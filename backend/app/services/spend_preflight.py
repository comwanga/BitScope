from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient


FEE_HEADROOM_BTC = 0.00001


class SpendPreflight:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def validate_address(self, address: str, code: str, message: str) -> dict[str, object]:
        validation = self._as_dict(self.rpc_client.call("validateaddress", [address]))
        if validation.get("isvalid") is not True:
            raise BitScopeError(
                code=code,
                message=message,
                status_code=400,
                details={"address": address, "rpc_method": "validateaddress"},
            )
        return validation

    def require_mature_balance(
        self,
        wallet_name: str,
        amount_btc: float,
        code: str,
        message: str,
        fee_headroom_btc: float = FEE_HEADROOM_BTC,
    ) -> dict[str, object]:
        balances = self._as_dict(self.rpc_client.call("getbalances", [], wallet_name=wallet_name))
        mine_balance = self._as_dict(balances.get("mine"))
        trusted = self._optional_float(mine_balance.get("trusted")) or 0.0
        immature = self._optional_float(mine_balance.get("immature")) or 0.0
        requested = round(float(amount_btc), 8)
        required = round(requested + fee_headroom_btc, 8)
        if trusted < required:
            raise BitScopeError(
                code=code,
                message=message,
                status_code=400,
                details={
                    "wallet_name": wallet_name,
                    "trusted_btc": trusted,
                    "immature_btc": immature,
                    "requested_btc": requested,
                    "fee_headroom_btc": fee_headroom_btc,
                    "required_btc": required,
                    "minimum_coinbase_confirmations": 101,
                    "rpc_method": "getbalances",
                },
            )
        return {
            "getbalances": balances,
            "trusted_btc": trusted,
            "immature_btc": immature,
            "required_btc": required,
            "fee_headroom_btc": fee_headroom_btc,
        }

    @staticmethod
    def _as_dict(value: object) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _optional_float(value: object) -> float | None:
        return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None
