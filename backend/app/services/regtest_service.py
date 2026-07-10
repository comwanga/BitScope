from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.types import JsonValue
from app.services.spend_preflight import SpendPreflight


class RegtestService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def mine(self, blocks: int, wallet_name: str | None = None, address: str | None = None) -> dict[str, object]:
        self._require_regtest()
        clean_wallet = self._optional_clean(wallet_name)
        clean_address = self._optional_clean(address)

        if clean_address is None:
            if clean_wallet is None:
                raise BitScopeError(
                    code="REGTEST_ADDRESS_REQUIRED",
                    message="Provide an address or a wallet name that can generate one.",
                    status_code=400,
                )
            generated = self.rpc_client.call("getnewaddress", ["bitscope-mining", "bech32"], wallet_name=clean_wallet)
            if not isinstance(generated, str):
                raise BitScopeError(
                    code="BITCOIN_CORE_INVALID_RESPONSE",
                    message="Bitcoin Core did not return a mining address.",
                    status_code=502,
                    details={"rpc_method": "getnewaddress"},
                )
            clean_address = generated

        block_hashes = self.rpc_client.call("generatetoaddress", [blocks, clean_address])
        normalized_hashes = [item for item in block_hashes if isinstance(item, str)] if isinstance(block_hashes, list) else []

        commands = []
        if clean_wallet and not address:
            commands.append(f"bitcoin-cli -rpcwallet={clean_wallet} getnewaddress bitscope-mining bech32")
        commands.append(f"bitcoin-cli generatetoaddress {blocks} {clean_address}")

        return {
            "blocks": blocks,
            "address": clean_address,
            "wallet_name": clean_wallet,
            "block_hashes": normalized_hashes,
            "cli_commands": commands,
            "rpc_methods": ["getnewaddress", "generatetoaddress"] if clean_wallet and not address else ["generatetoaddress"],
            "concepts": ["Regtest", "Mining", "Coinbase transaction", "Coinbase maturity"],
            "explanation": (
                "Regtest mining creates blocks immediately. Coinbase outputs become spendable after 100 confirmations, "
                "so a fresh wallet usually mines 101 blocks before spending."
            ),
            "raw": {"generatetoaddress": block_hashes},
        }

    def faucet(self, wallet_name: str, address: str, amount_btc: float, mine_confirmation: bool = True) -> dict[str, object]:
        self._require_regtest()
        clean_wallet = self._clean(wallet_name, "wallet name")
        clean_address = self._clean(address, "destination address")
        amount = self._amount(amount_btc)
        preflight = SpendPreflight(self.rpc_client)
        validation = preflight.validate_address(
            clean_address,
            "INVALID_REGTEST_ADDRESS",
            "Provide a valid address from the current regtest node. Addresses copied from an older regtest reset or wallet run can be stale.",
        )
        balance = preflight.require_mature_balance(
            clean_wallet,
            amount,
            "REGTEST_INSUFFICIENT_MATURE_FUNDS",
            (
                "The sending wallet does not have enough mature spendable balance. Mine enough regtest blocks to this wallet "
                "so coinbase rewards reach 101 confirmations, then retry the faucet send."
            ),
            fee_headroom_btc=0.0,
        )

        txid = self.rpc_client.call("sendtoaddress", [clean_address, amount], wallet_name=clean_wallet)
        if not isinstance(txid, str):
            raise BitScopeError(
                code="BITCOIN_CORE_INVALID_RESPONSE",
                message="Bitcoin Core did not return a transaction id.",
                status_code=502,
                details={"rpc_method": "sendtoaddress"},
            )

        confirmation_hashes: list[str] = []
        raw: dict[str, JsonValue] = {"validateaddress": validation, "getbalances": balance["getbalances"], "sendtoaddress": txid}
        commands = [
            f"bitcoin-cli validateaddress {clean_address}",
            f"bitcoin-cli -rpcwallet={clean_wallet} getbalances",
            f"bitcoin-cli -rpcwallet={clean_wallet} sendtoaddress {clean_address} {amount:.8f}",
        ]
        rpc_methods = ["validateaddress", "getbalances", "sendtoaddress"]

        if mine_confirmation:
            mined = self.mine(1, wallet_name=clean_wallet)
            confirmation_hashes = [item for item in mined["block_hashes"] if isinstance(item, str)]  # type: ignore[index]
            raw["confirmation_mine"] = mined["raw"]  # type: ignore[assignment]
            commands.extend(command for command in mined["cli_commands"] if isinstance(command, str))  # type: ignore[union-attr]
            rpc_methods.append("generatetoaddress")

        return {
            "txid": txid,
            "wallet_name": clean_wallet,
            "address": clean_address,
            "amount_btc": amount,
            "trusted_balance_btc": balance["trusted_btc"],
            "immature_balance_btc": balance["immature_btc"],
            "confirmation_block_hashes": confirmation_hashes,
            "cli_commands": commands,
            "rpc_methods": rpc_methods,
            "concepts": ["Regtest", "Faucet", "Wallet send", "Confirmation"],
            "explanation": "The regtest faucet sends coins from a local wallet and can mine one block to confirm the transaction.",
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
    def _optional_clean(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @classmethod
    def _clean(cls, value: str, label: str) -> str:
        cleaned = cls._optional_clean(value)
        if cleaned is None:
            raise BitScopeError(
                code="INVALID_REGTEST_REQUEST",
                message=f"Provide a {label}.",
                status_code=400,
            )
        return cleaned

    @staticmethod
    def _amount(value: float) -> float:
        amount = round(float(value), 8)
        if amount <= 0:
            raise BitScopeError(
                code="INVALID_REGTEST_REQUEST",
                message="Amount must be greater than zero.",
                status_code=400,
            )
        return amount
