from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.types import JsonValue


class TimelockService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def create_locktime_transaction(
        self,
        wallet_name: str,
        destination_address: str,
        amount_btc: float,
        locktime: int,
        sequence: int,
    ) -> dict[str, object]:
        self._require_regtest()
        clean_wallet = self._clean(wallet_name, "wallet name")
        clean_address = self._clean(destination_address, "destination address")
        amount = self._amount(amount_btc)
        if locktime < 0:
            raise BitScopeError(code="INVALID_TIMELOCK_REQUEST", message="Locktime must be zero or greater.", status_code=400)
        if sequence < 0 or sequence > 4_294_967_295:
            raise BitScopeError(code="INVALID_TIMELOCK_REQUEST", message="Sequence must fit in uint32.", status_code=400)

        validation = self._as_dict(self.rpc_client.call("validateaddress", [clean_address]))
        if validation.get("isvalid") is not True:
            raise BitScopeError(
                code="INVALID_TIMELOCK_ADDRESS",
                message=(
                    "Provide a valid destination address from the current regtest node. Regtest addresses from a previous reset "
                    "or deleted wallet are stale."
                ),
                status_code=400,
                details={"address": clean_address, "rpc_method": "validateaddress"},
            )

        utxos_value = self.rpc_client.call("listunspent", [1, 9999999], wallet_name=clean_wallet)
        utxos = [utxo for utxo in utxos_value if isinstance(utxo, dict)] if isinstance(utxos_value, list) else []
        selected = next((utxo for utxo in utxos if self._is_spendable_utxo(utxo, amount)), None)
        if selected is None:
            raise BitScopeError(
                code="TIMELOCK_UTXO_NOT_FOUND",
                message=(
                    "Bitcoin Core did not find a mature, spendable wallet UTXO large enough for this timelock transaction. "
                    "If this wallet was just mined on regtest, mine enough blocks for coinbase rewards to reach 101 confirmations."
                ),
                status_code=404,
                details={"wallet_name": clean_wallet, "amount_btc": amount, "minimum_coinbase_confirmations": 101},
            )
        selected_txid = self._require_str(selected.get("txid"), "listunspent", "Bitcoin Core returned a UTXO without a txid.")
        selected_vout = self._optional_int(selected.get("vout"))
        if selected_vout is None:
            raise BitScopeError(code="BITCOIN_CORE_INVALID_RESPONSE", message="Bitcoin Core returned a UTXO without a vout.", status_code=502)

        input_ref = {"txid": selected_txid, "vout": selected_vout, "sequence": int(sequence)}
        unsigned_hex = self._require_str(
            self.rpc_client.call("createrawtransaction", [[input_ref], {clean_address: amount}, int(locktime)]),
            "createrawtransaction",
            "Bitcoin Core did not return a locktime transaction skeleton.",
        )
        funded = self._as_dict(
            self.rpc_client.call(
                "fundrawtransaction",
                [unsigned_hex, {"add_inputs": False, "lockUnspents": True}],
                wallet_name=clean_wallet,
            )
        )
        funded_hex = self._require_str(funded.get("hex"), "fundrawtransaction", "Bitcoin Core did not return a funded locktime transaction.")
        signed = self._as_dict(self.rpc_client.call("signrawtransactionwithwallet", [funded_hex], wallet_name=clean_wallet))
        signed_hex = self._optional_str(signed.get("hex"))
        complete = self._optional_bool(signed.get("complete")) or False
        decoded = self._as_dict(self.rpc_client.call("decoderawtransaction", [signed_hex or funded_hex]))
        accept = self.rpc_client.call("testmempoolaccept", [[signed_hex or funded_hex]]) if signed_hex else []

        return {
            "wallet_name": clean_wallet,
            "destination_address": clean_address,
            "amount_btc": amount,
            "locktime": int(locktime),
            "sequence": int(sequence),
            "unsigned_hex": unsigned_hex,
            "funded_hex": funded_hex,
            "sequence_hex": funded_hex,
            "signed_hex": signed_hex,
            "complete": complete,
            "txid": self._optional_str(decoded.get("txid")),
            "fee_btc": self._optional_float(funded.get("fee")),
            "change_position": self._optional_int(funded.get("changepos")),
            "mempool_accept": accept,
            "cli_commands": [
                f"bitcoin-cli validateaddress {clean_address}",
                f"bitcoin-cli -rpcwallet={clean_wallet} listunspent 1 9999999",
                f"bitcoin-cli createrawtransaction '[{{\"txid\":\"{selected_txid}\",\"vout\":{selected_vout},\"sequence\":{int(sequence)}}}]' '{{\"{clean_address}\":{amount:.8f}}}' {int(locktime)}",
                f"bitcoin-cli -rpcwallet={clean_wallet} fundrawtransaction {unsigned_hex} '{{\"add_inputs\":false,\"lockUnspents\":true}}'",
                f"bitcoin-cli -rpcwallet={clean_wallet} signrawtransactionwithwallet {funded_hex}",
                f"bitcoin-cli testmempoolaccept '[\"{signed_hex or funded_hex}\"]'",
            ],
            "rpc_methods": ["validateaddress", "listunspent", "createrawtransaction", "fundrawtransaction", "signrawtransactionwithwallet", "decoderawtransaction", "testmempoolaccept"],
            "concepts": ["nLockTime", "Sequence", "Mempool policy", "Regtest", "Finality"],
            "explanation": (
                "A transaction-level locktime is only enforced when at least one input sequence is below final. "
                "BitScope builds a funded transaction, adjusts input sequences, signs it, and asks Bitcoin Core whether mempool policy accepts it."
            ),
            "raw": {
                "validateaddress": validation,
                "listunspent": utxos,
                "createrawtransaction": unsigned_hex,
                "fundrawtransaction": funded,
                "signrawtransactionwithwallet": signed,
                "decoderawtransaction": decoded,
                "testmempoolaccept": accept,
            },
        }

    def script_template(self, mode: str, value: int, pubkey_hex: str) -> dict[str, object]:
        clean_mode = mode.strip().lower()
        if clean_mode not in {"cltv", "csv"}:
            raise BitScopeError(code="INVALID_TIMELOCK_REQUEST", message="Mode must be cltv or csv.", status_code=400)
        if value < 0:
            raise BitScopeError(code="INVALID_TIMELOCK_REQUEST", message="Timelock value must be zero or greater.", status_code=400)
        clean_pubkey = pubkey_hex.strip().lower()
        self._validate_hex(clean_pubkey, "public key")

        encoded_value = self._script_number(value)
        opcode = "b1" if clean_mode == "cltv" else "b2"
        script_hex = f"{len(encoded_value) // 2:02x}{encoded_value}{opcode}75{len(bytes.fromhex(clean_pubkey)):02x}{clean_pubkey}ac"
        decoded = self._as_dict(self.rpc_client.call("decodescript", [script_hex]))
        return {
            "mode": clean_mode,
            "value": value,
            "pubkey_hex": clean_pubkey,
            "script_hex": script_hex,
            "asm": self._optional_str(decoded.get("asm")),
            "p2sh": self._optional_str(decoded.get("p2sh")),
            "segwit": decoded.get("segwit") if isinstance(decoded.get("segwit"), dict) else None,
            "cli_commands": [f"bitcoin-cli decodescript {script_hex}"],
            "rpc_methods": ["decodescript"],
            "concepts": ["CLTV" if clean_mode == "cltv" else "CSV", "Script", "Timelock", "Tapscript caveat"],
            "explanation": (
                "CLTV checks an absolute block height or median-time-past lock. CSV checks relative age through the input sequence. "
                "This template is a learning script; production scripts should be reviewed carefully."
            ),
            "raw": {"decodescript": decoded},
        }

    def _require_regtest(self) -> None:
        if self.rpc_client.settings.bitcoin_network != "regtest":
            raise BitScopeError(
                code="REGTEST_ONLY",
                message="This timelock lab is only available when BITCOIN_NETWORK is set to regtest.",
                status_code=400,
                details={"network": self.rpc_client.settings.bitcoin_network},
            )

    @staticmethod
    def _script_number(value: int) -> str:
        if value == 0:
            return ""
        result = bytearray()
        remaining = value
        while remaining:
            result.append(remaining & 0xFF)
            remaining >>= 8
        if result[-1] & 0x80:
            result.append(0)
        return bytes(result).hex()

    @staticmethod
    def _validate_hex(value: str, label: str) -> None:
        if not value or len(value) % 2 != 0:
            raise BitScopeError(code="INVALID_TIMELOCK_REQUEST", message=f"Provide an even-length hex {label}.", status_code=400)
        try:
            bytes.fromhex(value)
        except ValueError as exc:
            raise BitScopeError(code="INVALID_TIMELOCK_REQUEST", message=f"{label.title()} must be hexadecimal.", status_code=400) from exc

    @staticmethod
    def _clean(value: str, label: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise BitScopeError(code="INVALID_TIMELOCK_REQUEST", message=f"Provide a {label}.", status_code=400)
        return cleaned

    @staticmethod
    def _amount(value: float) -> float:
        if value <= 0:
            raise BitScopeError(code="INVALID_TIMELOCK_REQUEST", message="Amount must be greater than zero.", status_code=400)
        return round(float(value), 8)

    @classmethod
    def _is_spendable_utxo(cls, utxo: dict[str, object], amount: float) -> bool:
        utxo_amount = cls._optional_float(utxo.get("amount"))
        if utxo_amount is None or utxo_amount <= amount:
            return False
        if utxo.get("spendable") is False or utxo.get("safe") is False:
            return False
        confirmations = cls._optional_int(utxo.get("confirmations"))
        generated = utxo.get("generated") is True
        if generated and (confirmations is None or confirmations < 101):
            return False
        if confirmations is not None and confirmations < 1:
            return False
        return True

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _require_str(value: object, rpc_method: str, message: str) -> str:
        if isinstance(value, str) and value:
            return value
        raise BitScopeError(code="BITCOIN_CORE_INVALID_RESPONSE", message=message, status_code=502, details={"rpc_method": rpc_method})

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
