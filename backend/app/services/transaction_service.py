from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.errors import RpcError
from app.rpc.types import JsonValue


class TransactionService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def get_transaction(self, txid: str) -> dict[str, object]:
        cleaned_txid = self._clean_txid(txid)

        try:
            raw_transaction = self.rpc_client.call("getrawtransaction", [cleaned_txid, True])
        except RpcError as exc:
            if exc.code in {"BITCOIN_CORE_NOT_FOUND", "INVALID_RPC_PARAMETER"}:
                raise BitScopeError(
                    code="TRANSACTION_NOT_FOUND",
                    message=(
                        "Bitcoin Core could not find that transaction. If it is confirmed, your node may need "
                        "txindex=1 or the block hash supplied by a later BitScope phase."
                    ),
                    status_code=404,
                    details={"txid": cleaned_txid},
                ) from exc
            raise

        raw_data = self._as_dict(raw_transaction)
        if not raw_data:
            raise BitScopeError(
                code="TRANSACTION_NOT_FOUND",
                message="Bitcoin Core returned an empty transaction response.",
                status_code=404,
                details={"txid": cleaned_txid},
            )

        tx_hex = raw_data.get("hex")
        decoded = raw_data
        if isinstance(tx_hex, str):
            try:
                decoded_value = self.rpc_client.call("decoderawtransaction", [tx_hex])
                decoded_dict = self._as_dict(decoded_value)
                if decoded_dict:
                    decoded = decoded_dict
            except RpcError:
                decoded = raw_data

        mempool_entry: dict[str, object] | None = None
        try:
            mempool_value = self.rpc_client.call("getmempoolentry", [cleaned_txid])
            mempool_entry = self._as_dict(mempool_value)
        except RpcError as exc:
            if exc.code not in {"BITCOIN_CORE_NOT_FOUND", "INVALID_RPC_PARAMETER"}:
                raise

        inputs = [self._normalize_input(item) for item in decoded.get("vin", []) if isinstance(item, dict)]
        outputs = [self._normalize_output(item) for item in decoded.get("vout", []) if isinstance(item, dict)]

        fee_btc = None
        fee_source = None
        if mempool_entry and isinstance(mempool_entry.get("fees"), dict):
            fees = mempool_entry["fees"]
            base_fee = fees.get("base") if isinstance(fees, dict) else None
            if isinstance(base_fee, int | float):
                fee_btc = float(base_fee)
                fee_source = "getmempoolentry.fees.base"

        confirmations = raw_data.get("confirmations")
        in_mempool = mempool_entry is not None

        return {
            "txid": str(decoded.get("txid") or raw_data.get("txid") or cleaned_txid),
            "hash": decoded.get("hash") or raw_data.get("hash"),
            "version": decoded.get("version"),
            "size": decoded.get("size"),
            "vsize": decoded.get("vsize"),
            "weight": decoded.get("weight"),
            "locktime": decoded.get("locktime"),
            "confirmations": confirmations if isinstance(confirmations, int) else None,
            "block_hash": raw_data.get("blockhash"),
            "block_time": raw_data.get("blocktime"),
            "time": raw_data.get("time"),
            "in_mempool": in_mempool,
            "fee_btc": fee_btc,
            "fee_source": fee_source,
            "inputs": inputs,
            "outputs": outputs,
            "cli_commands": [
                f"bitcoin-cli getrawtransaction {cleaned_txid} true",
                f"bitcoin-cli decoderawtransaction <raw-transaction-hex>",
                f"bitcoin-cli getmempoolentry {cleaned_txid}",
            ],
            "rpc_methods": ["getrawtransaction", "decoderawtransaction", "getmempoolentry"],
            "concepts": ["Transaction", "UTXO", "Input", "Output", "Fee", "Script", "Witness", "Locktime"],
            "explanation": (
                "A transaction spends previous outputs as inputs and creates new outputs. Bitcoin Core can decode "
                "the structure directly; fee calculation is only shown when the node provides reliable context."
            ),
            "raw": {
                "getrawtransaction": raw_data,
                "decoderawtransaction": decoded,
                "getmempoolentry": mempool_entry,
            },
        }

    def transaction_policy(self, txid: str) -> dict[str, object]:
        cleaned_txid = self._clean_txid(txid)

        try:
            entry = self._as_dict(self.rpc_client.call("getmempoolentry", [cleaned_txid]))
        except RpcError as exc:
            if exc.code in {"BITCOIN_CORE_NOT_FOUND", "INVALID_RPC_PARAMETER"}:
                raise BitScopeError(
                    code="TRANSACTION_NOT_IN_MEMPOOL",
                    message="Bitcoin Core does not currently have that transaction in its mempool.",
                    status_code=404,
                    details={"txid": cleaned_txid},
                ) from exc
            raise

        fees = entry.get("fees") if isinstance(entry.get("fees"), dict) else {}
        fee_btc = self._optional_float(fees.get("base") if isinstance(fees, dict) else None)
        modified_fee_btc = self._optional_float(fees.get("modified") if isinstance(fees, dict) else None)
        ancestor_fees_btc = self._optional_float(fees.get("ancestor") if isinstance(fees, dict) else None)
        descendant_fees_btc = self._optional_float(fees.get("descendant") if isinstance(fees, dict) else None)
        vsize = self._optional_int(entry.get("vsize"))
        bip125 = self._optional_bool(entry.get("bip125-replaceable"))
        fee_rate = self._sat_vb(fee_btc, vsize)

        warnings: list[str] = []
        if bip125 is False:
            warnings.append("This transaction does not signal BIP125 replaceability, so wallet RBF may not be available.")
        if vsize is None or fee_btc is None:
            warnings.append("Bitcoin Core did not return enough fee data to compute a base fee rate.")

        return {
            "txid": cleaned_txid,
            "in_mempool": True,
            "bip125_replaceable": bip125,
            "can_rbf": bip125 is True,
            "can_cpfp": True,
            "fee_btc": fee_btc,
            "modified_fee_btc": modified_fee_btc,
            "vsize": vsize,
            "fee_rate_sat_vb": fee_rate,
            "ancestor_count": self._optional_int(entry.get("ancestorcount")),
            "ancestor_size": self._optional_int(entry.get("ancestorsize")),
            "ancestor_fees_btc": ancestor_fees_btc,
            "descendant_count": self._optional_int(entry.get("descendantcount")),
            "descendant_size": self._optional_int(entry.get("descendantsize")),
            "descendant_fees_btc": descendant_fees_btc,
            "warnings": warnings,
            "cli_commands": [f"bitcoin-cli getmempoolentry {cleaned_txid}"],
            "rpc_methods": ["getmempoolentry"],
            "concepts": ["Mempool policy", "BIP125 replace-by-fee", "CPFP", "Ancestors", "Descendants", "Fee rate"],
            "explanation": (
                "Bitcoin Core mempool policy data explains whether an unconfirmed transaction signals replacement, "
                "how much fee it pays, and how it relates to ancestor or descendant packages. RBF replaces the parent; "
                "CPFP spends one of its outputs with a high-fee child."
            ),
            "raw": {"getmempoolentry": entry},
        }

    def bump_rbf_transaction(
        self,
        wallet_name: str,
        txid: str,
        fee_rate_sat_vb: float | None,
        conf_target: int | None,
    ) -> dict[str, object]:
        self._require_regtest()
        clean_wallet = self._clean(wallet_name, "wallet name")
        clean_txid = self._clean_txid(txid)

        options: dict[str, object] = {}
        if fee_rate_sat_vb is not None:
            options["fee_rate"] = round(float(fee_rate_sat_vb), 3)
        if conf_target is not None:
            options["conf_target"] = int(conf_target)
            options["estimate_mode"] = "economical"

        result = self._as_dict(self.rpc_client.call("bumpfee", [clean_txid, options], wallet_name=clean_wallet))
        errors = [item for item in result.get("errors", []) if isinstance(item, str)] if isinstance(result.get("errors"), list) else []
        replacement_txid = self._optional_str(result.get("txid"))

        return {
            "wallet_name": clean_wallet,
            "original_txid": clean_txid,
            "replacement_txid": replacement_txid,
            "original_fee_btc": self._optional_float(result.get("origfee")),
            "replacement_fee_btc": self._optional_float(result.get("fee")),
            "fee_delta_btc": self._optional_float(result.get("fee_delta")),
            "errors": errors,
            "cli_commands": [f"bitcoin-cli -rpcwallet={clean_wallet} bumpfee {clean_txid} '{self._cli_json(options)}'"],
            "rpc_methods": ["bumpfee"],
            "concepts": ["RBF", "BIP125 replace-by-fee", "Mempool policy", "Fee rate", "Wallet"],
            "explanation": (
                "Bitcoin Core's wallet `bumpfee` creates and broadcasts a replacement transaction for a wallet-owned "
                "unconfirmed transaction that signals BIP125 replaceability. BitScope keeps this regtest-only because "
                "fee bumping broadcasts a new transaction."
            ),
            "raw": {"bumpfee": result},
        }

    def create_cpfp_child(
        self,
        wallet_name: str,
        parent_txid: str,
        parent_vout: int,
        destination_address: str,
        amount_btc: float,
        fee_rate_sat_vb: float | None,
        broadcast: bool,
    ) -> dict[str, object]:
        self._require_regtest()
        clean_wallet = self._clean(wallet_name, "wallet name")
        clean_txid = self._clean_txid(parent_txid)
        clean_address = self._clean(destination_address, "destination address")
        clean_amount = self._clean_amount(amount_btc)

        input_ref = {"txid": clean_txid, "vout": int(parent_vout)}
        unsigned_hex = self._require_str(
            self.rpc_client.call("createrawtransaction", [[input_ref], {clean_address: clean_amount}]),
            "createrawtransaction",
            "Bitcoin Core did not return a CPFP child transaction skeleton.",
        )
        options: dict[str, object] = {"lockUnspents": True}
        if fee_rate_sat_vb is not None:
            options["fee_rate"] = round(float(fee_rate_sat_vb), 3)

        funded = self._as_dict(self.rpc_client.call("fundrawtransaction", [unsigned_hex, options], wallet_name=clean_wallet))
        funded_hex = self._require_str(
            funded.get("hex"),
            "fundrawtransaction",
            "Bitcoin Core did not return a funded CPFP child transaction.",
        )
        signed = self._as_dict(self.rpc_client.call("signrawtransactionwithwallet", [funded_hex], wallet_name=clean_wallet))
        signed_hex = self._optional_str(signed.get("hex"))
        complete = self._optional_bool(signed.get("complete")) or False
        decoded = self._as_dict(self.rpc_client.call("decoderawtransaction", [signed_hex or funded_hex]))
        mempool_accept = self.rpc_client.call("testmempoolaccept", [[signed_hex or funded_hex]]) if signed_hex else []
        child_txid = self._optional_str(decoded.get("txid"))
        raw: dict[str, object] = {
            "createrawtransaction": unsigned_hex,
            "fundrawtransaction": funded,
            "signrawtransactionwithwallet": signed,
            "decoderawtransaction": decoded,
            "testmempoolaccept": mempool_accept,
        }
        cli_commands = [
            f"bitcoin-cli createrawtransaction '[{self._cli_json(input_ref)}]' '{{\"{clean_address}\":{clean_amount:.8f}}}'",
            f"bitcoin-cli -rpcwallet={clean_wallet} fundrawtransaction {unsigned_hex} '{self._cli_json(options)}'",
            f"bitcoin-cli -rpcwallet={clean_wallet} signrawtransactionwithwallet {funded_hex}",
            f"bitcoin-cli testmempoolaccept '[\"{signed_hex or funded_hex}\"]'",
        ]
        rpc_methods = ["createrawtransaction", "fundrawtransaction", "signrawtransactionwithwallet", "decoderawtransaction", "testmempoolaccept"]

        if broadcast:
            if not signed_hex or not complete:
                raise BitScopeError(
                    code="CPFP_CHILD_INCOMPLETE",
                    message="Bitcoin Core could not fully sign the CPFP child transaction.",
                    status_code=400,
                    details={"parent_txid": clean_txid, "parent_vout": parent_vout},
                )
            child_txid = self._require_str(
                self.rpc_client.call("sendrawtransaction", [signed_hex]),
                "sendrawtransaction",
                "Bitcoin Core did not return a CPFP child transaction id.",
            )
            raw["sendrawtransaction"] = child_txid
            cli_commands.append(f"bitcoin-cli sendrawtransaction {signed_hex}")
            rpc_methods.append("sendrawtransaction")

        return {
            "wallet_name": clean_wallet,
            "parent_txid": clean_txid,
            "parent_vout": int(parent_vout),
            "destination_address": clean_address,
            "amount_btc": clean_amount,
            "unsigned_hex": unsigned_hex,
            "funded_hex": funded_hex,
            "signed_hex": signed_hex,
            "complete": complete,
            "child_txid": child_txid,
            "fee_btc": self._optional_float(funded.get("fee")),
            "change_position": self._optional_int(funded.get("changepos")),
            "broadcast": broadcast,
            "cli_commands": cli_commands,
            "rpc_methods": rpc_methods,
            "concepts": ["CPFP", "Child pays for parent", "Mempool package", "Fee rate", "Unconfirmed UTXO"],
            "explanation": (
                "A CPFP child spends an unconfirmed parent output and pays enough fee that miners may prefer confirming "
                "the parent and child together. This flow is regtest-only and uses `testmempoolaccept` before optional broadcast."
            ),
            "raw": raw,
        }

    def build_regtest_transaction(self, wallet_name: str, address: str, amount_btc: float) -> dict[str, object]:
        self._require_regtest()
        clean_wallet = self._clean(wallet_name, "wallet name")
        clean_address = self._clean(address, "destination address")
        clean_amount = self._clean_amount(amount_btc)

        unsigned_hex = self._require_str(
            self.rpc_client.call("createrawtransaction", [[], {clean_address: clean_amount}]),
            "createrawtransaction",
            "Bitcoin Core did not return an unsigned raw transaction.",
        )
        funded = self._as_dict(self.rpc_client.call("fundrawtransaction", [unsigned_hex], wallet_name=clean_wallet))
        funded_hex = self._require_str(
            funded.get("hex"),
            "fundrawtransaction",
            "Bitcoin Core did not return a funded raw transaction.",
        )
        signed = self._as_dict(self.rpc_client.call("signrawtransactionwithwallet", [funded_hex], wallet_name=clean_wallet))
        signed_hex = self._optional_str(signed.get("hex"))
        complete = self._optional_bool(signed.get("complete")) or False
        decoded = self._as_dict(self.rpc_client.call("decoderawtransaction", [signed_hex or funded_hex]))
        txid = self._optional_str(decoded.get("txid"))

        return self._transaction_builder_response(
            clean_wallet,
            clean_address,
            clean_amount,
            unsigned_hex,
            funded,
            funded_hex,
            signed,
            signed_hex,
            complete,
            decoded,
            txid,
            [],
            {"createrawtransaction": unsigned_hex, "fundrawtransaction": funded, "signrawtransactionwithwallet": signed, "decoderawtransaction": decoded},
            broadcast_txid=None,
        )

    def send_regtest_transaction(
        self,
        wallet_name: str,
        address: str,
        amount_btc: float,
        mine_confirmation: bool = True,
    ) -> dict[str, object]:
        built = self.build_regtest_transaction(wallet_name, address, amount_btc)
        signed_hex = built.get("signed_hex")
        if not isinstance(signed_hex, str) or not built.get("complete"):
            raise BitScopeError(
                code="REGTEST_TRANSACTION_INCOMPLETE",
                message="Bitcoin Core could not fully sign the funded transaction.",
                status_code=400,
                details={"wallet_name": wallet_name},
            )

        txid = self._require_str(
            self.rpc_client.call("sendrawtransaction", [signed_hex]),
            "sendrawtransaction",
            "Bitcoin Core did not return a broadcast transaction id.",
        )

        confirmation_hashes: list[str] = []
        raw = self._as_dict(built["raw"])
        raw["sendrawtransaction"] = txid
        cli_commands = [command for command in built["cli_commands"] if isinstance(command, str)]
        cli_commands.append(f"bitcoin-cli sendrawtransaction {signed_hex}")
        rpc_methods = [method for method in built["rpc_methods"] if isinstance(method, str)]
        rpc_methods.append("sendrawtransaction")

        if mine_confirmation:
            mining_address = self._require_str(
                self.rpc_client.call("getnewaddress", ["bitscope-confirmation", "bech32"], wallet_name=str(built["wallet_name"])),
                "getnewaddress",
                "Bitcoin Core did not return a confirmation mining address.",
            )
            mined = self.rpc_client.call("generatetoaddress", [1, mining_address])
            confirmation_hashes = [item for item in mined if isinstance(item, str)] if isinstance(mined, list) else []
            raw["confirmation_address"] = mining_address
            raw["generatetoaddress"] = mined
            cli_commands.append(f"bitcoin-cli -rpcwallet={built['wallet_name']} getnewaddress bitscope-confirmation bech32")
            cli_commands.append(f"bitcoin-cli generatetoaddress 1 {mining_address}")
            rpc_methods.extend(["getnewaddress", "generatetoaddress"])

        response = dict(built)
        response.update(
            {
                "txid": txid,
                "confirmation_block_hashes": confirmation_hashes,
                "cli_commands": cli_commands,
                "rpc_methods": rpc_methods,
                "explanation": (
                    "BitScope built, funded, signed, and broadcast a regtest transaction using Bitcoin Core raw transaction RPCs. "
                    "If confirmation mining was enabled, it mined one local block after broadcast."
                ),
                "raw": raw,
            }
        )
        return response

    @staticmethod
    def _normalize_input(vin: dict[str, object]) -> dict[str, object]:
        script_sig = vin.get("scriptSig") if isinstance(vin.get("scriptSig"), dict) else {}
        witness = vin.get("txinwitness") if isinstance(vin.get("txinwitness"), list) else []

        return {
            "coinbase": vin.get("coinbase") if isinstance(vin.get("coinbase"), str) else None,
            "previous_txid": vin.get("txid") if isinstance(vin.get("txid"), str) else None,
            "vout": vin.get("vout") if isinstance(vin.get("vout"), int) else None,
            "sequence": vin.get("sequence") if isinstance(vin.get("sequence"), int) else None,
            "script_sig_asm": script_sig.get("asm") if isinstance(script_sig.get("asm"), str) else None,
            "script_sig_hex": script_sig.get("hex") if isinstance(script_sig.get("hex"), str) else None,
            "witness": [item for item in witness if isinstance(item, str)],
        }

    @staticmethod
    def _normalize_output(vout: dict[str, object]) -> dict[str, object]:
        script_pub_key = vout.get("scriptPubKey") if isinstance(vout.get("scriptPubKey"), dict) else {}
        address = script_pub_key.get("address")
        if not isinstance(address, str):
            addresses = script_pub_key.get("addresses")
            address = addresses[0] if isinstance(addresses, list) and addresses and isinstance(addresses[0], str) else None

        value = vout.get("value")
        return {
            "n": vout.get("n") if isinstance(vout.get("n"), int) else 0,
            "value_btc": float(value) if isinstance(value, int | float) else 0.0,
            "script_pub_key_asm": script_pub_key.get("asm") if isinstance(script_pub_key.get("asm"), str) else None,
            "script_pub_key_hex": script_pub_key.get("hex") if isinstance(script_pub_key.get("hex"), str) else None,
            "script_type": script_pub_key.get("type") if isinstance(script_pub_key.get("type"), str) else None,
            "address": address,
        }

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    def _transaction_builder_response(
        self,
        wallet_name: str,
        address: str,
        amount_btc: float,
        unsigned_hex: str,
        funded: dict[str, object],
        funded_hex: str,
        signed: dict[str, object],
        signed_hex: str | None,
        complete: bool,
        decoded: dict[str, object],
        txid: str | None,
        confirmation_hashes: list[str],
        raw: dict[str, object],
        broadcast_txid: str | None,
    ) -> dict[str, object]:
        fee = self._optional_float(funded.get("fee"))
        change_position = self._optional_int(funded.get("changepos"))
        display_txid = broadcast_txid or txid
        return {
            "wallet_name": wallet_name,
            "address": address,
            "amount_btc": amount_btc,
            "unsigned_hex": unsigned_hex,
            "funded_hex": funded_hex,
            "signed_hex": signed_hex,
            "complete": complete,
            "txid": display_txid,
            "fee_btc": fee,
            "change_position": change_position,
            "confirmation_block_hashes": confirmation_hashes,
            "cli_commands": [
                f"bitcoin-cli createrawtransaction [] '{{\"{address}\":{amount_btc:.8f}}}'",
                f"bitcoin-cli -rpcwallet={wallet_name} fundrawtransaction {unsigned_hex}",
                f"bitcoin-cli -rpcwallet={wallet_name} signrawtransactionwithwallet {funded_hex}",
                f"bitcoin-cli decoderawtransaction {signed_hex or funded_hex}",
            ],
            "rpc_methods": ["createrawtransaction", "fundrawtransaction", "signrawtransactionwithwallet", "decoderawtransaction"],
            "concepts": ["Regtest", "Raw transaction", "Coin selection", "Change output", "Wallet signing", "Broadcast"],
            "explanation": (
                "This regtest builder starts with an output-only raw transaction, asks the wallet to select inputs and add change, "
                "then signs the funded transaction without broadcasting it."
            ),
            "raw": raw,
        }

    def _require_regtest(self) -> None:
        if self.rpc_client.settings.bitcoin_network != "regtest":
            raise BitScopeError(
                code="REGTEST_ONLY",
                message="This action is only available when BITCOIN_NETWORK is set to regtest.",
                status_code=400,
                details={"network": self.rpc_client.settings.bitcoin_network},
            )

    @staticmethod
    def _clean(value: str, label: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise BitScopeError(
                code="INVALID_REGTEST_TRANSACTION",
                message=f"Provide a {label}.",
                status_code=400,
            )
        return cleaned

    @staticmethod
    def _clean_amount(amount_btc: float) -> float:
        if amount_btc <= 0:
            raise BitScopeError(
                code="INVALID_REGTEST_TRANSACTION",
                message="Amount must be greater than zero.",
                status_code=400,
            )
        return round(float(amount_btc), 8)

    @staticmethod
    def _clean_txid(txid: str) -> str:
        cleaned_txid = txid.strip()
        if len(cleaned_txid) != 64 or not all(character in "0123456789abcdefABCDEF" for character in cleaned_txid):
            raise BitScopeError(
                code="INVALID_TXID",
                message="Enter a 64-character transaction id in hexadecimal.",
                status_code=400,
                details={"txid": txid},
            )
        return cleaned_txid

    @staticmethod
    def _sat_vb(fee_btc: float | None, vsize: int | None) -> float | None:
        if fee_btc is None or not vsize:
            return None
        return round((fee_btc * 100_000_000) / vsize, 2)

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
