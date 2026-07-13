from typing import Any

from pydantic import BaseModel, Field


class CreatePsbtRequest(BaseModel):
    wallet_name: str = Field(min_length=1, max_length=128)
    recipient_address: str = Field(min_length=1, max_length=128)
    amount_btc: float = Field(gt=0)


class DecodePsbtRequest(BaseModel):
    psbt: str = Field(min_length=1, max_length=1_000_000)


class ProcessPsbtRequest(BaseModel):
    wallet_name: str = Field(min_length=1, max_length=128)
    psbt: str = Field(min_length=1, max_length=1_000_000)
    sign: bool = True


class FinalizePsbtRequest(BaseModel):
    psbt: str = Field(min_length=1, max_length=1_000_000)
    extract: bool = False


class PsbtDecodeResponse(BaseModel):
    psbt: str
    txid: str | None = None
    input_count: int
    output_count: int
    fee_btc: float | None = None
    is_complete: bool | None = None
    next_role: str | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class PsbtCreateResponse(BaseModel):
    wallet_name: str
    psbt: str
    fee_btc: float | None = None
    change_position: int | None = None
    recipient_address: str
    amount_btc: float
    decoded: PsbtDecodeResponse | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class PsbtProcessResponse(BaseModel):
    wallet_name: str
    psbt: str
    complete: bool
    signed: bool
    decoded: PsbtDecodeResponse | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class PsbtFinalizeResponse(BaseModel):
    complete: bool
    psbt: str | None = None
    hex: str | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
