from typing import Any

from pydantic import BaseModel, Field


class DecodeScriptRequest(BaseModel):
    script_hex: str = Field(min_length=1)


class ScriptTemplateRequest(BaseModel):
    template: str
    pubkey_hex: str | None = None
    fallback_pubkey_hex: str | None = None
    pubkey_hash_hex: str | None = None
    hash_hex: str | None = None


class ScriptTestRequest(BaseModel):
    transaction_hex: str = Field(min_length=1)


class OpReturnTransactionRequest(BaseModel):
    wallet_name: str = Field(min_length=1)
    data: str = Field(min_length=1)
    data_format: str = "text"
    destination_address: str | None = None
    amount_btc: float | None = None
    broadcast: bool = False
    mine_confirmation: bool = False


class ScriptOpcode(BaseModel):
    offset: int
    opcode: str
    data_hex: str | None = None
    data_length: int | None = None
    description: str


class DecodeScriptResponse(BaseModel):
    script_hex: str
    asm: str | None = None
    script_type: str | None = None
    req_sigs: int | None = None
    addresses: list[str]
    p2sh: str | None = None
    segwit: dict[str, Any] | None = None
    opcodes: list[ScriptOpcode]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class ScriptTemplateResponse(BaseModel):
    template: str
    script_hex: str
    asm: str | None = None
    script_type: str | None = None
    p2sh: str | None = None
    segwit: dict[str, Any] | None = None
    opcodes: list[ScriptOpcode]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class ScriptTestResponse(BaseModel):
    transaction_hex: str
    accepted: bool | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class OpReturnTransactionResponse(BaseModel):
    wallet_name: str
    data_format: str
    data_hex: str
    data_utf8: str | None = None
    data_bytes: int
    op_return_script_hex: str
    destination_address: str | None = None
    amount_btc: float | None = None
    unsigned_hex: str
    funded_hex: str
    signed_hex: str | None = None
    complete: bool
    txid: str | None = None
    fee_btc: float | None = None
    change_position: int | None = None
    mempool_accept: Any
    broadcast: bool
    confirmation_block_hashes: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
