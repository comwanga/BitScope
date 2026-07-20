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

    def create_from_signer_wallets(
        self,
        wallet_names: list[str],
        required_signatures: int,
        address_type: str,
    ) -> dict[str, object]:
        """Create one multisig script with exactly one signer key from each wallet."""

        NetworkSafetyGuard(self.rpc_client).require_regtest()
        clean_wallets = [self._clean(wallet_name, "signer wallet name") for wallet_name in wallet_names]
        if len(clean_wallets) < 2 or len(clean_wallets) > 15 or len(clean_wallets) != len(set(clean_wallets)):
            raise BitScopeError(
                code="INVALID_MULTISIG_REQUEST",
                message="Provide between 2 and 15 distinct signer wallets.",
                status_code=400,
            )
        if required_signatures < 1 or required_signatures > len(clean_wallets):
            raise BitScopeError(
                code="INVALID_MULTISIG_REQUEST",
                message="Required signatures must be between 1 and the signer count.",
                status_code=400,
            )
        clean_type = self._address_type(address_type)
        source_addresses: list[str] = []
        pubkeys: list[str] = []
        address_info: dict[str, object] = {}
        for index, wallet_name in enumerate(clean_wallets):
            address = self._require_str(
                self.rpc_client.call(
                    "getnewaddress",
                    [f"bitscope-multisig-signer-{index + 1}", "bech32"],
                    wallet_name=wallet_name,
                ),
                "getnewaddress",
                "Bitcoin Core did not return a signer address.",
            )
            info = self._as_dict(
                self.rpc_client.call("getaddressinfo", [address], wallet_name=wallet_name)
            )
            pubkey = self._require_str(
                info.get("pubkey"),
                "getaddressinfo",
                "Bitcoin Core did not return a public key for a signer address.",
            )
            source_addresses.append(address)
            pubkeys.append(pubkey)
            address_info[wallet_name] = info

        created = self._as_dict(
            self.rpc_client.call("createmultisig", [required_signatures, pubkeys, clean_type])
        )
        registrations: dict[str, object] = {}
        for wallet_name in clean_wallets:
            registrations[wallet_name] = self._as_dict(
                self.rpc_client.call(
                    "addmultisigaddress",
                    [required_signatures, pubkeys, "bitscope-multisig", clean_type],
                    wallet_name=wallet_name,
                )
            )
        first_registration = self._as_dict(registrations[clean_wallets[0]])
        multisig_address = self._require_str(
            first_registration.get("address") or created.get("address"),
            "addmultisigaddress",
            "Bitcoin Core did not return a multisig address.",
        )
        registered_addresses = {
            self._optional_str(self._as_dict(value).get("address"))
            for value in registrations.values()
        }
        if registered_addresses != {multisig_address}:
            raise BitScopeError(
                code="BITCOIN_CORE_INVALID_RESPONSE",
                message="Signer wallets did not register the same multisig address.",
                status_code=502,
                details={"rpc_method": "addmultisigaddress"},
            )
        watch_imports: dict[str, object] = {}
        for wallet_name in clean_wallets:
            watch_imports[wallet_name] = self.rpc_client.call(
                "importaddress",
                [multisig_address, "bitscope-multisig-watch", False],
                wallet_name=wallet_name,
            )

        return {
            "signer_wallets": clean_wallets,
            "required_signatures": required_signatures,
            "signer_count": len(clean_wallets),
            "address_type": clean_type,
            "source_addresses": source_addresses,
            "pubkeys": pubkeys,
            "multisig_address": multisig_address,
            "redeem_script": self._optional_str(
                first_registration.get("redeemScript") or created.get("redeemScript")
            ),
            "descriptor": self._optional_str(
                first_registration.get("descriptor") or created.get("descriptor")
            ),
            "cli_commands": [
                "bitcoin-cli -rpcwallet=<signer-wallet> getnewaddress bitscope-multisig-signer-1 bech32",
                "bitcoin-cli -rpcwallet=<signer-wallet> getaddressinfo <signer-address>",
                f"bitcoin-cli createmultisig {required_signatures} '[<pubkeys>]' {clean_type}",
                (
                    f"bitcoin-cli -rpcwallet=<signer-wallet> addmultisigaddress {required_signatures} "
                    f"'[<pubkeys>]' bitscope-multisig {clean_type}"
                ),
                (
                    "bitcoin-cli -rpcwallet=<signer-wallet> importaddress "
                    f"{multisig_address} bitscope-multisig-watch false"
                ),
            ],
            "rpc_methods": [
                "getnewaddress",
                "getaddressinfo",
                "createmultisig",
                "addmultisigaddress",
                "importaddress",
            ],
            "concepts": ["Multisig", "PSBT", "Signing threshold", "Legacy wallet"],
            "explanation": (
                "Each session-owned legacy wallet contributes one public key and registers the same multisig script. "
                "The wallets remain local simulation contexts, not independent external custodians."
            ),
            "raw": {
                "getaddressinfo": address_info,
                "createmultisig": created,
                "addmultisigaddress": registrations,
                "importaddress": watch_imports,
            },
        }

    def fund(
        self,
        wallet_name: str,
        multisig_address: str,
        amount_btc: float,
        mine_confirmation: bool,
        fee_rate_sat_vb: float | None = None,
    ) -> dict[str, object]:
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
        send_parameters: list[object] = [clean_address, amount]
        if fee_rate_sat_vb is not None:
            fee_rate = round(float(fee_rate_sat_vb), 3)
            if fee_rate <= 0:
                raise BitScopeError(
                    code="INVALID_MULTISIG_REQUEST",
                    message="The funding fee rate must be greater than zero.",
                    status_code=400,
                )
            send_parameters = [
                clean_address,
                amount,
                "",
                "",
                False,
                True,
                None,
                "unset",
                None,
                fee_rate,
            ]
        txid = self._require_str(
            self.rpc_client.call("sendtoaddress", send_parameters, wallet_name=clean_wallet),
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

    def create_spend_psbt(
        self,
        wallet_name: str,
        multisig_address: str,
        destination_address: str,
        amount_btc: float,
        fee_rate_sat_vb: float,
    ) -> dict[str, object]:
        """Construct a multisig PSBT without signing or finalizing it."""

        NetworkSafetyGuard(self.rpc_client).require_regtest()
        clean_wallet = self._clean(wallet_name, "signer wallet name")
        clean_multisig = self._clean(multisig_address, "multisig address")
        clean_destination = self._clean(destination_address, "destination address")
        amount = self._amount(amount_btc)
        fee_rate = round(float(fee_rate_sat_vb), 3)
        if fee_rate <= 0:
            raise BitScopeError(
                code="INVALID_MULTISIG_REQUEST",
                message="The PSBT fee rate must be greater than zero.",
                status_code=400,
            )
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
        utxos_value = self.rpc_client.call(
            "listunspent",
            [1, 9_999_999, [clean_multisig]],
            wallet_name=clean_wallet,
        )
        utxos = [item for item in utxos_value if isinstance(item, dict)] if isinstance(utxos_value, list) else []
        inputs = [
            {"txid": item["txid"], "vout": item["vout"]}
            for item in utxos
            if isinstance(item.get("txid"), str)
            and isinstance(item.get("vout"), int)
            and not isinstance(item.get("vout"), bool)
        ]
        if not inputs:
            raise BitScopeError(
                code="MULTISIG_UTXO_NOT_FOUND",
                message="Bitcoin Core did not find a confirmed wallet-known multisig output.",
                status_code=404,
                details={"multisig_address": clean_multisig},
            )
        options = {
            "includeWatching": True,
            "changeAddress": clean_multisig,
            "fee_rate": fee_rate,
        }
        created = self._as_dict(
            self.rpc_client.call(
                "walletcreatefundedpsbt",
                [inputs, [{clean_destination: amount}], 0, options, True],
                wallet_name=clean_wallet,
            )
        )
        psbt = self._require_str(
            created.get("psbt"),
            "walletcreatefundedpsbt",
            "Bitcoin Core did not return a multisig spend PSBT.",
        )
        return {
            "wallet_name": clean_wallet,
            "multisig_address": clean_multisig,
            "destination_address": clean_destination,
            "amount_btc": amount,
            "input_count": len(inputs),
            "inputs": inputs,
            "psbt": psbt,
            "fee_btc": self._optional_float(created.get("fee")),
            "change_position": self._optional_int(created.get("changepos")),
            "cli_commands": [
                f"bitcoin-cli -rpcwallet={clean_wallet} listunspent 1 9999999 '[\"{clean_multisig}\"]'",
                (
                    f"bitcoin-cli -rpcwallet={clean_wallet} walletcreatefundedpsbt '[<multisig-inputs>]' "
                    f"'[{{\"{clean_destination}\":{amount:.8f}}}]' 0 "
                    f"'{{\"includeWatching\":true,\"changeAddress\":\"{clean_multisig}\","
                    f"\"fee_rate\":{fee_rate:.3f}}}' true"
                ),
            ],
            "rpc_methods": ["validateaddress", "listunspent", "walletcreatefundedpsbt"],
            "concepts": ["Multisig", "PSBT", "Signing threshold", "Wallet UTXO"],
            "explanation": (
                "The first signer wallet constructs an unsigned funded PSBT from the confirmed multisig output. "
                "Signing and finalization remain separate explicit actions."
            ),
            "raw": {
                "validate_multisig_address": multisig_validation,
                "validate_destination_address": destination_validation,
                "listunspent": utxos,
                "walletcreatefundedpsbt": created,
            },
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
