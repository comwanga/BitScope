from typing import Any, TypeAlias

JsonValue: TypeAlias = dict[str, Any] | list[Any] | str | int | float | bool | None
RpcParams: TypeAlias = list[JsonValue] | dict[str, JsonValue] | None


READ_ONLY_RPC_METHODS = {
    "getbestblockhash",
    "getblock",
    "getblockchaininfo",
    "getblockcount",
    "getblockhash",
    "getblockheader",
    "getchaintips",
    "getchaintxstats",
    "getdeploymentinfo",
    "getdifficulty",
    "getmemoryinfo",
    "getmempoolinfo",
    "getmempoolentry",
    "getnettotals",
    "getnetworkinfo",
    "getpeerinfo",
    "getrawmempool",
    "getrawtransaction",
    "gettxout",
    "gettxoutsetinfo",
    "uptime",
    "validateaddress",
    "decodescript",
    "decodepsbt",
    "estimatesmartfee",
    "listwalletdir",
    "listwallets",
}
