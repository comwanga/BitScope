from typing import Protocol

from app.config import Settings
from app.rpc.errors import RpcError
from app.rpc.types import JsonValue, RpcParams


FORBIDDEN_RPC_METHODS = frozenset(
    {
        "backupwallet",
        "dumpprivkey",
        "dumpwallet",
        "encryptwallet",
        "gethdkeys",
        "importprivkey",
        "importwallet",
        "sethdseed",
        "signmessagewithprivkey",
        "stop",
        "walletlock",
        "walletpassphrase",
        "walletpassphrasechange",
    }
)

READ_ONLY_METHODS = frozenset(
    {
        "decodepsbt",
        "decoderawtransaction",
        "decodescript",
        "deriveaddresses",
        "estimatesmartfee",
        "getbestblockhash",
        "getblock",
        "getblockchaininfo",
        "getblockcount",
        "getblockhash",
        "getblockheader",
        "getchaintips",
        "getchaintxstats",
        "getconnectioncount",
        "getdeploymentinfo",
        "getdescriptorinfo",
        "getdifficulty",
        "getmemoryinfo",
        "getmempoolentry",
        "getmempoolinfo",
        "getnettotals",
        "getnetworkinfo",
        "getpeerinfo",
        "getrawmempool",
        "getrawtransaction",
        "gettxout",
        "gettxoutsetinfo",
        "listwalletdir",
        "listwallets",
        "testmempoolaccept",
        "uptime",
        "validateaddress",
    }
)

WALLET_READ_METHODS = READ_ONLY_METHODS | {
    "getaddressinfo",
    "getbalances",
    "getreceivedbyaddress",
    "gettransaction",
    "getwalletinfo",
    "listdescriptors",
    "listtransactions",
    "listunspent",
}

REGTEST_MUTATION_METHODS = WALLET_READ_METHODS | {
    "addmultisigaddress",
    "bumpfee",
    "createmultisig",
    "createrawtransaction",
    "createwallet",
    "finalizepsbt",
    "fundrawtransaction",
    "generatetoaddress",
    "getnewaddress",
    "loadwallet",
    "sendrawtransaction",
    "sendtoaddress",
    "signrawtransactionwithwallet",
    "walletcreatefundedpsbt",
    "walletprocesspsbt",
}


class RpcTransport(Protocol):
    settings: Settings

    def call(self, method: str, params: RpcParams = None, wallet_name: str | None = None) -> JsonValue: ...


class CapabilityRpcClient:
    capability_name = "base"
    allowed_methods: frozenset[str] = frozenset()

    def __init__(self, transport: RpcTransport) -> None:
        self.transport = transport

    @property
    def settings(self) -> Settings:
        return self.transport.settings

    def call(self, method: str, params: RpcParams = None, wallet_name: str | None = None) -> JsonValue:
        if method in FORBIDDEN_RPC_METHODS:
            raise forbidden_rpc_error(method)
        if method not in self.allowed_methods:
            raise RpcError(
                code="RPC_CAPABILITY_VIOLATION",
                message="This BitScope service is not permitted to call the requested Bitcoin Core RPC method.",
                status_code=403,
                details={"rpc_method": method, "capability": self.capability_name},
            )
        if wallet_name is None and params is None:
            return self.transport.call(method)
        if wallet_name is None:
            return self.transport.call(method, params)
        return self.transport.call(method, params, wallet_name=wallet_name)

    def get_blockchain_info(self) -> JsonValue:
        helper = getattr(self.transport, "get_blockchain_info", None)
        return helper() if callable(helper) else self.call("getblockchaininfo")

    def get_network_info(self) -> JsonValue:
        helper = getattr(self.transport, "get_network_info", None)
        return helper() if callable(helper) else self.call("getnetworkinfo")

    def get_mempool_info(self) -> JsonValue:
        helper = getattr(self.transport, "get_mempool_info", None)
        return helper() if callable(helper) else self.call("getmempoolinfo")

    def get_block_count(self) -> JsonValue:
        helper = getattr(self.transport, "get_block_count", None)
        return helper() if callable(helper) else self.call("getblockcount")

    def get_best_block_hash(self) -> JsonValue:
        helper = getattr(self.transport, "get_best_block_hash", None)
        return helper() if callable(helper) else self.call("getbestblockhash")


class ReadOnlyRpcClient(CapabilityRpcClient):
    capability_name = "read_only"
    allowed_methods = READ_ONLY_METHODS


class WalletReadRpcClient(CapabilityRpcClient):
    capability_name = "wallet_read"
    allowed_methods = frozenset(WALLET_READ_METHODS)


class RegtestMutationRpcClient(CapabilityRpcClient):
    capability_name = "regtest_mutation"
    allowed_methods = frozenset(REGTEST_MUTATION_METHODS)


def forbidden_rpc_error(method: str) -> RpcError:
    return RpcError(
        code="RPC_METHOD_FORBIDDEN",
        message="BitScope permanently forbids this Bitcoin Core RPC method.",
        status_code=403,
        details={"rpc_method": method},
    )
