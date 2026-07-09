from typing import Any

from pydantic import BaseModel


class MerkleNode(BaseModel):
    hash: str
    duplicated: bool = False


class MerkleLayer(BaseModel):
    level: int
    label: str
    nodes: list[MerkleNode]


class BlockResponse(BaseModel):
    query: str
    query_type: str
    height: int | None = None
    hash: str
    confirmations: int | None = None
    timestamp: int | None = None
    previous_block_hash: str | None = None
    next_block_hash: str | None = None
    merkle_root: str | None = None
    version: int | None = None
    version_hex: str | None = None
    difficulty: float | None = None
    nonce: int | None = None
    bits: str | None = None
    size: int | None = None
    stripped_size: int | None = None
    weight: int | None = None
    transaction_count: int
    transaction_ids: list[str]
    merkle_layers: list[MerkleLayer]
    merkle_verified: bool | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
