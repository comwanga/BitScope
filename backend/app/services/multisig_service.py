from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.capabilities import RegtestMutationRpcClient
from app.rpc.types import JsonValue
from app.services.network_safety import NetworkSafetyGuard
from app.services.spend_preflight import SpendPreflight


class MultisigService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = RegtestMutationRpcClient(rpc_client)

    def create(self, wallet_name: str, required_signatures: int, signer_count: int, address_type: str) -> dict[str, object]:
        NetworkSafetyGuard(self.rpc_client).require_regtest()
        clean_wallet = self._clean(wallet_name, "wallet name")
        clean_type = self._address_type(address_type)
        if required_signatures < 1 or signer_count < 1 or required_signatures > signer_count:
            raise BitScopeError(
                code="INVALID_MULTISIG_REQUEST",
                message="Required signatures must be between 1 and the signer count.",
                status_code=400,
            )
        if signer_count > 15:
            raise BitScopeError(
                code="INVALID_MULTISIG_REQUEST",
                message="BitScope limits this lab to 15 signer keys.",
                status_code=400,
            )

        source_addresses: list[str] = []
        pubkeys: list[str] = []
        raw_address_info: dict[str, object] = {}
        for index in range(signer_count):
            address = self._require_str(
                self.rpc_client.call("getnewaddress", [f"bitscope-multisig-signer-{index + 1}", "bech32"], wallet_name=clean_wallet),
                "getnewaddress",
                "Bitcoin Core did not return a signer address.",
            )
            info = self._as_dict(self.rpc_client.call("getaddressinfo", [address], wallet_name=clean_wallet))
            pubkey = self._require_str(info.get("pubkey"), "getaddressinfo", "Bitcoin Core did not return a public key for a signer address.")
            source_addresses.append(address)
            pubkeys.append(pubkey)
            raw_address_info[address] = info

        created = self._as_dict(self.rpc_client.call("createmultisig", [required_signatures, pubkeys, clean_type]))
        added = self._as_dict(
            self.rpc_client.call(
                "addmultisigaddress",
                [required_signatures, pubkeys, "bitscope-multisig", clean_type],
                wallet_name=clean_wallet,
            )
        )
        multisig_address = self._require_str(added.get("address") or created.get("address"), "addmultisigaddress", "Bitcoin Core did not return a multisig address.")

        return {
            "wallet_name": clean_wallet,
            "required_signatures": required_signatures,
            "signer_count": signer_count,
            "address_type": clean_type,
            "source_addresses": source_addresses,
            "pubkeys": pubkeys,
            "multisig_address": multisig_address,
            "redeem_script": self._optional_str(added.get("redeemScript") or created.get("redeemScript")),
            "descriptor": self._optional_str(added.get("descriptor") or created.get("descriptor")),
            "warnings": self._string_list(added.get("warnings")),
            "cli_commands": [
                f"bitcoin-cli -rpcwallet={clean_wallet} getnewaddress bitscope-multisig-signer-1 bech32",
                f"bitcoin-cli -rpcwallet={clean_wallet} getaddressinfo <signer-address>",
                f"bitcoin-cli createmultisig {required_signatures} '[<pubkeys>]' {clean_type}",
                f"bitcoin-cli -rpcwallet={clean_wallet} addmultisigaddress {required_signatures} '[<pubkeys>]' bitscope-multisig {clean_type}",
            ],
            "rpc_methods": ["getnewaddress", "getaddressinfo", "createmultisig", "addmultisigaddress"],
            "concepts": ["Multisig", "Public keys", "P2SH", "P2WSH", "Descriptor wallet", "Regtest"],
            "explanation": (
                "BitScope asks Bitcoin Core for fresh wallet public keys, constructs an m-of-n multisig script, "
                "and registers the resulting address with the wallet so regtest funding and PSBT spending can be demonstrated."
            ),
            "raw": {"getaddressinfo": raw_address_info, "createmultisig": created, "addmultisigaddress": added},
        }

    def fund(self, wallet_name: str, multisig_address: str, amount_btc: float, mine_confirmation: bool) -> dict[str, object]:
        NetworkSafetyGuard(self.rpc_client).require_regtest()
        clean_wallet = self._clean(wallet_name, "wallet name")
        clean_address = self._clean(multisig_address, "multisig address")
        amount = self._amount(amount_btc)
        preflight = SpendPreflight(self.rpc_client)
        validation = preflight.validate_address(
            clean_address,
            "INVALID_MULTISIG_ADDRESS",
            "Provide a valid multisig address from the current regtest node before funding it.",
        )
        balance = preflight.require_mature_balance(
            clean_wallet,
            amount,
            "MULTISIG_INSUFFICIENT_MATURE_FUNDS",
            (
                "The funding wallet does not have enough mature spendable balance for this multisig funding transaction. "
                "Mine enough regtest blocks to this wallet so coinbase rewards reach 101 confirmations, then retry."
            ),
        )
        txid = self._require_str(
            self.rpc_client.call("sendtoaddress", [clean_address, amount], wallet_name=clean_wallet),
            "sendtoaddress",
            "Bitcoin Core did not return a multisig funding transaction id.",
        )

        block_hashes: list[str] = []
        raw: dict[str, object] = {"validateaddress": validation, "getbalances": balance["getbalances"], "sendtoaddress": txid}
        cli_commands = [
            f"bitcoin-cli validateaddress {clean_address}",
            f"bitcoin-cli -rpcwallet={clean_wallet} getbalances",
            f"bitcoin-cli -rpcwallet={clean_wallet} sendtoaddress {clean_address} {amount:.8f}",
        ]
        rpc_methods = ["validateaddress", "getbalances", "sendtoaddress"]
        if mine_confirmation:
            mining_address = self._require_str(
                self.rpc_client.call("getnewaddress", ["bitscope-multisig-confirmation", "bech32"], wallet_name=clean_wallet),
                "getnewaddress",
                "Bitcoin Core did not return a mining address.",
            )
            mined = self.rpc_client.call("generatetoaddress", [1, mining_address])
            block_hashes = [item for item in mined if isinstance(item, str)] if isinstance(mined, list) else []
            raw["confirmation_address"] = mining_address
            raw["generatetoaddress"] = mined
            cli_commands.extend(
                [
                    f"bitcoin-cli -rpcwallet={clean_wallet} getnewaddress bitscope-multisig-confirmation bech32",
                    f"bitcoin-cli generatetoaddress 1 {mining_address}",
                ]
            )
            rpc_methods.extend(["getnewaddress", "generatetoaddress"])

        return {
            "wallet_name": clean_wallet,
            "multisig_address": clean_address,
            "amount_btc": amount,
            "txid": txid,
            "confirmation_block_hashes": block_hashes,
            "cli_commands": cli_commands,
            "rpc_methods": rpc_methods,
            "concepts": ["Multisig", "Funding transaction", "UTXO", "Confirmation"],
            "explanation": "This sends regtest coins to the multisig address, creating a UTXO that the PSBT spend step can consume.",
            "raw": raw,
        }

    def spend_psbt(self, wallet_name: str, multisig_address: str, destination_address: str, amount_btc: float, extract: bool) -> dict[str, object]:
        NetworkSafetyGuard(self.rpc_client).require_regtest()
        clean_wallet = self._clean(wallet_name, "wallet name")
        clean_multisig = self._clean(multisig_address, "multisig address")
        clean_destination = self._clean(destination_address, "destination address")
        amount = self._amount(amount_btc)
        preflight = SpendPreflight(self.rpc_client)
        multisig_validation = preflight.validate_address(
            clean_multisig,
            "INVALID_MULTISIG_ADDRESS",
            "Provide a valid multisig address from the current regtest node before creating a PSBT spend.",
        )
        destination_validation = preflight.validate_address(
            clean_destination,
            "INVALID_MULTISIG_DESTINATION_ADDRESS",
            "Provide a valid destination address from the current regtest node before creating a multisig PSBT spend.",
        )

        utxos_value = self.rpc_client.call("listunspent", [0, 9999999, [clean_multisig]], wallet_name=clean_wallet)
        utxos = [utxo for utxo in utxos_value if isinstance(utxo, dict)] if isinstance(utxos_value, list) else []
        if not utxos:
            raise BitScopeError(
                code="MULTISIG_UTXO_NOT_FOUND",
                message="Bitcoin Core did not find a wallet-known UTXO for that multisig address.",
                status_code=404,
                details={"multisig_address": clean_multisig},
            )

        inputs = [
            {"txid": txid, "vout": vout}
            for utxo in utxos
            for txid, vout in [(utxo.get("txid"), utxo.get("vout"))]
            if isinstance(txid, str) and isinstance(vout, int)
        ]
        if not inputs:
            raise BitScopeError(
                code="MULTISIG_UTXO_NOT_FOUND",
                message="Bitcoin Core returned multisig UTXOs without spendable outpoints.",
                status_code=502,
            )

        created = self._as_dict(
            self.rpc_client.call(
                "walletcreatefundedpsbt",
                [inputs, [{clean_destination: amount}], 0, {"includeWatching": True, "changeAddress": clean_multisig}, True],
                wallet_name=clean_wallet,
            )
        )
        psbt = self._require_str(created.get("psbt"), "walletcreatefundedpsbt", "Bitcoin Core did not return a multisig spend PSBT.")
        processed = self._as_dict(self.rpc_client.call("walletprocesspsbt", [psbt, True], wallet_name=clean_wallet))
        processed_psbt = self._require_str(processed.get("psbt"), "walletprocesspsbt", "Bitcoin Core did not return a processed multisig PSBT.")
        finalized = self._as_dict(self.rpc_client.call("finalizepsbt", [processed_psbt, extract]))

        return {
            "wallet_name": clean_wallet,
            "multisig_address": clean_multisig,
            "destination_address": clean_destination,
            "amount_btc": amount,
            "input_count": len(inputs),
            "psbt": psbt,
            "processed_psbt": processed_psbt,
            "complete": self._optional_bool(processed.get("complete")) is True or self._optional_bool(finalized.get("complete")) is True,
            "hex": self._optional_str(finalized.get("hex")),
            "final_psbt": self._optional_str(finalized.get("psbt")),
            "fee_btc": self._optional_float(created.get("fee")),
            "change_position": self._optional_int(created.get("changepos")),
            "cli_commands": [
                f"bitcoin-cli validateaddress {clean_multisig}",
                f"bitcoin-cli validateaddress {clean_destination}",
                f"bitcoin-cli -rpcwallet={clean_wallet} listunspent 0 9999999 '[\"{clean_multisig}\"]'",
                f"bitcoin-cli -rpcwallet={clean_wallet} walletcreatefundedpsbt '[<multisig-inputs>]' '[{{\"{clean_destination}\":{amount:.8f}}}]' 0 '{{\"includeWatching\":true,\"changeAddress\":\"{clean_multisig}\"}}' true",
                f"bitcoin-cli -rpcwallet={clean_wallet} walletprocesspsbt <psbt> true",
                f"bitcoin-cli finalizepsbt <processed-psbt> {str(extract).lower()}",
            ],
            "rpc_methods": ["validateaddress", "listunspent", "walletcreatefundedpsbt", "walletprocesspsbt", "finalizepsbt"],
            "concepts": ["Multisig", "PSBT", "Signing threshold", "Finalization", "Wallet UTXO"],
            "explanation": (
                "The wallet builds a PSBT spending UTXOs from the multisig address, signs with the keys it controls, "
                "and asks Bitcoin Core to finalize the PSBT. Extraction returns raw transaction hex without broadcasting."
            ),
            "raw": {
                "validate_multisig_address": multisig_validation,
                "validate_destination_address": destination_validation,
                "listunspent": utxos,
                "walletcreatefundedpsbt": created,
                "walletprocesspsbt": processed,
                "finalizepsbt": finalized,
            },
        }

    @staticmethod
    def _clean(value: str, label: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise BitScopeError(code="INVALID_MULTISIG_REQUEST", message=f"Provide a {label}.", status_code=400)
        return cleaned

    @staticmethod
    def _address_type(value: str) -> str:
        clean = value.strip() or "bech32"
        if clean not in {"legacy", "p2sh-segwit", "bech32"}:
            raise BitScopeError(code="INVALID_MULTISIG_REQUEST", message="Address type must be legacy, p2sh-segwit, or bech32.", status_code=400)
        return clean

    @staticmethod
    def _amount(value: float) -> float:
        if value <= 0:
            raise BitScopeError(code="INVALID_MULTISIG_REQUEST", message="Amount must be greater than zero.", status_code=400)
        return round(float(value), 8)

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
    def _string_list(value: object) -> list[str]:
        return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []
