from typing import Any

from pydantic import BaseModel


class NodeStatusResponse(BaseModel):
    chain: str | None = None
    blocks: int | None = None
    headers: int | None = None
    best_block_hash: str | None = None
    verification_progress: float | None = None
    initial_block_download: bool | None = None
    difficulty: float | None = None
    pruned: bool | None = None
    size_on_disk: int | None = None
    network_active: bool | None = None
    peer_count: int | None = None
    mempool_tx_count: int | None = None
    mempool_usage: int | None = None
    mempool_min_fee: float | None = None
    incremental_relay_fee: float | None = None
    relay_fee: float | None = None
    warnings: list[str] = []
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
