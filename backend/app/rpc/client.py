from itertools import count
from urllib.parse import quote

import httpx

from app.config import Settings, get_settings
from app.rpc.errors import RpcError, map_rpc_error
from app.rpc.types import RpcParams, JsonValue


class BitcoinRpcClient:
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._id_counter = count(1)
        self._client = httpx.Client(
            auth=(self.settings.bitcoin_rpc_user, self.settings.bitcoin_rpc_password),
            timeout=self.settings.bitcoin_rpc_timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BitcoinRpcClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def call(self, method: str, params: RpcParams = None, wallet_name: str | None = None) -> JsonValue:
        payload = {
            "jsonrpc": "1.0",
            "id": next(self._id_counter),
            "method": method,
            "params": [] if params is None else params,
        }

        try:
            response = self._client.post(self.rpc_url(wallet_name), json=payload)
        except httpx.TimeoutException as exc:
            raise RpcError(
                code="BITCOIN_CORE_TIMEOUT",
                message="Bitcoin Core did not answer before the RPC timeout.",
                status_code=504,
                details={"rpc_method": method},
            ) from exc
        except httpx.RequestError as exc:
            raise RpcError(
                code="BITCOIN_CORE_OFFLINE",
                message="Bitcoin Core is not reachable. Start bitcoind and check the RPC host and port.",
                status_code=503,
                details={"rpc_method": method},
            ) from exc

        if response.status_code in {401, 403}:
            raise RpcError(
                code="RPC_AUTH_FAILED",
                message="Bitcoin Core rejected the configured RPC username or password.",
                status_code=401,
                details={"rpc_method": method},
            )

        try:
            body = response.json()
        except ValueError as exc:
            if response.status_code >= 400:
                raise RpcError(
                    code="BITCOIN_CORE_HTTP_ERROR",
                    message="Bitcoin Core returned an unexpected HTTP error.",
                    status_code=502,
                    details={"rpc_method": method, "http_status": response.status_code},
                ) from exc
            raise RpcError(
                code="BITCOIN_CORE_INVALID_RESPONSE",
                message="Bitcoin Core returned a response that was not valid JSON.",
                status_code=502,
                details={"rpc_method": method},
            ) from exc

        if not isinstance(body, dict):
            raise RpcError(
                code="BITCOIN_CORE_INVALID_RESPONSE",
                message="Bitcoin Core returned an unexpected JSON-RPC response shape.",
                status_code=502,
                details={"rpc_method": method},
            )

        if body.get("error") is not None:
            error = body["error"] if isinstance(body["error"], dict) else {"message": str(body["error"])}
            raise map_rpc_error(method, error)

        if response.status_code >= 400:
            raise RpcError(
                code="BITCOIN_CORE_HTTP_ERROR",
                message="Bitcoin Core returned an unexpected HTTP error.",
                status_code=502,
                details={"rpc_method": method, "http_status": response.status_code},
            )

        return body.get("result")

    def rpc_url(self, wallet_name: str | None = None) -> str:
        base_url = self.settings.rpc_url.rstrip("/")
        selected_wallet = wallet_name if wallet_name is not None else self.settings.bitcoin_rpc_wallet
        if not selected_wallet:
            return base_url

        return f"{base_url}/wallet/{quote(selected_wallet, safe='')}"

    def get_blockchain_info(self) -> JsonValue:
        return self.call("getblockchaininfo")

    def get_network_info(self) -> JsonValue:
        return self.call("getnetworkinfo")

    def get_mempool_info(self) -> JsonValue:
        return self.call("getmempoolinfo")

    def get_block_count(self) -> JsonValue:
        return self.call("getblockcount")

    def get_best_block_hash(self) -> JsonValue:
        return self.call("getbestblockhash")
