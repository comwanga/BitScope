from typing import Any

from pydantic import BaseModel, Field


class TaprootInspectRequest(BaseModel):
    address: str | None = Field(default=None, max_length=128)
    script_hex: str | None = Field(default=None, max_length=1_000_000)


class TaprootInspectResponse(BaseModel):
    address: str | None = None
    script_hex: str | None = None
    is_taproot: bool
    witness_version: int | None = None
    witness_program: str | None = None
    output_key: str | None = None
    script_type: str | None = None
    asm: str | None = None
    notes: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
