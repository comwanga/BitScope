from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.treasury import (
    TreasuryParticipant,
    TreasuryParticipantGroup,
    TreasuryParticipantRole,
    TreasuryPolicy,
)


def public_key(index: int) -> str:
    prefix = "02" if index % 2 else "03"
    return f"{prefix}{index:064x}"


def signer_group(role: TreasuryParticipantRole, key_offset: int) -> TreasuryParticipantGroup:
    # Deliberately supply non-canonical list order; position is the stable policy order.
    return TreasuryParticipantGroup(
        role=role,
        participants=[
            TreasuryParticipant(
                participant_id=f"{role.value}-{position}",
                role=role,
                position=position,
                wallet_name=f"treasury-{role.value}-{position}",
                public_key=public_key(key_offset + position).upper(),
            )
            for position in (3, 1, 2)
        ],
    )


def valid_policy() -> TreasuryPolicy:
    return TreasuryPolicy(
        recovery_delay_blocks=5,
        emergency_delay_blocks=10,
        operators=signer_group(TreasuryParticipantRole.OPERATOR, 0),
        recovery=signer_group(TreasuryParticipantRole.RECOVERY, 10),
        emergency=signer_group(TreasuryParticipantRole.EMERGENCY, 20),
    )


def test_policy_models_capture_the_proven_public_three_path_policy() -> None:
    policy = valid_policy()

    assert policy.policy_id == "community-treasury-recovery"
    assert policy.script_type == "p2wsh"
    assert policy.delay_unit == "blocks"
    assert policy.operators.required_signatures == 2
    assert [participant.position for participant in policy.operators.ordered_participants()] == [1, 2, 3]
    assert all(
        participant.public_key == participant.public_key.lower()
        for participant in policy.operators.participants
    )


def test_participant_rejects_non_public_or_uncompressed_key_material() -> None:
    with pytest.raises(ValidationError, match="public_key"):
        TreasuryParticipant(
            participant_id="operator-1",
            role=TreasuryParticipantRole.OPERATOR,
            position=1,
            wallet_name="treasury-operator-1",
            public_key="private-key-material",
        )


def test_group_requires_matching_roles_and_each_canonical_position() -> None:
    group = signer_group(TreasuryParticipantRole.OPERATOR, 0)
    invalid = group.model_dump()
    invalid["participants"][0]["role"] = TreasuryParticipantRole.RECOVERY
    invalid["participants"][1]["position"] = 3

    with pytest.raises(ValidationError, match="match the role|positions"):
        TreasuryParticipantGroup.model_validate(invalid)


def test_policy_requires_emergency_delay_after_recovery_delay() -> None:
    invalid = valid_policy().model_dump()
    invalid["emergency_delay_blocks"] = invalid["recovery_delay_blocks"]

    with pytest.raises(ValidationError, match="greater than the recovery delay"):
        TreasuryPolicy.model_validate(invalid)


def test_policy_rejects_reused_wallets_and_public_keys_across_roles() -> None:
    invalid = valid_policy().model_dump()
    invalid["emergency"]["participants"][0]["wallet_name"] = invalid["operators"]["participants"][0]["wallet_name"]
    invalid["emergency"]["participants"][0]["public_key"] = invalid["operators"]["participants"][0]["public_key"]

    with pytest.raises(ValidationError, match="wallets must be unique|public keys must be unique"):
        TreasuryPolicy.model_validate(invalid)


def test_policy_rejects_delays_outside_block_based_bip68_range() -> None:
    invalid = valid_policy().model_dump()
    invalid["emergency_delay_blocks"] = 65_536

    with pytest.raises(ValidationError, match="less than or equal to 65535"):
        TreasuryPolicy.model_validate(invalid)


def test_policy_rejects_threshold_or_shape_drift_from_reviewed_version() -> None:
    invalid_threshold = valid_policy().model_dump()
    invalid_threshold["operators"]["required_signatures"] = 1
    with pytest.raises(ValidationError, match="Input should be 2"):
        TreasuryPolicy.model_validate(invalid_threshold)

    invalid_extra = valid_policy().model_dump()
    invalid_extra["unsupported_branch"] = "simulated"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TreasuryPolicy.model_validate(invalid_extra)
