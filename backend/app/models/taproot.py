from typing import Any

from pydantic import BaseModel


class TaprootInspectRequest(BaseModel):
    address: str | None = None
    script_hex: str | None = None


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
