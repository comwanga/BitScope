from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LabAction(BaseModel):
    sequence: int = Field(ge=1)
    kind: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    details: dict[str, object] = Field(default_factory=dict)


class LabSession(BaseModel):
    session_id: str
    wallet_name: str
    owned_wallets: list[str]
    wallet_generation: int = Field(ge=0)
    runtime_chain: Literal["regtest"]
    starting_height: int = Field(ge=0)
    created_addresses: list[str] = Field(default_factory=list)
    transaction_ids: list[str] = Field(default_factory=list)
    block_hashes: list[str] = Field(default_factory=list)
    expected_utxos: list[dict[str, object]] = Field(default_factory=list)
    actions: list[LabAction] = Field(default_factory=list)
    lesson_progress: dict[str, str] = Field(default_factory=dict)
    status: Literal["creating", "active", "resetting", "cleaned", "cleanup_failed"]
    cleanup_status: str | None = None
    created_at: datetime
    updated_at: datetime


class LabCreateRequest(BaseModel):
    lesson_id: str | None = Field(default=None, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class LabResetResponse(BaseModel):
    session: LabSession
    previous_wallet: str


class LabDeleteResponse(BaseModel):
    session_id: str
    cleanup_status: str
    unloaded_wallets: list[str]
