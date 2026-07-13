from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.capabilities import WalletReadRpcClient
from app.rpc.errors import RpcError
from app.rpc.types import JsonValue


ADDRESS_LIMITATION = (
    "Bitcoin Core does not track full address history by default. BitScope can validate this address, "
    "but cannot show full transaction history unless the address belongs to your wallet or a local indexer is implemented."
)

WALLET_OPTIONAL_ERRORS = {
    "WALLET_NOT_LOADED",
    "BITCOIN_CORE_NOT_FOUND",
    "INVALID_RPC_PARAMETER",
    "BITCOIN_CORE_RPC_ERROR",
}


class AddressService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = WalletReadRpcClient(rpc_client)

    def get_address(self, address: str) -> dict[str, object]:
        normalized_address = address.strip()
        if not normalized_address:
            raise BitScopeError(
                code="INVALID_ADDRESS",
                message="Provide a Bitcoin address to inspect.",
                status_code=400,
            )

        validation = self._as_dict(self.rpc_client.call("validateaddress", [normalized_address]))
        if validation.get("isvalid") is not True:
            raise BitScopeError(
                code="INVALID_ADDRESS",
                message="Bitcoin Core says this address is invalid for the current network.",
                status_code=400,
                details={"address": normalized_address, "validation": validation},
            )

        address_info = self._wallet_dict_call("getaddressinfo", [normalized_address])
        utxo_values = self._wallet_list_call("listunspent", [0, 9999999, [normalized_address]])
        received = self._wallet_number_call("getreceivedbyaddress", [normalized_address, 0])
        utxos = [self._normalize_utxo(utxo) for utxo in utxo_values if isinstance(utxo, dict)]
        wallet_name = self.rpc_client.settings.bitcoin_rpc_wallet or None
        is_mine = self._optional_bool(address_info.get("ismine"))
        is_watch_only = self._optional_bool(address_info.get("iswatchonly"))
        has_wallet_context = bool(is_mine or is_watch_only or received is not None or utxos)

        return {
            "address": normalized_address,
            "is_valid": True,
            "network": self.rpc_client.settings.bitcoin_network,
            "address_type": self._address_type(validation, address_info),
            "script_pub_key": self._optional_str(address_info.get("scriptPubKey") or validation.get("scriptPubKey")),
            "witness_version": self._optional_int(validation.get("witness_version") or address_info.get("witness_version")),
            "witness_program": self._optional_str(validation.get("witness_program") or address_info.get("witness_program")),
            "is_mine": is_mine,
            "is_watch_only": is_watch_only,
            "solvable": self._optional_bool(address_info.get("solvable")),
            "wallet_name": wallet_name if has_wallet_context else None,
            "received_btc": received,
            "utxos": utxos,
            "limitation": None if has_wallet_context else ADDRESS_LIMITATION,
            "cli_commands": [
                f"bitcoin-cli validateaddress {normalized_address}",
                f"bitcoin-cli getaddressinfo {normalized_address}",
                f"bitcoin-cli listunspent 0 9999999 '[\"{normalized_address}\"]'",
                f"bitcoin-cli getreceivedbyaddress {normalized_address} 0",
            ],
            "rpc_methods": ["validateaddress", "getaddressinfo", "listunspent", "getreceivedbyaddress"],
            "concepts": ["Address", "ScriptPubKey", "Wallet", "Watch-only", "UTXO"],
            "explanation": (
                "Bitcoin Core can validate an address for the active network. Wallet-specific RPCs add received "
                "amounts and UTXOs when the address belongs to the configured wallet or watch-only set."
            ),
            "raw": {
                "validateaddress": validation,
                "getaddressinfo": address_info,
                "listunspent": utxo_values,
                "getreceivedbyaddress": received,
            },
        }

    def _wallet_dict_call(self, method: str, params: list[object]) -> dict[str, object]:
        try:
            return self._as_dict(self.rpc_client.call(method, params))
        except RpcError as exc:
            if exc.code in WALLET_OPTIONAL_ERRORS:
                return {}
            raise

    def _wallet_list_call(self, method: str, params: list[object]) -> list[object]:
        try:
            result = self.rpc_client.call(method, params)
        except RpcError as exc:
            if exc.code in WALLET_OPTIONAL_ERRORS:
                return []
            raise

        return result if isinstance(result, list) else []

    def _wallet_number_call(self, method: str, params: list[object]) -> float | None:
        try:
            result = self.rpc_client.call(method, params)
        except RpcError as exc:
            if exc.code in WALLET_OPTIONAL_ERRORS:
                return None
            raise

        return float(result) if isinstance(result, int | float) else None

    def _normalize_utxo(self, utxo: dict[object, object]) -> dict[str, object]:
        return {
            "txid": self._optional_str(utxo.get("txid")) or "",
            "vout": self._optional_int(utxo.get("vout")) or 0,
            "amount_btc": float(utxo.get("amount")) if isinstance(utxo.get("amount"), int | float) else 0.0,
            "confirmations": self._optional_int(utxo.get("confirmations")) or 0,
            "spendable": self._optional_bool(utxo.get("spendable")),
            "solvable": self._optional_bool(utxo.get("solvable")),
            "safe": self._optional_bool(utxo.get("safe")),
            "descriptor": self._optional_str(utxo.get("desc")),
        }

    def _address_type(self, validation: dict[str, object], address_info: dict[str, object]) -> str | None:
        explicit_type = self._optional_str(address_info.get("type") or validation.get("type"))
        if explicit_type:
            return explicit_type

        descriptor = self._optional_str(address_info.get("desc") or address_info.get("parent_desc"))
        if descriptor:
            return descriptor.split("(", 1)[0]

        if validation.get("iswitness") is True:
            version = self._optional_int(validation.get("witness_version"))
            return "witness_v0" if version == 0 else f"witness_v{version}" if version is not None else "witness"

        return None

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        return value if isinstance(value, bool) else None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_str(value: object) -> str | None:
        return value if isinstance(value, str) and value else None
