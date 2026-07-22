from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from app.models.scenario import Identifier, StrictScenarioModel


CompressedPublicKey = Annotated[
    str,
    Field(
        min_length=66,
        max_length=66,
        pattern=r"^(?:02|03)[0-9a-fA-F]{64}$",
    ),
]
RelativeBlockDelay = Annotated[int, Field(ge=1, le=65_535)]


class TreasuryParticipantRole(StrEnum):
    OPERATOR = "operator"
    RECOVERY = "recovery"
    EMERGENCY = "emergency"


class TreasurySpendPath(StrEnum):
    IMMEDIATE = "immediate"
    RECOVERY = "recovery"
    EMERGENCY = "emergency"


class TreasuryParticipant(StrictScenarioModel):
    """One public signer identity backed by an isolated Bitcoin Core wallet."""

    participant_id: Identifier
    role: TreasuryParticipantRole
    position: int = Field(ge=1, le=3)
    wallet_name: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    public_key: CompressedPublicKey

    @field_validator("public_key")
    @classmethod
    def public_key_is_canonical_lowercase(cls, value: str) -> str:
        return value.lower()


class TreasuryParticipantGroup(StrictScenarioModel):
    """The proven fixed-size 2-of-3 threshold for one treasury branch."""

    role: TreasuryParticipantRole
    required_signatures: Literal[2] = 2
    participants: list[TreasuryParticipant] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def group_is_coherent(self) -> TreasuryParticipantGroup:
        if any(participant.role != self.role for participant in self.participants):
            raise ValueError("Every treasury participant must match the role of its signer group.")
        if {participant.position for participant in self.participants} != {1, 2, 3}:
            raise ValueError("Treasury signer positions must contain each value from 1 through 3 exactly once.")
        if len({participant.participant_id for participant in self.participants}) != 3:
            raise ValueError("Treasury participant identifiers must be unique within a signer group.")
        if len({participant.wallet_name for participant in self.participants}) != 3:
            raise ValueError("Treasury participant wallets must be unique within a signer group.")
        if len({participant.public_key for participant in self.participants}) != 3:
            raise ValueError("Treasury participant public keys must be unique within a signer group.")
        return self

    def ordered_participants(self) -> tuple[TreasuryParticipant, ...]:
        return tuple(sorted(self.participants, key=lambda participant: participant.position))


class TreasuryPolicy(StrictScenarioModel):
    """Public inputs for the reviewed Community Treasury Recovery policy."""

    schema_version: Literal[1] = 1
    policy_id: Identifier = "community-treasury-recovery"
    policy_version: Literal["1.0.0"] = "1.0.0"
    script_type: Literal["p2wsh"] = "p2wsh"
    delay_unit: Literal["blocks"] = "blocks"
    recovery_delay_blocks: RelativeBlockDelay
    emergency_delay_blocks: RelativeBlockDelay
    operators: TreasuryParticipantGroup
    recovery: TreasuryParticipantGroup
    emergency: TreasuryParticipantGroup

    @model_validator(mode="after")
    def policy_is_coherent(self) -> TreasuryPolicy:
        expected_roles = (
            (self.operators, TreasuryParticipantRole.OPERATOR),
            (self.recovery, TreasuryParticipantRole.RECOVERY),
            (self.emergency, TreasuryParticipantRole.EMERGENCY),
        )
        if any(group.role != expected for group, expected in expected_roles):
            raise ValueError("Treasury signer groups must occupy their matching policy roles.")
        if self.emergency_delay_blocks <= self.recovery_delay_blocks:
            raise ValueError("The emergency delay must be greater than the recovery delay.")

        participants = [
            participant
            for group, _ in expected_roles
            for participant in group.participants
        ]
        if len({participant.participant_id for participant in participants}) != len(participants):
            raise ValueError("Treasury participant identifiers must be unique across the policy.")
        if len({participant.wallet_name for participant in participants}) != len(participants):
            raise ValueError("Treasury participant wallets must be unique across the policy.")
        if len({participant.public_key for participant in participants}) != len(participants):
            raise ValueError("Treasury participant public keys must be unique across the policy.")
        return self


class TreasuryPolicyBranch(StrictScenarioModel):
    path: TreasurySpendPath
    label: str = Field(min_length=1, max_length=120)
    required_signatures: Literal[2] = 2
    participant_ids: list[Identifier] = Field(min_length=3, max_length=3)
    relative_delay_blocks: RelativeBlockDelay | None = None


class TreasuryPolicyDecisionTree(StrictScenarioModel):
    root_label: Literal["Treasury P2WSH output"] = "Treasury P2WSH output"
    branches: list[TreasuryPolicyBranch] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def tree_contains_each_proven_path(self) -> TreasuryPolicyDecisionTree:
        if [branch.path for branch in self.branches] != [
            TreasurySpendPath.IMMEDIATE,
            TreasurySpendPath.RECOVERY,
            TreasurySpendPath.EMERGENCY,
        ]:
            raise ValueError("The treasury decision tree must contain the proven paths in canonical order.")
        if self.branches[0].relative_delay_blocks is not None:
            raise ValueError("The immediate treasury path cannot have a relative delay.")
        if any(branch.relative_delay_blocks is None for branch in self.branches[1:]):
            raise ValueError("Every delayed treasury path must declare its relative block delay.")
        return self


class MaterializedTreasuryPolicy(StrictScenarioModel):
    policy: TreasuryPolicy
    miniscript: str = Field(min_length=1, max_length=10_000)
    descriptor: str = Field(min_length=1, max_length=10_000)
    normalized_descriptor: str = Field(min_length=1, max_length=10_000)
    checksum: str = Field(min_length=8, max_length=8)
    address: str = Field(min_length=1, max_length=128)
    is_range: Literal[False] = False
    is_solvable: Literal[True] = True
    has_private_keys: Literal[False] = False
    decision_tree: TreasuryPolicyDecisionTree


class TreasuryPolicyImportResult(StrictScenarioModel):
    coordinator_wallet: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    descriptor: str = Field(min_length=1, max_length=10_000)
    label: str = Field(min_length=1, max_length=128)
    imported: Literal[True] = True
    coordinator_can_sign: Literal[False] = False
