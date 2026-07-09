from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.types import JsonValue


class WalletService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def summary(self) -> dict[str, object]:
        loaded_wallets = self._as_str_list(self.rpc_client.call("listwallets"))
        wallet_dir = self._as_dict(self.rpc_client.call("listwalletdir"))
        available = [
            self._wallet_info_from_dir(wallet, loaded_wallets)
            for wallet in wallet_dir.get("wallets", [])
            if isinstance(wallet, dict)
        ]

        return {
            "loaded_wallets": loaded_wallets,
            "available_wallets": available,
            "configured_wallet": self.rpc_client.settings.bitcoin_rpc_wallet or None,
            "cli_commands": ["bitcoin-cli listwallets", "bitcoin-cli listwalletdir"],
            "rpc_methods": ["listwallets", "listwalletdir"],
            "concepts": ["Wallet", "Descriptor wallet", "Loaded wallet", "Wallet directory"],
            "explanation": (
                "Bitcoin Core separates wallets that exist on disk from wallets currently loaded into the node. "
                "Loaded wallets can answer balance, address, UTXO, and transaction RPC calls."
            ),
            "raw": {"listwallets": loaded_wallets, "listwalletdir": wallet_dir},
        }

    def create_wallet(self, wallet_name: str) -> dict[str, object]:
        clean_name = self._clean_wallet_name(wallet_name)
        result = self._as_dict(self.rpc_client.call("createwallet", [clean_name]))
        created_name = self._optional_str(result.get("name")) or clean_name

        return {
            "wallet_name": created_name,
            "message": f"Wallet '{created_name}' is created and loaded.",
            "warning": self._optional_str(result.get("warning")),
            "cli_commands": [f"bitcoin-cli createwallet {created_name}"],
            "rpc_methods": ["createwallet"],
            "concepts": ["Wallet", "Descriptor wallet", "Private keys"],
            "explanation": "Bitcoin Core creates a wallet file on disk and loads it so wallet RPCs can use it immediately.",
            "raw": {"createwallet": result},
        }

    def load_wallet(self, wallet_name: str) -> dict[str, object]:
        clean_name = self._clean_wallet_name(wallet_name)
        result = self._as_dict(self.rpc_client.call("loadwallet", [clean_name]))
        loaded_name = self._optional_str(result.get("name")) or clean_name

        return {
            "wallet_name": loaded_name,
            "message": f"Wallet '{loaded_name}' is loaded.",
            "warning": self._optional_str(result.get("warning")),
            "cli_commands": [f"bitcoin-cli loadwallet {loaded_name}"],
            "rpc_methods": ["loadwallet"],
            "concepts": ["Wallet", "Loaded wallet", "Wallet RPC endpoint"],
            "explanation": "Loading a wallet makes it available at Bitcoin Core's wallet-specific RPC endpoint.",
            "raw": {"loadwallet": result},
        }

    def balance(self, wallet_name: str) -> dict[str, object]:
        clean_name = self._clean_wallet_name(wallet_name)
        balances = self._as_dict(self.rpc_client.call("getbalances", wallet_name=clean_name))
        mine = self._as_dict(balances.get("mine"))
        trusted = self._optional_float(mine.get("trusted"))
        pending = self._optional_float(mine.get("untrusted_pending"))
        immature = self._optional_float(mine.get("immature"))

        return {
            "wallet_name": clean_name,
            "trusted_btc": trusted,
            "untrusted_pending_btc": pending,
            "immature_btc": immature,
            "total_btc": sum(value for value in [trusted, pending, immature] if value is not None),
            "cli_commands": [f"bitcoin-cli -rpcwallet={clean_name} getbalances"],
            "rpc_methods": ["getbalances"],
            "concepts": ["Wallet balance", "Trusted balance", "Immature coinbase", "Unconfirmed transaction"],
            "explanation": (
                "Wallet balances are local accounting from Bitcoin Core. Coinbase outputs mined on regtest are "
                "immature until they have 100 confirmations."
            ),
            "raw": {"getbalances": balances},
        }

    def new_address(self, wallet_name: str, label: str = "", address_type: str = "bech32") -> dict[str, object]:
        clean_name = self._clean_wallet_name(wallet_name)
        clean_type = address_type.strip() or "bech32"
        if clean_type not in {"legacy", "p2sh-segwit", "bech32", "bech32m"}:
            raise BitScopeError(
                code="INVALID_ADDRESS_TYPE",
                message="Address type must be legacy, p2sh-segwit, bech32, or bech32m.",
                status_code=400,
                details={"address_type": address_type},
            )

        address = self.rpc_client.call("getnewaddress", [label, clean_type], wallet_name=clean_name)
        if not isinstance(address, str):
            raise BitScopeError(
                code="BITCOIN_CORE_INVALID_RESPONSE",
                message="Bitcoin Core did not return an address.",
                status_code=502,
                details={"rpc_method": "getnewaddress"},
            )

        return {
            "wallet_name": clean_name,
            "address": address,
            "label": label,
            "address_type": clean_type,
            "cli_commands": [f"bitcoin-cli -rpcwallet={clean_name} getnewaddress \"{label}\" {clean_type}"],
            "rpc_methods": ["getnewaddress"],
            "concepts": ["Address", "Descriptor wallet", "Receive address", "Script type"],
            "explanation": "Bitcoin Core derives a fresh receiving address from the selected wallet.",
            "raw": {"getnewaddress": address},
        }

    def utxos(self, wallet_name: str) -> dict[str, object]:
        clean_name = self._clean_wallet_name(wallet_name)
        raw_utxos = self.rpc_client.call("listunspent", [0, 9999999], wallet_name=clean_name)
        utxos = [self._normalize_utxo(utxo) for utxo in raw_utxos if isinstance(utxo, dict)] if isinstance(raw_utxos, list) else []
        total = sum(utxo["amount_btc"] for utxo in utxos if isinstance(utxo.get("amount_btc"), float))

        return {
            "wallet_name": clean_name,
            "utxos": utxos,
            "total_btc": total,
            "cli_commands": [f"bitcoin-cli -rpcwallet={clean_name} listunspent 0 9999999"],
            "rpc_methods": ["listunspent"],
            "concepts": ["UTXO", "Spendable output", "Confirmations", "Coin selection"],
            "explanation": "The wallet UTXO set is the list of unspent outputs Bitcoin Core knows this wallet can track.",
            "raw": {"listunspent": raw_utxos},
        }

    def transactions(self, wallet_name: str, count: int = 20) -> dict[str, object]:
        clean_name = self._clean_wallet_name(wallet_name)
        clean_count = max(1, min(count, 100))
        raw_transactions = self.rpc_client.call("listtransactions", ["*", clean_count, 0, True], wallet_name=clean_name)
        transactions = [
            self._normalize_transaction(transaction)
            for transaction in raw_transactions
            if isinstance(transaction, dict)
        ] if isinstance(raw_transactions, list) else []

        return {
            "wallet_name": clean_name,
            "transactions": transactions,
            "cli_commands": [f"bitcoin-cli -rpcwallet={clean_name} listtransactions \"*\" {clean_count} 0 true"],
            "rpc_methods": ["listtransactions"],
            "concepts": ["Wallet transaction", "Confirmation", "Send", "Receive"],
            "explanation": "Bitcoin Core reports wallet-relevant transaction records from the selected wallet's local history.",
            "raw": {"listtransactions": raw_transactions},
        }

    def _wallet_info_from_dir(self, wallet: dict[object, object], loaded_wallets: list[str]) -> dict[str, object]:
        name = self._optional_str(wallet.get("name")) or ""
        return {
            "wallet_name": name,
            "loaded": name in loaded_wallets,
            "scanning": self._optional_bool(wallet.get("scanning")),
            "private_keys_enabled": self._optional_bool(wallet.get("private_keys_enabled")),
            "descriptors": self._optional_bool(wallet.get("descriptors")),
            "blank": self._optional_bool(wallet.get("blank")),
            "birthtime": self._optional_int(wallet.get("birthtime")),
            "warnings": [warning for warning in wallet.get("warnings", []) if isinstance(warning, str)]
            if isinstance(wallet.get("warnings"), list)
            else [],
        }

    def _normalize_utxo(self, utxo: dict[object, object]) -> dict[str, object]:
        return {
            "txid": self._optional_str(utxo.get("txid")) or "",
            "vout": self._optional_int(utxo.get("vout")) or 0,
            "address": self._optional_str(utxo.get("address")),
            "label": self._optional_str(utxo.get("label")),
            "amount_btc": self._optional_float(utxo.get("amount")) or 0.0,
            "confirmations": self._optional_int(utxo.get("confirmations")) or 0,
            "spendable": self._optional_bool(utxo.get("spendable")),
            "solvable": self._optional_bool(utxo.get("solvable")),
            "safe": self._optional_bool(utxo.get("safe")),
        }

    def _normalize_transaction(self, transaction: dict[object, object]) -> dict[str, object]:
        return {
            "txid": self._optional_str(transaction.get("txid")) or "",
            "category": self._optional_str(transaction.get("category")),
            "address": self._optional_str(transaction.get("address")),
            "amount_btc": self._optional_float(transaction.get("amount")),
            "fee_btc": self._optional_float(transaction.get("fee")),
            "confirmations": self._optional_int(transaction.get("confirmations")),
            "time": self._optional_int(transaction.get("time")),
            "trusted": self._optional_bool(transaction.get("trusted")),
        }

    @staticmethod
    def _clean_wallet_name(wallet_name: str) -> str:
        clean_name = wallet_name.strip()
        if not clean_name:
            raise BitScopeError(
                code="INVALID_WALLET_NAME",
                message="Provide a wallet name.",
                status_code=400,
            )
        return clean_name

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _as_str_list(value: JsonValue) -> list[str]:
        return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []

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
