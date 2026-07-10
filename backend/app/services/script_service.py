from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.types import JsonValue
from app.services.spend_preflight import SpendPreflight


OPCODE_NAMES = {
    0x00: "OP_0",
    0x63: "OP_IF",
    0x67: "OP_ELSE",
    0x68: "OP_ENDIF",
    0x51: "OP_1",
    0x52: "OP_2",
    0x53: "OP_3",
    0x54: "OP_4",
    0x55: "OP_5",
    0x56: "OP_6",
    0x57: "OP_7",
    0x58: "OP_8",
    0x59: "OP_9",
    0x5A: "OP_10",
    0x5B: "OP_11",
    0x5C: "OP_12",
    0x5D: "OP_13",
    0x5E: "OP_14",
    0x5F: "OP_15",
    0x60: "OP_16",
    0x6A: "OP_RETURN",
    0x75: "OP_DROP",
    0x76: "OP_DUP",
    0x87: "OP_EQUAL",
    0x88: "OP_EQUALVERIFY",
    0xA9: "OP_HASH160",
    0xA8: "OP_SHA256",
    0xAC: "OP_CHECKSIG",
    0xAD: "OP_CHECKSIGVERIFY",
    0xAE: "OP_CHECKMULTISIG",
    0xB1: "OP_CHECKLOCKTIMEVERIFY",
    0xB2: "OP_CHECKSEQUENCEVERIFY",
}

OPCODE_DESCRIPTIONS = {
    "OP_0": "Pushes an empty vector onto the stack.",
    "OP_IF": "Runs the following branch if the top stack item is true.",
    "OP_ELSE": "Switches to the alternate branch of a conditional.",
    "OP_ENDIF": "Ends a conditional script branch.",
    "OP_DROP": "Removes the top stack item.",
    "OP_DUP": "Duplicates the top stack item.",
    "OP_HASH160": "Hashes the top stack item with HASH160.",
    "OP_SHA256": "Hashes the top stack item with SHA256.",
    "OP_EQUAL": "Checks whether two stack items are equal.",
    "OP_EQUALVERIFY": "Checks equality and fails the script if it is false.",
    "OP_CHECKSIG": "Checks a signature against a public key.",
    "OP_CHECKMULTISIG": "Checks multiple signatures against multiple public keys.",
    "OP_RETURN": "Marks the output as provably unspendable and carries optional data.",
    "OP_CHECKLOCKTIMEVERIFY": "Enforces an absolute locktime rule.",
    "OP_CHECKSEQUENCEVERIFY": "Enforces a relative locktime rule.",
}


