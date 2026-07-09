from typing import Any

from pydantic import BaseModel, Field


class DescriptorAnalyzeRequest(BaseModel):
    descriptor: str = Field(min_length=1)
    derive_start: int | None = Field(default=None, ge=0, le=1_000_000)
    derive_end: int | None = Field(default=None, ge=0, le=1_000_000)


class DescriptorAnalyzeResponse(BaseModel):
    descriptor: str
    normalized_descriptor: str | None = None
    checksum: str | None = None
    is_range: bool | None = None
    is_solvable: bool | None = None
    has_private_keys: bool | None = None
    derived_addresses: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class WalletDescriptorInfo(BaseModel):
    descriptor: str
    active: bool | None = None
    internal: bool | None = None
    range: list[int] | None = None
    next_index: int | None = None
    timestamp: int | str | None = None


class WalletDescriptorsResponse(BaseModel):
    wallet_name: str
    descriptors: list[WalletDescriptorInfo]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
