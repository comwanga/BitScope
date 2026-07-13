from typing import Any

from pydantic import BaseModel, Field


class MineRequest(BaseModel):
    blocks: int = Field(default=1, ge=1, le=500)
    wallet_name: str | None = Field(default=None, max_length=128)
    address: str | None = Field(default=None, max_length=128)


class FaucetRequest(BaseModel):
    wallet_name: str = Field(min_length=1, max_length=128)
    address: str = Field(min_length=1, max_length=128)
    amount_btc: float = Field(default=1.0, gt=0)
    mine_confirmation: bool = True


class RegtestMineResponse(BaseModel):
    blocks: int
    address: str
    wallet_name: str | None = None
    block_hashes: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class RegtestFaucetResponse(BaseModel):
    txid: str
    wallet_name: str
    address: str
    amount_btc: float
    confirmation_block_hashes: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
