from typing import Any

from pydantic import BaseModel


class FeeEstimate(BaseModel):
    target_blocks: int
    btc_per_kvb: float | None = None
    sats_per_vbyte: float | None = None
    available: bool
    errors: list[str]


class FeeEstimateResponse(BaseModel):
    estimates: list[FeeEstimate]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
