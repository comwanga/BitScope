from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.types import JsonValue
from app.services.spend_preflight import SpendPreflight


class PsbtService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def create(self, wallet_name: str, recipient_address: str, amount_btc: float) -> dict[str, object]:
        clean_wallet = self._clean(wallet_name, "wallet name")
        clean_address = self._clean(recipient_address, "recipient address")
        amount = self._amount(amount_btc)
        preflight = SpendPreflight(self.rpc_client)
        validation = preflight.validate_address(
            clean_address,
            "INVALID_PSBT_RECIPIENT_ADDRESS",
            "Provide a valid recipient address from the current Bitcoin Core node before creating a funded PSBT.",
        )
        balance = preflight.require_mature_balance(
            clean_wallet,
            amount,
            "PSBT_INSUFFICIENT_MATURE_FUNDS",
            (
                "The wallet does not have enough mature spendable balance to fund this PSBT. Mine enough regtest blocks "
                "to this wallet so coinbase rewards reach 101 confirmations, then retry."
            ),
        )
        outputs = [{clean_address: amount}]
        result = self._as_dict(
            self.rpc_client.call(
                "walletcreatefundedpsbt",
                [[], outputs, 0, {"includeWatching": True}, True],
                wallet_name=clean_wallet,
            )
        )
        psbt = self._optional_str(result.get("psbt"))
        if psbt is None:
            raise BitScopeError(
                code="BITCOIN_CORE_INVALID_RESPONSE",
                message="Bitcoin Core did not return a PSBT.",
                status_code=502,
                details={"rpc_method": "walletcreatefundedpsbt"},
            )

        decoded = self.decode(psbt)

        return {
            "wallet_name": clean_wallet,
            "psbt": psbt,
            "fee_btc": self._optional_float(result.get("fee")),
            "change_position": self._optional_int(result.get("changepos")),
            "recipient_address": clean_address,
            "amount_btc": amount,
            "decoded": decoded,
            "cli_commands": [
                f"bitcoin-cli validateaddress {clean_address}",
                f"bitcoin-cli -rpcwallet={clean_wallet} getbalances",
                f"bitcoin-cli -rpcwallet={clean_wallet} walletcreatefundedpsbt [] '[{{\"{clean_address}\":{amount:.8f}}}]' 0 '{{\"includeWatching\":true}}' true",
                "bitcoin-cli decodepsbt <psbt>",
            ],
            "rpc_methods": ["validateaddress", "getbalances", "walletcreatefundedpsbt", "decodepsbt"],
            "concepts": ["PSBT", "Coin selection", "Change output", "Fee"],
            "explanation": (
                "Bitcoin Core selects wallet UTXOs and builds an unsigned funded PSBT. Nothing is broadcast; "
                "the PSBT must still be processed, finalized, and sent by a separate explicit action."
            ),
            "raw": {"validateaddress": validation, "getbalances": balance["getbalances"], "walletcreatefundedpsbt": result, "decodepsbt": decoded["raw"]["decodepsbt"]},
        }

    def decode(self, psbt: str) -> dict[str, object]:
        clean_psbt = self._clean(psbt, "PSBT")
        decoded = self._as_dict(self.rpc_client.call("decodepsbt", [clean_psbt]))
        tx = self._as_dict(decoded.get("tx"))
        inputs = decoded.get("inputs")
        outputs = decoded.get("outputs")

        return {
            "psbt": clean_psbt,
            "txid": self._optional_str(tx.get("txid")),
            "input_count": len(inputs) if isinstance(inputs, list) else 0,
            "output_count": len(outputs) if isinstance(outputs, list) else 0,
            "fee_btc": self._optional_float(decoded.get("fee")),
            "is_complete": self._optional_bool(decoded.get("complete")),
            "next_role": self._optional_str(decoded.get("next")),
            "cli_commands": ["bitcoin-cli decodepsbt <psbt>"],
            "rpc_methods": ["decodepsbt"],
            "concepts": ["PSBT", "Inputs", "Outputs", "Signer roles"],
            "explanation": "Decoding a PSBT reveals the unsigned transaction, known UTXO data, signatures, and the next role Bitcoin Core expects.",
            "raw": {"decodepsbt": decoded},
        }

    def process(self, wallet_name: str, psbt: str, sign: bool = True) -> dict[str, object]:
        clean_wallet = self._clean(wallet_name, "wallet name")
        clean_psbt = self._clean(psbt, "PSBT")
        if sign and self.rpc_client.settings.bitcoin_network == "mainnet":
            raise BitScopeError(
                code="MAINNET_SIGNING_DISABLED",
                message="PSBT signing is disabled on mainnet by default to protect real funds.",
                status_code=400,
            )

        result = self._as_dict(self.rpc_client.call("walletprocesspsbt", [clean_psbt, sign], wallet_name=clean_wallet))
        processed_psbt = self._optional_str(result.get("psbt"))
        if processed_psbt is None:
            raise BitScopeError(
                code="BITCOIN_CORE_INVALID_RESPONSE",
                message="Bitcoin Core did not return a processed PSBT.",
                status_code=502,
                details={"rpc_method": "walletprocesspsbt"},
            )
        decoded = self.decode(processed_psbt)

        return {
            "wallet_name": clean_wallet,
            "psbt": processed_psbt,
            "complete": self._optional_bool(result.get("complete")) is True,
            "signed": sign,
            "decoded": decoded,
            "cli_commands": [f"bitcoin-cli -rpcwallet={clean_wallet} walletprocesspsbt <psbt> {str(sign).lower()}"],
            "rpc_methods": ["walletprocesspsbt", "decodepsbt"],
            "concepts": ["PSBT", "Signing", "Wallet", "Finalization"],
            "explanation": "Wallet processing updates the PSBT with wallet metadata and, when requested, signatures for wallet-owned inputs.",
            "raw": {"walletprocesspsbt": result, "decodepsbt": decoded["raw"]["decodepsbt"]},
        }

    def finalize(self, psbt: str, extract: bool = False) -> dict[str, object]:
        clean_psbt = self._clean(psbt, "PSBT")
        result = self._as_dict(self.rpc_client.call("finalizepsbt", [clean_psbt, extract]))

        return {
            "complete": self._optional_bool(result.get("complete")) is True,
            "psbt": self._optional_str(result.get("psbt")),
            "hex": self._optional_str(result.get("hex")),
            "cli_commands": [f"bitcoin-cli finalizepsbt <psbt> {str(extract).lower()}"],
            "rpc_methods": ["finalizepsbt"],
            "concepts": ["PSBT", "Finalization", "Transaction extraction"],
            "explanation": (
                "Finalization converts a complete PSBT into final scriptSigs and witnesses. If extraction is enabled, "
                "Bitcoin Core returns raw transaction hex, but BitScope still does not broadcast it."
            ),
            "raw": {"finalizepsbt": result},
        }

    @staticmethod
    def _clean(value: str, label: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise BitScopeError(
                code="INVALID_PSBT_REQUEST",
                message=f"Provide a {label}.",
                status_code=400,
            )
        return cleaned

    @staticmethod
    def _amount(value: float) -> float:
        if value <= 0:
            raise BitScopeError(
                code="INVALID_PSBT_REQUEST",
                message="Amount must be greater than zero.",
                status_code=400,
            )
        return round(float(value), 8)

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        return value if isinstance(value, bool) else None

    @staticmethod
    def _optional_float(value: object) -> float | None:
        return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_str(value: object) -> str | None:
        return value if isinstance(value, str) and value else None
