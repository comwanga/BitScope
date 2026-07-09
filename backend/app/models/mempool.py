from typing import Any

from pydantic import BaseModel


class MempoolSummaryResponse(BaseModel):
    transaction_count: int | None = None
    virtual_size: int | None = None
    total_fee_btc: float | None = None
    mempool_min_fee: float | None = None
    incremental_relay_fee: float | None = None
    memory_usage: int | None = None
    max_mempool: int | None = None
    sample_transaction_ids: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class MempoolEntryResponse(BaseModel):
    txid: str
    vsize: int | None = None
    weight: int | None = None
    time: int | None = None
    height: int | None = None
    descendant_count: int | None = None
    descendant_size: int | None = None
    ancestor_count: int | None = None
    ancestor_size: int | None = None
    fee_btc: float | None = None
    modified_fee_btc: float | None = None
    depends: list[str]
    spent_by: list[str]
    bip125_replaceable: bool | None = None
    unbroadcast: bool | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
