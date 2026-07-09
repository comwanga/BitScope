from typing import Any

from pydantic import BaseModel


class ZmqStatusResponse(BaseModel):
    configured: bool
    rawblock_endpoint: str | None = None
    rawtx_endpoint: str | None = None
    sse_endpoint: str
    zmq_listener_available: bool
    recommended_bitcoin_conf: list[str]
    warnings: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class RpcLanguageExample(BaseModel):
    language: str
    title: str
    description: str
    code: str


class RpcExamplesResponse(BaseModel):
    rpc_url: str
    wallet_rpc_path: str
    examples: list[RpcLanguageExample]
    zmq_conf: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