class ScriptService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def decode(self, script_hex: str) -> dict[str, object]:
        clean_hex = script_hex.strip().lower()
        self._validate_hex(clean_hex)
        decoded = self._as_dict(self.rpc_client.call("decodescript", [clean_hex]))

        return {
            "script_hex": clean_hex,
            "asm": self._optional_str(decoded.get("asm")),
            "script_type": self._optional_str(decoded.get("type")),
            "req_sigs": self._optional_int(decoded.get("reqSigs")),
            "addresses": [address for address in decoded.get("addresses", []) if isinstance(address, str)]
            if isinstance(decoded.get("addresses"), list)
            else [],
            "p2sh": self._optional_str(decoded.get("p2sh")),
            "segwit": decoded.get("segwit") if isinstance(decoded.get("segwit"), dict) else None,
            "opcodes": self._parse_opcodes(clean_hex),
            "cli_commands": [f"bitcoin-cli decodescript {clean_hex}"],
            "rpc_methods": ["decodescript"],
            "concepts": ["Script", "Opcode", "scriptPubKey", "P2SH", "SegWit"],
            "explanation": (
                "Bitcoin Core decodes raw script bytes into asm, standard script type, addresses when possible, "
                "and nested P2SH or SegWit forms. BitScope also splits the bytecode into opcode/data pushes for learning."
            ),
            "raw": {"decodescript": decoded},
        }

    def template(
        self,
        template_name: str,
        pubkey_hex: str | None = None,
        fallback_pubkey_hex: str | None = None,
        pubkey_hash_hex: str | None = None,
        hash_hex: str | None = None,
    ) -> dict[str, object]:
        clean_template = template_name.strip().lower()
        script_hex = self._build_template(clean_template, pubkey_hex, fallback_pubkey_hex, pubkey_hash_hex, hash_hex)
        decoded = self.decode(script_hex)

        return {
            "template": clean_template,
            "script_hex": script_hex,
            "asm": decoded["asm"],
            "script_type": decoded["script_type"],
            "p2sh": decoded["p2sh"],
            "segwit": decoded["segwit"],
            "opcodes": decoded["opcodes"],
            "cli_commands": decoded["cli_commands"],
            "rpc_methods": decoded["rpc_methods"],
            "concepts": ["Script", "P2SH", "P2WSH", "Conditionals", "Hashlock", "Redeem script"],
            "explanation": self._template_explanation(clean_template),
            "raw": decoded["raw"],
        }

    def test_spend(self, transaction_hex: str) -> dict[str, object]:
        clean_hex = transaction_hex.strip().lower()
        self._validate_hex(clean_hex)
        result = self.rpc_client.call("testmempoolaccept", [[clean_hex]])

        return {
            "transaction_hex": clean_hex,
            "accepted": self._extract_acceptance(result),
            "cli_commands": [f"bitcoin-cli testmempoolaccept '[\"{clean_hex}\"]'"],
            "rpc_methods": ["testmempoolaccept"],
            "concepts": ["Script validation", "Mempool policy", "Consensus", "Standardness"],
            "explanation": (
                "Bitcoin Core does not expose a generic isolated script interpreter over RPC. `testmempoolaccept` checks "
                "a fully formed transaction against consensus and mempool policy, including script validation."
            ),
            "raw": {"testmempoolaccept": result},
        }

    def create_op_return(
        self,
        wallet_name: str,
        data: str,
        data_format: str = "text",
        destination_address: str | None = None,
        amount_btc: float | None = None,
        broadcast: bool = False,
        mine_confirmation: bool = False,
    ) -> dict[str, object]:
        self._require_regtest()
        clean_wallet = self._clean_text(wallet_name, "wallet name")
        clean_format = data_format.strip().lower()
        data_hex = self._encode_op_return_data(data, clean_format)
        data_bytes = len(bytes.fromhex(data_hex))
        output_script_hex = self._op_return_script_hex(data_hex)
        preflight = SpendPreflight(self.rpc_client)

        outputs: list[dict[str, object]] = [{"data": data_hex}]
        clean_address = self._clean_optional_text(destination_address)
        clean_amount = None
        validation: dict[str, object] | None = None
        if clean_address or amount_btc is not None:
            if not clean_address:
                raise BitScopeError(
                    code="INVALID_OP_RETURN_TRANSACTION",
                    message="Provide a destination address when adding a spend output.",
                    status_code=400,
                )
            clean_amount = self._clean_amount(amount_btc)
            validation = preflight.validate_address(
                clean_address,
                "INVALID_OP_RETURN_DESTINATION_ADDRESS",
                "Provide a valid destination address from the current regtest node before adding a spend output.",
            )
            outputs.insert(0, {clean_address: clean_amount})
        balance = preflight.require_mature_balance(
            clean_wallet,
            clean_amount or 0.0,
            "OP_RETURN_INSUFFICIENT_MATURE_FUNDS",
            (
                "The wallet does not have enough mature spendable balance to fund this OP_RETURN transaction and its fee. "
                "Mine enough regtest blocks to this wallet so coinbase rewards reach 101 confirmations, then retry."
            ),
        )

        unsigned_hex = self._require_str(
            self.rpc_client.call("createrawtransaction", [[], outputs]),
            "createrawtransaction",
            "Bitcoin Core did not return an unsigned OP_RETURN transaction.",
        )
        funded = self._as_dict(self.rpc_client.call("fundrawtransaction", [unsigned_hex], wallet_name=clean_wallet))
        funded_hex = self._require_str(
            funded.get("hex"),
            "fundrawtransaction",
            "Bitcoin Core did not return a funded OP_RETURN transaction.",
        )
        signed = self._as_dict(self.rpc_client.call("signrawtransactionwithwallet", [funded_hex], wallet_name=clean_wallet))
        signed_hex = self._optional_str(signed.get("hex"))
        complete = self._optional_bool(signed.get("complete")) or False
        decoded = self._as_dict(self.rpc_client.call("decoderawtransaction", [signed_hex or funded_hex]))
        mempool_accept = self.rpc_client.call("testmempoolaccept", [[signed_hex or funded_hex]]) if signed_hex else []
        txid = self._optional_str(decoded.get("txid"))

        raw: dict[str, object] = {
            "getbalances": balance["getbalances"],
            "createrawtransaction": unsigned_hex,
            "fundrawtransaction": funded,
            "signrawtransactionwithwallet": signed,
            "decoderawtransaction": decoded,
            "testmempoolaccept": mempool_accept,
        }
        if validation is not None:
            raw["validateaddress"] = validation
        cli_outputs = self._cli_json(outputs)
        cli_commands = [
            f"bitcoin-cli -rpcwallet={clean_wallet} getbalances",
            f"bitcoin-cli createrawtransaction [] '{cli_outputs}'",
            f"bitcoin-cli -rpcwallet={clean_wallet} fundrawtransaction {unsigned_hex}",
            f"bitcoin-cli -rpcwallet={clean_wallet} signrawtransactionwithwallet {funded_hex}",
            f"bitcoin-cli decoderawtransaction {signed_hex or funded_hex}",
            f"bitcoin-cli testmempoolaccept '[\"{signed_hex or funded_hex}\"]'",
        ]
        rpc_methods = ["getbalances", "createrawtransaction", "fundrawtransaction", "signrawtransactionwithwallet", "decoderawtransaction", "testmempoolaccept"]
        if validation is not None:
            cli_commands.insert(0, f"bitcoin-cli validateaddress {clean_address}")
            rpc_methods.insert(0, "validateaddress")
        confirmation_hashes: list[str] = []

        if broadcast:
            if not signed_hex or not complete:
                raise BitScopeError(
                    code="OP_RETURN_TRANSACTION_INCOMPLETE",
                    message="Bitcoin Core could not fully sign the OP_RETURN transaction.",
                    status_code=400,
                    details={"wallet_name": clean_wallet},
                )
            txid = self._require_str(
                self.rpc_client.call("sendrawtransaction", [signed_hex]),
                "sendrawtransaction",
                "Bitcoin Core did not return an OP_RETURN transaction id.",
            )
            raw["sendrawtransaction"] = txid
            cli_commands.append(f"bitcoin-cli sendrawtransaction {signed_hex}")
            rpc_methods.append("sendrawtransaction")

            if mine_confirmation:
                mining_address = self._require_str(
                    self.rpc_client.call("getnewaddress", ["bitscope-data-confirmation", "bech32"], wallet_name=clean_wallet),
                    "getnewaddress",
                    "Bitcoin Core did not return a confirmation mining address.",
                )
                mined = self.rpc_client.call("generatetoaddress", [1, mining_address])
                confirmation_hashes = [item for item in mined if isinstance(item, str)] if isinstance(mined, list) else []
                raw["confirmation_address"] = mining_address
                raw["generatetoaddress"] = mined
                cli_commands.append(f"bitcoin-cli -rpcwallet={clean_wallet} getnewaddress bitscope-data-confirmation bech32")
                cli_commands.append(f"bitcoin-cli generatetoaddress 1 {mining_address}")
                rpc_methods.extend(["getnewaddress", "generatetoaddress"])

        return {
            "wallet_name": clean_wallet,
            "data_format": clean_format,
            "data_hex": data_hex,
            "data_utf8": data if clean_format == "text" else None,
            "data_bytes": data_bytes,
            "op_return_script_hex": output_script_hex,
            "destination_address": clean_address,
            "amount_btc": clean_amount,
            "unsigned_hex": unsigned_hex,
            "funded_hex": funded_hex,
            "signed_hex": signed_hex,
            "complete": complete,
            "txid": txid,
            "fee_btc": self._optional_float(funded.get("fee")),
            "change_position": self._optional_int(funded.get("changepos")),
            "mempool_accept": mempool_accept,
            "broadcast": broadcast,
            "confirmation_block_hashes": confirmation_hashes,
            "cli_commands": cli_commands,
            "rpc_methods": rpc_methods,
            "concepts": ["OP_RETURN", "Nulldata", "Unspendable output", "Raw transaction", "Wallet funding", "Standardness"],
            "explanation": (
                "An OP_RETURN output stores a small data commitment in a provably unspendable output. Bitcoin Core creates "
                "the nulldata output from the `data` field, the wallet funds and signs the transaction, and "
                "`testmempoolaccept` checks node policy before optional regtest broadcast."
            ),
            "raw": raw,
        }

    def _build_template(
        self,
        template_name: str,
        pubkey_hex: str | None,
        fallback_pubkey_hex: str | None,
        pubkey_hash_hex: str | None,
        hash_hex: str | None,
    ) -> str:
        if template_name == "p2pkh":
            clean_hash = self._clean_hex_field(pubkey_hash_hex, "public key hash", 20)
            return f"76a914{clean_hash}88ac"
        if template_name == "hashlock":
            clean_hash = self._clean_hex_field(hash_hex, "SHA256 hash", 32)
            clean_pubkey = self._clean_hex_field(pubkey_hex, "public key")
            return f"a820{clean_hash}88{self._push_hex(clean_pubkey)}ac"
        if template_name == "conditional":
            primary_pubkey = self._clean_hex_field(pubkey_hex, "primary public key")
            fallback_pubkey = self._clean_hex_field(fallback_pubkey_hex, "fallback public key")
            return f"63{self._push_hex(primary_pubkey)}ac67{self._push_hex(fallback_pubkey)}ac68"

        raise BitScopeError(
            code="INVALID_SCRIPT_TEMPLATE",
            message="Template must be p2pkh, hashlock, or conditional.",
            status_code=400,
            details={"template": template_name},
        )

    @staticmethod
    def _template_explanation(template_name: str) -> str:
        if template_name == "p2pkh":
            return "P2PKH locks coins to a HASH160 public key hash and requires a matching signature and public key to spend."
        if template_name == "hashlock":
            return "A hashlock requires a preimage whose SHA256 hash matches the committed value, plus a valid signature."
        if template_name == "conditional":
            return "A conditional script chooses between two signature branches based on the witness or scriptSig stack value."
        return "Template script generated for study."

    @staticmethod
    def _encode_op_return_data(data: str, data_format: str) -> str:
        clean_data = data.strip()
        if not clean_data:
            raise BitScopeError(
                code="INVALID_OP_RETURN_DATA",
                message="Provide data for the OP_RETURN output.",
                status_code=400,
            )
        if data_format == "text":
            data_hex = clean_data.encode("utf-8").hex()
        elif data_format == "hex":
            data_hex = clean_data.lower()
            ScriptService._validate_hex(data_hex)
        else:
            raise BitScopeError(
                code="INVALID_OP_RETURN_DATA",
                message="Data format must be text or hex.",
                status_code=400,
                details={"data_format": data_format},
            )

        byte_length = len(bytes.fromhex(data_hex))
        if byte_length > 80:
            raise BitScopeError(
                code="OP_RETURN_DATA_TOO_LARGE",
                message="OP_RETURN payloads in this lab are limited to 80 bytes.",
                status_code=400,
                details={"data_bytes": byte_length, "max_bytes": 80},
            )
        return data_hex

    @staticmethod
    def _op_return_script_hex(data_hex: str) -> str:
        byte_length = len(bytes.fromhex(data_hex))
        if byte_length <= 75:
            return f"6a{byte_length:02x}{data_hex}"
        return f"6a4c{byte_length:02x}{data_hex}"

    def _parse_opcodes(self, script_hex: str) -> list[dict[str, object]]:
        script = bytes.fromhex(script_hex)
        opcodes: list[dict[str, object]] = []
        cursor = 0

        while cursor < len(script):
            offset = cursor
            opcode = script[cursor]
            cursor += 1

            if 1 <= opcode <= 75:
                data = script[cursor : cursor + opcode]
                if len(data) != opcode:
                    raise BitScopeError(
                        code="INVALID_SCRIPT",
                        message="The script ended inside a data push.",
                        status_code=400,
                        details={"offset": offset, "expected_bytes": opcode, "remaining_bytes": len(data)},
                    )
                cursor += opcode
                opcodes.append(
                    {
                        "offset": offset,
                        "opcode": f"OP_PUSHBYTES_{opcode}",
                        "data_hex": data.hex(),
                        "data_length": opcode,
                        "description": f"Pushes {opcode} byte(s) onto the stack.",
                    }
                )
                continue

            if opcode == 0x4C:
                cursor, item = self._read_pushdata(script, cursor, offset, 1, "OP_PUSHDATA1")
                opcodes.append(item)
                continue
            if opcode == 0x4D:
                cursor, item = self._read_pushdata(script, cursor, offset, 2, "OP_PUSHDATA2")
                opcodes.append(item)
                continue
            if opcode == 0x4E:
                cursor, item = self._read_pushdata(script, cursor, offset, 4, "OP_PUSHDATA4")
                opcodes.append(item)
                continue

            name = OPCODE_NAMES.get(opcode, f"OP_UNKNOWN_{opcode:02x}")
            opcodes.append(
                {
                    "offset": offset,
                    "opcode": name,
                    "data_hex": None,
                    "data_length": None,
                    "description": OPCODE_DESCRIPTIONS.get(name, "Opcode recognized by byte value; see Bitcoin Script references for full semantics."),
                }
            )

        return opcodes

    def _read_pushdata(
        self,
        script: bytes,
        cursor: int,
        offset: int,
        length_size: int,
        opcode_name: str,
    ) -> tuple[int, dict[str, object]]:
        if cursor + length_size > len(script):
            raise BitScopeError(
                code="INVALID_SCRIPT",
                message="The script ended before a pushdata length could be read.",
                status_code=400,
                details={"offset": offset, "length_size": length_size},
            )
        data_length = int.from_bytes(script[cursor : cursor + length_size], "little")
        cursor += length_size
        data = script[cursor : cursor + data_length]
        if len(data) != data_length:
            raise BitScopeError(
                code="INVALID_SCRIPT",
                message="The script ended inside a pushdata payload.",
                status_code=400,
                details={"offset": offset, "expected_bytes": data_length, "remaining_bytes": len(data)},
            )

        return (
            cursor + data_length,
            {
                "offset": offset,
                "opcode": opcode_name,
                "data_hex": data.hex(),
                "data_length": data_length,
                "description": f"Reads a length prefix and pushes {data_length} byte(s) onto the stack.",
            },
        )

    @classmethod
    def _clean_hex_field(cls, value: str | None, label: str, byte_length: int | None = None) -> str:
        clean_value = (value or "").strip().lower()
        if not clean_value:
            raise BitScopeError(
                code="INVALID_SCRIPT_TEMPLATE",
                message=f"Provide {label} hex.",
                status_code=400,
            )
        cls._validate_hex(clean_value)
        if byte_length is not None and len(bytes.fromhex(clean_value)) != byte_length:
            raise BitScopeError(
                code="INVALID_SCRIPT_TEMPLATE",
                message=f"{label.title()} must be {byte_length} byte(s).",
                status_code=400,
            )
        return clean_value

    @staticmethod
    def _push_hex(value: str) -> str:
        byte_length = len(bytes.fromhex(value))
        if byte_length > 75:
            raise BitScopeError(
                code="INVALID_SCRIPT_TEMPLATE",
                message="This learning template only supports direct pushes up to 75 bytes.",
                status_code=400,
            )
        return f"{byte_length:02x}{value}"

    def _require_regtest(self) -> None:
        if self.rpc_client.settings.bitcoin_network != "regtest":
            raise BitScopeError(
                code="REGTEST_ONLY",
                message="This action is only available when BITCOIN_NETWORK is set to regtest.",
                status_code=400,
                details={"network": self.rpc_client.settings.bitcoin_network},
            )

    @staticmethod
    def _clean_text(value: str, label: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise BitScopeError(
                code="INVALID_OP_RETURN_TRANSACTION",
                message=f"Provide a {label}.",
                status_code=400,
            )
        return cleaned

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        cleaned = (value or "").strip()
        return cleaned or None

    @staticmethod
    def _clean_amount(amount_btc: float | None) -> float:
        if amount_btc is None or amount_btc <= 0:
            raise BitScopeError(
                code="INVALID_OP_RETURN_TRANSACTION",
                message="Amount must be greater than zero when adding a spend output.",
                status_code=400,
            )
        return round(float(amount_btc), 8)

    @staticmethod
    def _cli_json(value: object) -> str:
        import json

        return json.dumps(value, separators=(",", ":"))

    @staticmethod
    def _require_str(value: object, rpc_method: str, message: str) -> str:
        if isinstance(value, str) and value:
            return value
        raise BitScopeError(
            code="BITCOIN_CORE_INVALID_RESPONSE",
            message=message,
            status_code=502,
            details={"rpc_method": rpc_method},
        )

    @staticmethod
    def _extract_acceptance(value: JsonValue) -> bool | None:
        if not isinstance(value, list) or not value or not isinstance(value[0], dict):
            return None
        accepted = value[0].get("allowed")
        return accepted if isinstance(accepted, bool) else None

    @staticmethod
    def _validate_hex(script_hex: str) -> None:
        if not script_hex:
            raise BitScopeError(
                code="INVALID_SCRIPT",
                message="Provide script hex to decode.",
                status_code=400,
            )
        if len(script_hex) % 2 != 0:
            raise BitScopeError(
                code="INVALID_SCRIPT",
                message="Script hex must have an even number of characters.",
                status_code=400,
            )
        try:
            bytes.fromhex(script_hex)
        except ValueError as exc:
            raise BitScopeError(
                code="INVALID_SCRIPT",
                message="Script hex contains non-hexadecimal characters.",
                status_code=400,
            ) from exc

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        return value if isinstance(value, bool) else None

    @staticmethod
    def _optional_float(value: object) -> float | None:
        return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_str(value: object) -> str | None:
        return value if isinstance(value, str) and value else None
