from datetime import UTC, datetime

from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.errors import RpcError
from app.rpc.types import JsonValue


SCRIPT_SAMPLE_HEX = "76a91489abcdefabbaabbaabbaabbaabbaabbaabbaabba88ac"


class DemoService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def run(
        self,
        wallet_name: str,
        fresh_wallet: bool,
        mine_blocks: int,
        send_amount_btc: float,
        include_script_sample: bool,
    ) -> dict[str, object]:
        self._require_regtest()
        session_id = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        clean_wallet = self._wallet_name(wallet_name)
        active_wallet = f"{clean_wallet}-{session_id}" if fresh_wallet else clean_wallet
        amount = round(float(send_amount_btc), 8)

        steps: list[dict[str, object]] = []
        block_hashes: list[str] = []
        confirmation_hashes: list[str] = []
        txid: str | None = None

        wallet_raw = self._ensure_wallet(active_wallet)
        steps.append(
            self._step(
                "wallet",
                "Create or load demo wallet",
                "completed",
                f"Wallet `{active_wallet}` is loaded and ready for wallet RPC calls.",
                [
                    f"bitcoin-cli createwallet {active_wallet}",
                    f"bitcoin-cli loadwallet {active_wallet}",
                ],
                ["createwallet", "loadwallet", "listwallets", "listwalletdir"],
                ["Wallet", "Descriptor wallet", "Wallet RPC endpoint"],
                wallet_raw,
            )
        )

        mining_address = self._string_call("getnewaddress", ["bitscope-demo-mining", "bech32"], active_wallet)
        mined = self.rpc_client.call("generatetoaddress", [mine_blocks, mining_address])
        block_hashes = [item for item in mined if isinstance(item, str)] if isinstance(mined, list) else []
        steps.append(
            self._step(
                "mine",
                "Mine spendable regtest coins",
                "completed",
                f"Mined {len(block_hashes)} blocks. Coinbase outputs become spendable after 100 confirmations, so this primes the wallet.",
                [
                    f"bitcoin-cli -rpcwallet={active_wallet} getnewaddress bitscope-demo-mining bech32",
                    f"bitcoin-cli generatetoaddress {mine_blocks} {mining_address}",
                ],
                ["getnewaddress", "generatetoaddress"],
                ["Regtest", "Mining", "Coinbase maturity"],
                {"getnewaddress": mining_address, "generatetoaddress": mined},
            )
        )

        balance = self._as_dict(self.rpc_client.call("getbalances", [], wallet_name=active_wallet))
        steps.append(
            self._step(
                "balance",
                "Inspect wallet balance",
                "completed",
                "The wallet now has mature trusted balance if the mined coinbase rewards reached maturity.",
                [f"bitcoin-cli -rpcwallet={active_wallet} getbalances"],
                ["getbalances"],
                ["Wallet balance", "Trusted balance", "Immature coinbase"],
                {"getbalances": balance},
            )
        )

        recipient_address = self._string_call("getnewaddress", ["bitscope-demo-recipient", "bech32"], active_wallet)
        txid = self._string_call("sendtoaddress", [recipient_address, amount], active_wallet)
        confirmation_mine_address = self._string_call("getnewaddress", ["bitscope-demo-confirmation", "bech32"], active_wallet)
        confirmation_mined = self.rpc_client.call("generatetoaddress", [1, confirmation_mine_address])
        confirmation_hashes = [item for item in confirmation_mined if isinstance(item, str)] if isinstance(confirmation_mined, list) else []
        transaction = self.rpc_client.call("gettransaction", [txid, True], wallet_name=active_wallet)
        steps.append(
            self._step(
                "transaction",
                "Send and confirm a regtest transaction",
                "completed",
                f"Sent {amount:.8f} BTC to a fresh address and mined one confirmation block.",
                [
                    f"bitcoin-cli -rpcwallet={active_wallet} getnewaddress bitscope-demo-recipient bech32",
                    f"bitcoin-cli -rpcwallet={active_wallet} sendtoaddress {recipient_address} {amount:.8f}",
                    f"bitcoin-cli -rpcwallet={active_wallet} getnewaddress bitscope-demo-confirmation bech32",
                    f"bitcoin-cli generatetoaddress 1 {confirmation_mine_address}",
                    f"bitcoin-cli -rpcwallet={active_wallet} gettransaction {txid} true",
                ],
                ["getnewaddress", "sendtoaddress", "generatetoaddress", "gettransaction"],
                ["Transaction", "UTXO", "Confirmation", "Wallet send"],
                {
                    "recipient_address": recipient_address,
                    "sendtoaddress": txid,
                    "confirmation_address": confirmation_mine_address,
                    "confirmation_blocks": confirmation_mined,
                    "gettransaction": transaction,
                },
            )
        )

        if include_script_sample:
            decoded = self.rpc_client.call("decodescript", [SCRIPT_SAMPLE_HEX])
            steps.append(
                self._step(
                    "script",
                    "Decode a standard script",
                    "completed",
                    "Decoded a P2PKH script sample so the learner sees that addresses are wrappers around script conditions.",
                    [f"bitcoin-cli decodescript {SCRIPT_SAMPLE_HEX}"],
                    ["decodescript"],
                    ["Bitcoin Script", "P2PKH", "scriptPubKey"],
                    {"script_hex": SCRIPT_SAMPLE_HEX, "decodescript": decoded},
                )
            )

        cli_commands = [command for step in steps for command in step["cli_commands"] if isinstance(command, str)]
        rpc_methods = sorted({method for step in steps for method in step["rpc_methods"] if isinstance(method, str)})
        concepts = sorted({concept for step in steps for concept in step["concepts"] if isinstance(concept, str)})
        export_markdown = self._export_markdown(session_id, active_wallet, steps)

        return {
            "session_id": session_id,
            "wallet_name": active_wallet,
            "mining_address": mining_address,
            "recipient_address": recipient_address,
            "txid": txid,
            "block_hashes": block_hashes,
            "confirmation_block_hashes": confirmation_hashes,
            "cli_commands": cli_commands,
            "rpc_methods": rpc_methods,
            "concepts": concepts,
            "steps": steps,
            "export_markdown": export_markdown,
            "explanation": (
                "Demo Mode runs a compact regtest story: wallet setup, coinbase maturity, balance inspection, "
                "a confirmed wallet transaction, and script decoding. It returns a shareable command log for teaching."
            ),
        }

    def _ensure_wallet(self, wallet_name: str) -> dict[str, JsonValue]:
        raw: dict[str, JsonValue] = {}
        loaded = self._str_list(self.rpc_client.call("listwallets"))
        raw["listwallets_before"] = loaded
        if wallet_name in loaded:
            return raw

        try:
            raw["createwallet"] = self.rpc_client.call("createwallet", [wallet_name])
            return raw
        except RpcError as exc:
            message = str(exc.details.get("rpc_message", "")).lower()
            if "already exists" not in message:
                raise
            raw["createwallet"] = {"wallet_exists": True, "rpc_message": exc.details.get("rpc_message")}

        try:
            raw["loadwallet"] = self.rpc_client.call("loadwallet", [wallet_name])
        except RpcError as exc:
            message = str(exc.details.get("rpc_message", "")).lower()
            if "already loaded" not in message:
                raise
            raw["loadwallet"] = {"already_loaded": True, "rpc_message": exc.details.get("rpc_message")}
        return raw

    def _string_call(self, method: str, params: list[object], wallet_name: str | None = None) -> str:
        value = self.rpc_client.call(method, params, wallet_name=wallet_name)
        if not isinstance(value, str):
            raise BitScopeError(
                code="BITCOIN_CORE_INVALID_RESPONSE",
                message=f"Bitcoin Core did not return a string for {method}.",
                status_code=502,
                details={"rpc_method": method},
            )
        return value

    def _require_regtest(self) -> None:
        if self.rpc_client.settings.bitcoin_network != "regtest":
            raise BitScopeError(
                code="REGTEST_ONLY",
                message="Demo Mode is only available when BITCOIN_NETWORK is set to regtest.",
                status_code=400,
                details={"network": self.rpc_client.settings.bitcoin_network},
            )

    @staticmethod
    def _wallet_name(value: str) -> str:
        clean = value.strip()
        if not clean:
            raise BitScopeError(code="INVALID_WALLET_NAME", message="Provide a demo wallet name.", status_code=400)
        return clean

    @staticmethod
    def _step(
        step_id: str,
        title: str,
        status: str,
        summary: str,
        cli_commands: list[str],
        rpc_methods: list[str],
        concepts: list[str],
        raw: dict[str, JsonValue],
    ) -> dict[str, object]:
        return {
            "id": step_id,
            "title": title,
            "status": status,
            "summary": summary,
            "cli_commands": cli_commands,
            "rpc_methods": rpc_methods,
            "concepts": concepts,
            "raw": raw,
        }

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _str_list(value: JsonValue) -> list[str]:
        return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []

    @staticmethod
    def _export_markdown(session_id: str, wallet_name: str, steps: list[dict[str, object]]) -> str:
        lines = [
            f"# BitScope Demo Session {session_id}",
            "",
            f"Wallet: `{wallet_name}`",
            "",
            "## Steps",
        ]
        for index, step in enumerate(steps, start=1):
            lines.extend(["", f"### {index}. {step['title']}", "", str(step["summary"]), "", "```bash"])
            lines.extend(command for command in step["cli_commands"] if isinstance(command, str))
            lines.append("```")
        return "\n".join(lines)
