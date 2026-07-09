from typing import Any

from pydantic import BaseModel, Field


class LocktimeTransactionRequest(BaseModel):
    wallet_name: str = Field(min_length=1, max_length=128)
    destination_address: str = Field(min_length=1)
    amount_btc: float = Field(gt=0)
    locktime: int = Field(ge=0)
    sequence: int = Field(ge=0, le=4_294_967_295)


class TimelockScriptRequest(BaseModel):
    mode: str
    value: int = Field(ge=0)
    pubkey_hex: str = Field(min_length=1)


class LocktimeTransactionResponse(BaseModel):
    wallet_name: str
    destination_address: str
    amount_btc: float
    locktime: int
    sequence: int
    unsigned_hex: str
    funded_hex: str
    sequence_hex: str
    signed_hex: str | None = None
    complete: bool
    txid: str | None = None
    fee_btc: float | None = None
    change_position: int | None = None
    mempool_accept: Any
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class TimelockScriptResponse(BaseModel):
    mode: str
    value: int
    pubkey_hex: str
    script_hex: str
    asm: str | None = None
    p2sh: str | None = None
    segwit: dict[str, Any] | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
