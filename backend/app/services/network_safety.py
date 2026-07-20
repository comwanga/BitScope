from dataclasses import dataclass
from typing import Literal, cast

from app.config import BitcoinNetwork
from app.errors import BitScopeError
from app.rpc.capabilities import RpcTransport


RuntimeChain = Literal["main", "test", "signet", "regtest"]

CONFIG_TO_RUNTIME_CHAIN: dict[BitcoinNetwork, RuntimeChain] = {
    "mainnet": "main",
    "testnet": "test",
    "signet": "signet",
    "regtest": "regtest",
}

RUNTIME_TO_CONFIG_NETWORK: dict[RuntimeChain, BitcoinNetwork] = {
    runtime: configured for configured, runtime in CONFIG_TO_RUNTIME_CHAIN.items()
}


@dataclass(frozen=True)
class ChainContext:
    configured_network: BitcoinNetwork
    runtime_chain: RuntimeChain

    @property
    def runtime_network(self) -> BitcoinNetwork:
        return RUNTIME_TO_CONFIG_NETWORK[self.runtime_chain]

    @property
    def matches_configuration(self) -> bool:
        return CONFIG_TO_RUNTIME_CHAIN[self.configured_network] == self.runtime_chain


class NetworkSafetyGuard:
    """Fail-closed safety checks based on Bitcoin Core's live chain identity."""

    def __init__(self, rpc_client: RpcTransport) -> None:
        self.rpc_client = rpc_client

    def get_context(self) -> ChainContext:
        info = self.rpc_client.call("getblockchaininfo")
        if not isinstance(info, dict):
            raise self._invalid_chain_response()

        chain = info.get("chain")
        if chain not in RUNTIME_TO_CONFIG_NETWORK:
            raise self._invalid_chain_response(chain)

        configured = self.rpc_client.settings.bitcoin_network
        context = ChainContext(
            configured_network=configured,
            runtime_chain=cast(RuntimeChain, chain),
        )
        if not context.matches_configuration:
            raise BitScopeError(
                code="BITCOIN_NETWORK_MISMATCH",
                message="BitScope configuration does not match the network reported by Bitcoin Core.",
                status_code=409,
                details={
                    "configured_network": context.configured_network,
                    "runtime_network": context.runtime_network,
                    "runtime_chain": context.runtime_chain,
                },
            )
        return context

    def require_regtest(self) -> ChainContext:
        context = self.get_context()
        if context.runtime_chain != "regtest":
            raise BitScopeError(
                code="REGTEST_ONLY",
                message="This action is only available when the connected Bitcoin Core node is running regtest.",
                status_code=400,
                details={
                    "configured_network": context.configured_network,
                    "runtime_network": context.runtime_network,
                    "runtime_chain": context.runtime_chain,
                },
            )
        return context

    def require_read_only_network(self) -> ChainContext:
        return self.get_context()

    @staticmethod
    def _invalid_chain_response(chain: object = None) -> BitScopeError:
        details = {"rpc_method": "getblockchaininfo"}
        if isinstance(chain, str):
            details["runtime_chain"] = chain
        return BitScopeError(
            code="BITCOIN_CHAIN_UNVERIFIED",
            message="BitScope could not verify the network reported by Bitcoin Core.",
            status_code=502,
            details=details,
        )
