import hashlib
import struct
from decimal import Decimal

from ecdsa import SECP256k1, SigningKey
from ecdsa.util import sigencode_der_canonize
from app.errors import BitScopeError
from app.rpc.capabilities import RegtestMutationRpcClient, RpcTransport
from app.rpc.types import JsonValue
from app.services.network_safety import NetworkSafetyGuard
from app.services.spend_preflight import SpendPreflight


SATOSHI = Decimal("0.00000001")


class TimelockService:
    def __init__(self, rpc_client: RpcTransport) -> None:
        self.rpc_client = RegtestMutationRpcClient(rpc_client)
        self._cltv_keys: dict[str, SigningKey] = {}

    def create_locktime_transaction(
        self,
        wallet_name: str,
        destination_address: str,
        amount_btc: float,
        locktime: int,
        sequence: int,
    ) -> dict[str, object]:
        NetworkSafetyGuard(self.rpc_client).require_regtest()
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

    def create_cltv_policy(
        self,
        lock_height: int,
    ) -> dict[str, object]:
        """Create a native-SegWit CLTV policy backed by an ephemeral in-memory key."""

        NetworkSafetyGuard(self.rpc_client).require_regtest()
        if lock_height < 1 or lock_height >= 500_000_000:
            raise BitScopeError(
                code="INVALID_TIMELOCK_REQUEST",
                message="The CLTV lock must be an absolute block height below 500000000.",
                status_code=400,
            )
        signing_key = SigningKey.generate(curve=SECP256k1)
        pubkey = self._compressed_pubkey(signing_key)
        template = self.script_template("cltv", lock_height, pubkey)
        segwit = self._as_dict(template.get("segwit"))
        policy_address = self._require_str(
            segwit.get("address"),
            "decodescript",
            "Bitcoin Core did not return a native-SegWit CLTV address.",
        )
        script_pub_key = self._require_str(
            segwit.get("hex"),
            "decodescript",
            "Bitcoin Core did not return the CLTV output script.",
        )
        witness_script = self._require_str(
            template.get("script_hex"),
            "decodescript",
            "Bitcoin Core did not return the CLTV witness script.",
        )
        self._cltv_keys[policy_address] = signing_key
        return {
            "signer_kind": "ephemeral_software_key",
            "lock_height": lock_height,
            "pubkey": pubkey,
            "policy_address": policy_address,
            "script_pub_key": script_pub_key,
            "witness_script": witness_script,
            "template": template,
            "cli_commands": [
                f"bitcoin-cli decodescript {witness_script}",
            ],
            "rpc_methods": ["decodescript"],
            "concepts": ["CLTV", "P2WSH", "Absolute block height", "Ephemeral software key"],
            "explanation": (
                "The witness script requires the transaction locktime to reach the reviewed block height, "
                "drops that value, and then requires an ephemeral in-memory signer's signature."
            ),
            "raw": {
                "decodescript": template["raw"],
            },
        }

    def fund_cltv_policy(
        self,
        funding_wallet: str,
        policy_address: str,
        amount_btc: float,
        fee_rate_sat_vb: float,
    ) -> dict[str, object]:
        """Fund a fresh CLTV policy and identify its exact output before confirmation."""

        NetworkSafetyGuard(self.rpc_client).require_regtest()
        clean_wallet = self._clean(funding_wallet, "funding wallet name")
        clean_address = self._clean(policy_address, "CLTV policy address")
        amount = self._amount(amount_btc)
        fee_rate = round(float(fee_rate_sat_vb), 3)
        if fee_rate <= 0:
            raise BitScopeError(
                code="INVALID_TIMELOCK_REQUEST",
                message="The CLTV funding fee rate must be greater than zero.",
                status_code=400,
            )
        preflight = SpendPreflight(self.rpc_client)
        validation = preflight.validate_address(
            clean_address,
            "INVALID_TIMELOCK_ADDRESS",
            "Provide a valid CLTV policy address from the current regtest node.",
        )
        balance = preflight.require_mature_balance(
            clean_wallet,
            amount,
            "TIMELOCK_INSUFFICIENT_MATURE_FUNDS",
            "The funding wallet does not have enough mature balance for the CLTV policy output.",
        )
        txid = self._require_str(
            self.rpc_client.call(
                "sendtoaddress",
                [clean_address, amount, "", "", False, True, None, "unset", None, fee_rate],
                wallet_name=clean_wallet,
            ),
            "sendtoaddress",
            "Bitcoin Core did not return the CLTV funding transaction id.",
        )
        wallet_transaction = self._as_dict(
            self.rpc_client.call("gettransaction", [txid], wallet_name=clean_wallet)
        )
        raw_hex = self._require_str(
            wallet_transaction.get("hex"),
            "gettransaction",
            "Bitcoin Core did not return the CLTV funding transaction hex.",
        )
        decoded = self._as_dict(self.rpc_client.call("decoderawtransaction", [raw_hex]))
        output = self._find_output(decoded, clean_address)
        return {
            "funding_wallet": clean_wallet,
            "policy_address": clean_address,
            "amount_btc": amount,
            "txid": txid,
            "vout": output["n"],
            "output_amount_btc": output["value"],
            "script_pub_key": output["script_pub_key"],
            "fee_rate_sat_vb": fee_rate,
            "wallet_transaction": wallet_transaction,
            "decoded": decoded,
            "cli_commands": [
                f"bitcoin-cli -rpcwallet={clean_wallet} sendtoaddress {clean_address} {amount:.8f}",
                f"bitcoin-cli -rpcwallet={clean_wallet} gettransaction {txid}",
            ],
            "rpc_methods": ["validateaddress", "getbalances", "sendtoaddress", "gettransaction", "decoderawtransaction"],
            "concepts": ["CLTV", "Funding output", "P2WSH", "Outpoint"],
            "explanation": "The session funding wallet creates one policy output whose exact outpoint and amount are retained for the spend.",
            "raw": {
                "validateaddress": validation,
                "getbalances": balance["getbalances"],
                "sendtoaddress": txid,
                "gettransaction": wallet_transaction,
                "decoderawtransaction": decoded,
            },
        }

    def create_cltv_spend(
        self,
        funding: dict[str, object],
        policy_address: str,
        witness_script: str,
        destination_address: str,
        locktime: int,
        sequence: int,
        fee_sats: int,
    ) -> dict[str, object]:
        """Construct and locally sign one CLTV branch spend without persisting its key."""

        NetworkSafetyGuard(self.rpc_client).require_regtest()
        clean_policy_address = self._clean(policy_address, "CLTV policy address")
        signing_key = self._cltv_keys.get(clean_policy_address)
        if signing_key is None:
            raise BitScopeError(
                code="CLTV_SIGNER_NOT_AVAILABLE",
                message="The ephemeral CLTV signer is not available for this scenario run.",
                status_code=409,
            )
        clean_destination = self._clean(destination_address, "destination address")
        clean_witness_script = witness_script.strip().lower()
        self._validate_hex(clean_witness_script, "witness script")
        if locktime < 0 or locktime >= 500_000_000:
            raise BitScopeError(
                code="INVALID_TIMELOCK_REQUEST",
                message="The CLTV spend locktime must be an absolute block height.",
                status_code=400,
            )
        if sequence < 0 or sequence > 4_294_967_295:
            raise BitScopeError(
                code="INVALID_TIMELOCK_REQUEST",
                message="Sequence must fit in uint32.",
                status_code=400,
            )
        if fee_sats < 1:
            raise BitScopeError(
                code="INVALID_TIMELOCK_REQUEST",
                message="The CLTV spend fee must be positive.",
                status_code=400,
            )
        validation = self._as_dict(self.rpc_client.call("validateaddress", [clean_destination]))
        if validation.get("isvalid") is not True:
            raise BitScopeError(
                code="INVALID_TIMELOCK_ADDRESS",
                message="Provide a valid CLTV spend destination from the current regtest node.",
                status_code=400,
            )
        txid = self._require_str(
            funding.get("txid"),
            "gettransaction",
            "The CLTV funding record does not contain a transaction id.",
        )
        vout = self._require_int(funding.get("vout"), "gettransaction", "The CLTV funding record has no vout.")
        input_amount = self._require_decimal(
            funding.get("output_amount_btc"),
            "gettransaction",
            "The CLTV funding record has no output amount.",
        )
        script_pub_key = self._require_str(
            funding.get("script_pub_key"),
            "decoderawtransaction",
            "The CLTV funding record has no output script.",
        )
        output_amount = input_amount - (Decimal(fee_sats) * SATOSHI)
        if output_amount <= 0:
            raise BitScopeError(
                code="INVALID_TIMELOCK_REQUEST",
                message="The CLTV funding output cannot cover the configured spend fee.",
                status_code=400,
            )
        input_ref = {"txid": txid, "vout": vout, "sequence": sequence}
        unsigned_hex = self._require_str(
            self.rpc_client.call(
                "createrawtransaction",
                [[input_ref], {clean_destination: float(output_amount)}, locktime],
            ),
            "createrawtransaction",
            "Bitcoin Core did not return a CLTV spend transaction.",
        )
        decoded_unsigned = self._as_dict(
            self.rpc_client.call("decoderawtransaction", [unsigned_hex])
        )
        self._validate_unsigned_cltv(
            decoded_unsigned,
            txid,
            vout,
            clean_destination,
            float(output_amount),
            locktime,
            sequence,
        )
        destination_script = self._require_str(
            validation.get("scriptPubKey"),
            "validateaddress",
            "Bitcoin Core did not return the destination scriptPubKey.",
        )
        signed_hex = self._sign_cltv_transaction(
            signing_key,
            txid,
            vout,
            input_amount,
            clean_witness_script,
            destination_script,
            output_amount,
            locktime,
            sequence,
        )
        decoded = self._as_dict(self.rpc_client.call("decoderawtransaction", [signed_hex]))
        return {
            "signer_kind": "ephemeral_software_key",
            "destination_address": clean_destination,
            "funding_txid": txid,
            "funding_vout": vout,
            "input_amount_btc": float(input_amount),
            "output_amount_btc": float(output_amount),
            "fee_sats": fee_sats,
            "locktime": locktime,
            "sequence": sequence,
            "unsigned_hex": unsigned_hex,
            "signed_hex": signed_hex,
            "complete": True,
            "signing_errors": [],
            "decoded_unsigned": decoded_unsigned,
            "decoded": decoded,
            "cli_commands": [
                (
                    "bitcoin-cli createrawtransaction '[<cltv-outpoint>]' "
                    f"'{{\"{clean_destination}\":{float(output_amount):.8f}}}' {locktime}"
                ),
                "# BitScope signs the BIP143 digest with an ephemeral in-memory key; private material is never exported.",
            ],
            "rpc_methods": ["validateaddress", "createrawtransaction", "decoderawtransaction"],
            "concepts": ["CLTV", "nLockTime", "Sequence", "P2WSH witness", "Wallet signature"],
            "explanation": (
                "The transaction commits to an absolute locktime and sequence. BitScope signs its BIP143 digest with "
                "an ephemeral key that is never serialized into evidence, settings, SQLite, or an RPC request."
            ),
            "raw": {
                "validateaddress": validation,
                "createrawtransaction": unsigned_hex,
                "decoderawtransaction_unsigned": decoded_unsigned,
                "decoderawtransaction": decoded,
            },
        }

    def clear_ephemeral_cltv_keys(self) -> None:
        self._cltv_keys.clear()

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
    def _compressed_pubkey(signing_key: SigningKey) -> str:
        point = signing_key.verifying_key.pubkey.point
        prefix = b"\x02" if point.y() % 2 == 0 else b"\x03"
        return (prefix + int(point.x()).to_bytes(32, "big")).hex()

    @classmethod
    def _sign_cltv_transaction(
        cls,
        signing_key: SigningKey,
        txid: str,
        vout: int,
        input_amount: Decimal,
        witness_script_hex: str,
        destination_script_hex: str,
        output_amount: Decimal,
        locktime: int,
        sequence: int,
    ) -> str:
        version = struct.pack("<I", 2)
        outpoint = bytes.fromhex(txid)[::-1] + struct.pack("<I", vout)
        sequence_bytes = struct.pack("<I", sequence)
        witness_script = bytes.fromhex(witness_script_hex)
        destination_script = bytes.fromhex(destination_script_hex)
        input_sats = cls._satoshis(input_amount)
        output_sats = cls._satoshis(output_amount)
        serialized_output = (
            struct.pack("<Q", output_sats)
            + cls._compact_size(len(destination_script))
            + destination_script
        )
        sighash_preimage = b"".join(
            [
                version,
                cls._double_sha256(outpoint),
                cls._double_sha256(sequence_bytes),
                outpoint,
                cls._compact_size(len(witness_script)),
                witness_script,
                struct.pack("<Q", input_sats),
                sequence_bytes,
                cls._double_sha256(serialized_output),
                struct.pack("<I", locktime),
                struct.pack("<I", 1),
            ]
        )
        digest = cls._double_sha256(sighash_preimage)
        signature = signing_key.sign_digest_deterministic(
            digest,
            hashfunc=hashlib.sha256,
            sigencode=sigencode_der_canonize,
        ) + b"\x01"
        unsigned_input = outpoint + b"\x00" + sequence_bytes
        witness = (
            b"\x02"
            + cls._compact_size(len(signature))
            + signature
            + cls._compact_size(len(witness_script))
            + witness_script
        )
        transaction = b"".join(
            [
                version,
                b"\x00\x01",
                b"\x01",
                unsigned_input,
                b"\x01",
                serialized_output,
                witness,
                struct.pack("<I", locktime),
            ]
        )
        return transaction.hex()

    @classmethod
    def _validate_unsigned_cltv(
        cls,
        transaction: dict[str, object],
        funding_txid: str,
        funding_vout: int,
        destination_address: str,
        output_amount: float,
        locktime: int,
        sequence: int,
    ) -> None:
        if transaction.get("version") != 2 or transaction.get("locktime") != locktime:
            raise cls._invalid_response(
                "decoderawtransaction",
                "Bitcoin Core returned unexpected CLTV transaction version or locktime metadata.",
            )
        inputs = transaction.get("vin")
        if (
            not isinstance(inputs, list)
            or len(inputs) != 1
            or not isinstance(inputs[0], dict)
            or inputs[0].get("txid") != funding_txid
            or inputs[0].get("vout") != funding_vout
            or inputs[0].get("sequence") != sequence
        ):
            raise cls._invalid_response(
                "decoderawtransaction",
                "Bitcoin Core returned unexpected CLTV input metadata.",
            )
        outputs = transaction.get("vout")
        if not isinstance(outputs, list) or len(outputs) != 1 or not isinstance(outputs[0], dict):
            raise cls._invalid_response(
                "decoderawtransaction",
                "Bitcoin Core returned unexpected CLTV output metadata.",
            )
        script = outputs[0].get("scriptPubKey")
        value = outputs[0].get("value")
        if (
            not isinstance(script, dict)
            or script.get("address") != destination_address
            or not isinstance(value, int | float)
            or isinstance(value, bool)
            or Decimal(str(value)) != Decimal(str(output_amount))
        ):
            raise cls._invalid_response(
                "decoderawtransaction",
                "Bitcoin Core returned unexpected CLTV destination metadata.",
            )

    @staticmethod
    def _compact_size(value: int) -> bytes:
        if value < 0xFD:
            return bytes([value])
        if value <= 0xFFFF:
            return b"\xfd" + struct.pack("<H", value)
        if value <= 0xFFFFFFFF:
            return b"\xfe" + struct.pack("<I", value)
        return b"\xff" + struct.pack("<Q", value)

    @staticmethod
    def _double_sha256(value: bytes) -> bytes:
        return hashlib.sha256(hashlib.sha256(value).digest()).digest()

    @staticmethod
    def _satoshis(value: Decimal) -> int:
        satoshis = value * Decimal(100_000_000)
        if satoshis != satoshis.to_integral_value():
            raise BitScopeError(
                code="INVALID_TIMELOCK_REQUEST",
                message="CLTV transaction amounts must resolve to whole satoshis.",
                status_code=400,
            )
        return int(satoshis)

    @classmethod
    def _find_output(cls, transaction: dict[str, object], address: str) -> dict[str, object]:
        outputs = transaction.get("vout")
        if not isinstance(outputs, list):
            raise BitScopeError(
                code="BITCOIN_CORE_INVALID_RESPONSE",
                message="Bitcoin Core returned a funding transaction without outputs.",
                status_code=502,
                details={"rpc_method": "decoderawtransaction"},
            )
        for output in outputs:
            if not isinstance(output, dict):
                continue
            script = output.get("scriptPubKey")
            if not isinstance(script, dict) or script.get("address") != address:
                continue
            return {
                "n": cls._require_int(output.get("n"), "decoderawtransaction", "The CLTV output has no index."),
                "value": float(
                    cls._require_decimal(output.get("value"), "decoderawtransaction", "The CLTV output has no amount.")
                ),
                "script_pub_key": cls._require_str(
                    script.get("hex"),
                    "decoderawtransaction",
                    "The CLTV output has no scriptPubKey.",
                ),
            }
        raise BitScopeError(
            code="TIMELOCK_OUTPUT_NOT_FOUND",
            message="Bitcoin Core did not return the fresh CLTV policy output.",
            status_code=502,
            details={"rpc_method": "decoderawtransaction"},
        )

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

    @staticmethod
    def _require_int(value: object, rpc_method: str, message: str) -> int:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        raise BitScopeError(
            code="BITCOIN_CORE_INVALID_RESPONSE",
            message=message,
            status_code=502,
            details={"rpc_method": rpc_method},
        )

    @staticmethod
    def _require_decimal(value: object, rpc_method: str, message: str) -> Decimal:
        if isinstance(value, int | float | str) and not isinstance(value, bool):
            try:
                parsed = Decimal(str(value))
            except ArithmeticError:
                parsed = Decimal(0)
            if parsed > 0:
                return parsed
        raise BitScopeError(
            code="BITCOIN_CORE_INVALID_RESPONSE",
            message=message,
            status_code=502,
            details={"rpc_method": rpc_method},
        )

    @staticmethod
    def _invalid_response(rpc_method: str, message: str) -> BitScopeError:
        return BitScopeError(
            code="BITCOIN_CORE_INVALID_RESPONSE",
            message=message,
            status_code=502,
            details={"rpc_method": rpc_method},
        )
