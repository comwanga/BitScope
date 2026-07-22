from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue, field_validator, model_validator

from app.models.evidence import SafeBitcoinCliCommand
from app.models.scenario import ArtifactKey, Identifier, StrictScenarioModel


class LifecycleEventType(StrEnum):
    WALLET_PREPARED = "wallet_prepared"
    UTXO_SELECTED = "utxo_selected"
    RAW_TRANSACTION_CREATED = "raw_transaction_created"
    TRANSACTION_FUNDED = "transaction_funded"
    PSBT_CREATED = "psbt_created"
    PSBT_PARTIALLY_SIGNED = "psbt_partially_signed"
    PSBT_COMPLETED = "psbt_completed"
    TRANSACTION_FINALIZED = "transaction_finalized"
    MEMPOOL_PREFLIGHT_COMPLETED = "mempool_preflight_completed"
    TRANSACTION_BROADCAST = "transaction_broadcast"
    TRANSACTION_ENTERED_MEMPOOL = "transaction_entered_mempool"
    TRANSACTION_REPLACED = "transaction_replaced"
    CHILD_TRANSACTION_CREATED = "child_transaction_created"
    TRANSACTION_CONFIRMED = "transaction_confirmed"
    TIMELOCK_MATURED = "timelock_matured"
    SCENARIO_CLEANED_UP = "scenario_cleaned_up"


class TransactionLifecycleState(StrEnum):
    WALLET_READY = "wallet_ready"
    INPUT_SELECTED = "input_selected"
    DRAFT = "draft"
    FUNDED = "funded"
    PARTIALLY_SIGNED = "partially_signed"
    SIGNED = "signed"
    FINALIZED = "finalized"
    PREFLIGHTED = "preflighted"
    BROADCAST = "broadcast"
    IN_MEMPOOL = "in_mempool"
    REPLACED = "replaced"
    CHILD = "child"
    CONFIRMED = "confirmed"
    TIMELOCK_MATURE = "timelock_mature"
    CLEANED = "cleaned"


class MempoolRelationshipType(StrEnum):
    REPLACES = "replaces"
    REPLACED_BY = "replaced_by"
    CHILD_OF = "child_of"
    PARENT_OF = "parent_of"
    CONFLICTS_WITH = "conflicts_with"


class MempoolRelationship(StrictScenarioModel):
    relationship_type: MempoolRelationshipType
    related_txid: str
    explanation: str = Field(min_length=1, max_length=1_000)

    @field_validator("related_txid")
    @classmethod
    def related_txid_is_hex(cls, value: str) -> str:
        return _validate_txid(value)


class TransactionLifecycleEvent(StrictScenarioModel):
    schema_version: Literal[1] = 1
    event_id: ArtifactKey
    ordinal: int = Field(ge=1, le=10_000)
    event_type: LifecycleEventType
    timestamp: datetime
    step_id: Identifier
    track_id: ArtifactKey
    transaction_state: TransactionLifecycleState
    transaction_id: str | None = None
    transaction_hex_ref: ArtifactKey | None = None
    psbt_ref: ArtifactKey | None = None
    fee_btc: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=8)
    fee_rate_sat_vb: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=3)
    locktime: int | None = Field(default=None, ge=0, le=0xFFFFFFFF)
    sequence_values: list[int] = Field(default_factory=list, max_length=1_000)
    relationship: MempoolRelationship | None = None
    block_height: int | None = Field(default=None, ge=0)
    explanation: str = Field(min_length=1, max_length=2_000)
    rpc_method: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9]+$")
    cli_command: SafeBitcoinCliCommand
    evidence_id: ArtifactKey
    raw_safe_core_result: JsonValue = None

    @field_validator("transaction_id")
    @classmethod
    def transaction_id_is_hex(cls, value: str | None) -> str | None:
        return _validate_txid(value) if value is not None else None

    @field_validator("sequence_values")
    @classmethod
    def sequences_are_uint32(cls, value: list[int]) -> list[int]:
        if any(sequence < 0 or sequence > 0xFFFFFFFF for sequence in value):
            raise ValueError("Lifecycle sequence values must be unsigned 32-bit integers.")
        return value

    @model_validator(mode="after")
    def relationships_have_a_transaction(self) -> "TransactionLifecycleEvent":
        if self.relationship is not None and self.transaction_id is None:
            raise ValueError("Mempool relationship events require their own transaction id.")
        return self


class TransactionLifecycleTimeline(StrictScenarioModel):
    schema_version: Literal[1] = 1
    run_id: UUID
    scenario_id: Identifier
    scenario_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    lab_session_id: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    generated_at: datetime
    events: list[TransactionLifecycleEvent] = Field(default_factory=list, max_length=10_000)

    @model_validator(mode="after")
    def event_order_and_identity_are_coherent(self) -> "TransactionLifecycleTimeline":
        ids = [event.event_id for event in self.events]
        ordinals = [event.ordinal for event in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("Lifecycle event identifiers must be unique.")
        if len(ordinals) != len(set(ordinals)) or ordinals != sorted(ordinals):
            raise ValueError("Lifecycle event ordinals must be unique and ordered.")
        return self


def _validate_txid(value: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdefABCDEF" for character in value):
        raise ValueError("Lifecycle transaction identifiers must be 64 hexadecimal characters.")
    return value.lower()
