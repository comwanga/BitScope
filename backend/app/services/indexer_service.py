from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.errors import RpcError
from app.rpc.types import JsonValue


INDEX_LIMITATION = (
    "This is a bounded local scan over blocks your Bitcoin Core node can serve. It finds outputs paying the address "
    "inside the selected range, but it is not a persistent full address index and does not prove current balance."
)


class IndexerService:
    MAX_BLOCKS = 50

    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def scan_address_outputs(self, address: str, start_height: int, end_height: int) -> dict[str, object]:
        clean_address = address.strip()
        if not clean_address:
            raise BitScopeError(
                code="INVALID_ADDRESS",
                message="Provide an address to scan for.",
                status_code=400,
            )
        if end_height < start_height:
            raise BitScopeError(
                code="INVALID_INDEX_RANGE",
                message="End height must be greater than or equal to start height.",
                status_code=400,
                details={"start_height": start_height, "end_height": end_height},
            )
        block_count = end_height - start_height + 1
        if block_count > self.MAX_BLOCKS:
            raise BitScopeError(
                code="INDEX_RANGE_TOO_LARGE",
                message=f"Scan at most {self.MAX_BLOCKS} blocks at a time.",
                status_code=400,
                details={"requested_blocks": block_count, "max_blocks": self.MAX_BLOCKS},
            )

        validation = self._as_dict(self.rpc_client.call("validateaddress", [clean_address]))
        if validation.get("isvalid") is not True:
            raise BitScopeError(
                code="INVALID_ADDRESS",
                message="Bitcoin Core says this address is invalid for the current network.",
                status_code=400,
                details={"address": clean_address},
            )

        outputs: list[dict[str, object]] = []
        scanned_hashes: list[str] = []
        raw_blocks: dict[str, object] = {}

        for height in range(start_height, end_height + 1):
            try:
                block_hash = self.rpc_client.call("getblockhash", [height])
                if not isinstance(block_hash, str):
                    continue
                block = self._as_dict(self.rpc_client.call("getblock", [block_hash, 2]))
            except RpcError as exc:
                if exc.code in {"BITCOIN_CORE_NOT_FOUND", "INVALID_RPC_PARAMETER"}:
                    raise BitScopeError(
                        code="BLOCK_NOT_FOUND",
                        message="Bitcoin Core could not retrieve a block in that scan range.",
                        status_code=404,
                        details={"height": height},
                    ) from exc
                raise

            scanned_hashes.append(block_hash)
            raw_blocks[str(height)] = {"hash": block_hash, "tx_count": len(block.get("tx", [])) if isinstance(block.get("tx"), list) else 0}
            outputs.extend(self._matching_outputs(clean_address, height, block_hash, block))

        return {
            "address": clean_address,
            "start_height": start_height,
            "end_height": end_height,
            "blocks_scanned": len(scanned_hashes),
            "outputs": outputs,
            "total_received_btc_in_range": sum(output["value_btc"] for output in outputs if isinstance(output.get("value_btc"), float)),
            "limitation": INDEX_LIMITATION,
            "cli_commands": [
                f"bitcoin-cli validateaddress {clean_address}",
                f"bitcoin-cli getblockhash <height:{start_height}-{end_height}>",
                "bitcoin-cli getblock <blockhash> 2",
            ],
            "rpc_methods": ["validateaddress", "getblockhash", "getblock"],
            "concepts": ["Local indexing", "Address history limitation", "scriptPubKey", "UTXO", "Block scan"],
            "explanation": (
                "BitScope walks a small height range, asks Bitcoin Core for decoded block transactions, and records outputs whose "
                "scriptPubKey address matches the target. This demonstrates how a local index starts without using hosted APIs."
            ),
            "raw": {"validateaddress": validation, "blocks": raw_blocks},
        }

    def _matching_outputs(self, address: str, height: int, block_hash: str, block: dict[str, object]) -> list[dict[str, object]]:
        transactions = block.get("tx")
        if not isinstance(transactions, list):
            return []

        matches: list[dict[str, object]] = []
        for transaction in transactions:
            if not isinstance(transaction, dict):
                continue
            txid = self._optional_str(transaction.get("txid"))
            outputs = transaction.get("vout")
            if not txid or not isinstance(outputs, list):
                continue
            for output in outputs:
                if not isinstance(output, dict):
                    continue
                script_pub_key = self._as_dict(output.get("scriptPubKey"))
                output_address = self._address_from_script(script_pub_key)
                if output_address != address:
                    continue
                value = output.get("value")
                matches.append(
                    {
                        "txid": txid,
                        "vout": self._optional_int(output.get("n")) or 0,
                        "value_btc": float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0,
                        "block_height": height,
                        "block_hash": block_hash,
                        "script_type": self._optional_str(script_pub_key.get("type")),
                        "script_pub_key_hex": self._optional_str(script_pub_key.get("hex")),
                    }
                )
        return matches

    @staticmethod
    def _address_from_script(script_pub_key: dict[str, object]) -> str | None:
        address = script_pub_key.get("address")
        if isinstance(address, str):
            return address
        addresses = script_pub_key.get("addresses")
        if isinstance(addresses, list) and addresses and isinstance(addresses[0], str):
            return addresses[0]
        return None

    @staticmethod
    def _as_dict(value: object) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_str(value: object) -> str | None:
        return value if isinstance(value, str) and value else None
