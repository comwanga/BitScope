from app.rpc.client import BitcoinRpcClient
from app.rpc.types import JsonValue


FEE_TARGETS = [1, 3, 6, 12]


class FeeService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def estimates(self, targets: list[int] | None = None) -> dict[str, object]:
        selected_targets = targets or FEE_TARGETS
        estimates: list[dict[str, object]] = []
        raw: dict[str, object] = {}

        for target in selected_targets:
            result = self._as_dict(self.rpc_client.call("estimatesmartfee", [target]))
            raw[str(target)] = result
            btc_per_kvb = result.get("feerate")
            errors = [error for error in result.get("errors", []) if isinstance(error, str)] if isinstance(result.get("errors"), list) else []

            estimates.append(
                {
                    "target_blocks": target,
                    "btc_per_kvb": float(btc_per_kvb) if isinstance(btc_per_kvb, int | float) else None,
                    "sats_per_vbyte": self.btc_per_kvb_to_sats_per_vbyte(btc_per_kvb)
                    if isinstance(btc_per_kvb, int | float)
                    else None,
                    "available": isinstance(btc_per_kvb, int | float),
                    "errors": errors,
                }
            )

        return {
            "estimates": estimates,
            "cli_commands": [f"bitcoin-cli estimatesmartfee {target}" for target in selected_targets],
            "rpc_methods": ["estimatesmartfee"],
            "concepts": ["Fee", "Fee rate", "Virtual bytes", "Mempool", "Confirmation target"],
            "explanation": (
                "Bitcoin Core estimates feerates from recent block and mempool behavior. On regtest or quiet nodes, "
                "estimates are often unavailable because there is no meaningful fee market history."
            ),
            "raw": raw,
        }

    @staticmethod
    def btc_per_kvb_to_sats_per_vbyte(btc_per_kvb: int | float) -> float:
        return float(btc_per_kvb) * 100_000

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}
