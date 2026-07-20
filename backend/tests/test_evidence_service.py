import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.errors import BitScopeError
from app.models.evidence import EvidenceRecord, SafeBitcoinCliCommand
from app.models.lab import LabSession
from app.models.scenario import ScenarioRun
from app.services.evidence_service import REDACTED, EvidenceService
from app.services.lab_session_store import LabSessionStore
from app.services.scenario_run_store import ScenarioRunStore


NOW = datetime(2026, 7, 20, 16, 0, tzinfo=UTC)
RUN_ID = UUID("2f14cd37-5b52-4b5b-a11c-3e5971e98eb7")


def scenario_run() -> ScenarioRun:
    return ScenarioRun(
        run_id=RUN_ID,
        scenario_id="transaction-lifecycle",
        scenario_version="1.0.0",
        lab_session_id="session_alpha",
        runtime_chain="regtest",
        bitcoin_core_version="/Satoshi:28.1.0/",
        defined_step_ids=["inspect_transaction"],
        created_at=NOW,
        updated_at=NOW,
    )


def rpc_record(**changes: object) -> EvidenceRecord:
    payload: dict[str, object] = {
        "evidence_id": "rpc.transaction",
        "kind": "rpc_result",
        "label": "Decoded transaction",
        "scenario_id": "transaction-lifecycle",
        "scenario_version": "1.0.0",
        "run_id": RUN_ID,
        "lab_session_id": "session_alpha",
        "step_id": "inspect_transaction",
        "captured_at": NOW,
        "core_output": {
            "rpc_method": "decoderawtransaction",
            "safe_parameters": ["020000000001"],
            "result": {"txid": "ab" * 32, "locktime": 0},
            "run_specific_paths": ["$.result.txid"],
        },
        "bitscope_interpretation": {
            "summary": "Bitcoin Core decoded the candidate transaction.",
            "facts": [
                {"name": "transaction.locktime", "value": 0},
                {"name": "transaction.txid", "value": "ab" * 32, "run_specific": True},
            ],
        },
        "commands": [
            {
                "arguments": ["-regtest", "decoderawtransaction", "020000000001"],
                "description": "Decode the candidate transaction on regtest.",
            }
        ],
    }
    payload.update(changes)
    return EvidenceRecord.model_validate(payload)


def evidence_service() -> EvidenceService:
    return EvidenceService.from_settings(
        Settings(
            bitcoin_rpc_user="scenario-rpc-user",
            bitcoin_rpc_password="scenario-rpc-password",
            bitscope_local_access_token="scenario-local-token",
        )
    )


def test_evidence_record_is_typed_and_separates_core_output() -> None:
    record = rpc_record()

    assert record.core_output is not None
    assert record.core_output.rpc_method == "decoderawtransaction"
    assert record.bitscope_interpretation.facts[1].run_specific is True

    with pytest.raises(ValidationError, match="distinct Bitcoin Core output"):
        rpc_record(core_output=None)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EvidenceRecord.model_validate({**record.model_dump(mode="python"), "arbitrary_log": {"value": 1}})
    with pytest.raises(ValidationError, match="must include a timezone"):
        rpc_record(captured_at=datetime(2026, 7, 20, 16, 0))


def test_safe_commands_reject_credentials_and_control_characters() -> None:
    for unsafe_argument in (
        "-rpcpassword=secret",
        "-rpcuser=alice",
        "--header=X-BitScope-Token: secret",
        "getblockcount\nstop",
    ):
        with pytest.raises(ValidationError):
            SafeBitcoinCliCommand(
                arguments=["-regtest", unsafe_argument],
                description="Unsafe command.",
            )


def test_capture_recursively_redacts_secrets_and_preserves_protocol_data() -> None:
    extended_private_key = "zprv" + "1" * 40
    wif_private_key = "K" + "1" * 51
    safe_transaction_hex = "020000000001"
    record = rpc_record(
        core_output={
            "rpc_method": "decoderawtransaction",
            "safe_parameters": {
                "hex": safe_transaction_hex,
                "rpc_password": "nested-secret",
                "nested": {
                    "note": "token=scenario-local-token",
                    "authorization": "Basic YWxpY2U6c2VjcmV0",
                    "environment": {"BITCOIN_RPC_PASSWORD": "environment-secret"},
                },
            },
            "result": {
                "txid": "ab" * 32,
                "descriptor": f"wpkh({extended_private_key}/0/*)",
                "private_material": wif_private_key,
            },
            "run_specific_paths": ["$.result.txid"],
        },
        bitscope_interpretation={
            "summary": "Observed with scenario-rpc-user using scenario-rpc-password.",
            "facts": [{"name": "transaction.hex", "value": safe_transaction_hex}],
        },
    )

    captured = evidence_service().capture(scenario_run(), record)
    serialized = captured.canonical_json

    for secret in (
        "scenario-rpc-user",
        "scenario-rpc-password",
        "scenario-local-token",
        "nested-secret",
        "environment-secret",
        extended_private_key,
        wif_private_key,
        "YWxpY2U6c2VjcmV0",
    ):
        assert secret not in serialized
    assert REDACTED in serialized
    assert safe_transaction_hex in serialized
    assert captured.record.core_output is not None
    assert captured.record.core_output.safe_parameters["rpc_password"] == REDACTED
    assert captured.run.revision == 1
    assert captured.run.evidence == [captured.reference]
    assert captured.reference.content_sha256 == sha256(serialized.encode("utf-8")).hexdigest()


def test_capture_is_canonical_and_deterministic() -> None:
    service = evidence_service()
    first = service.capture(scenario_run(), rpc_record())
    second = service.capture(scenario_run(), rpc_record())

    assert first.canonical_json == second.canonical_json
    assert first.reference == second.reference
    parsed = json.loads(first.canonical_json)
    assert list(parsed) == sorted(parsed)
    assert first.canonical_json.endswith("\n")


def test_even_short_configured_secret_values_are_not_leaked() -> None:
    service = EvidenceService.from_settings(
        Settings(
            bitcoin_rpc_user="u",
            bitcoin_rpc_password="pw",
            bitscope_local_access_token="tok",
        )
    )
    record = rpc_record(
        bitscope_interpretation={
            "summary": "Credentials were u, pw, and tok.",
            "facts": [],
        }
    )

    captured = service.capture(scenario_run(), record)

    assert "Credentials were [REDACTED], [REDACTED], and [REDACTED]." in captured.canonical_json


def test_secret_value_collisions_do_not_rewrite_evidence_identity() -> None:
    service = EvidenceService.from_settings(
        Settings(
            bitcoin_rpc_user="transaction-lifecycle",
            bitcoin_rpc_password="rpc_result",
            bitscope_local_access_token="session_alpha",
        )
    )

    captured = service.capture(scenario_run(), rpc_record())

    assert captured.record.scenario_id == "transaction-lifecycle"
    assert captured.record.kind == "rpc_result"
    assert captured.record.lab_session_id == "session_alpha"


def test_capture_rejects_cross_run_identity_and_unknown_steps() -> None:
    service = evidence_service()

    with pytest.raises(BitScopeError) as mismatch:
        service.capture(scenario_run(), rpc_record(lab_session_id="session_other"))
    assert mismatch.value.code == "EVIDENCE_RUN_IDENTITY_MISMATCH"
    assert mismatch.value.details["mismatched_fields"] == ["lab_session_id"]

    with pytest.raises(BitScopeError) as unknown_step:
        service.capture(scenario_run(), rpc_record(step_id="missing_step"))
    assert unknown_step.value.code == "EVIDENCE_STEP_NOT_FOUND"


def test_capture_enforces_bounded_content() -> None:
    service = EvidenceService.from_settings(Settings(), max_content_bytes=1_024)
    oversized = rpc_record(
        bitscope_interpretation={
            "summary": "x" * 2_000,
            "facts": [],
        }
    )

    with pytest.raises(BitScopeError) as too_large:
        service.capture(scenario_run(), oversized)
    assert too_large.value.code == "EVIDENCE_CONTENT_TOO_LARGE"


def test_captured_reference_persists_with_the_run(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    LabSessionStore(str(database)).save(
        LabSession(
            session_id="session_alpha",
            wallet_name="bitscope-session-alpha",
            owned_wallets=["bitscope-session-alpha"],
            wallet_generation=0,
            runtime_chain="regtest",
            starting_height=200,
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    store = ScenarioRunStore(str(database))
    run = scenario_run()
    store.create(run)

    captured = evidence_service().capture(run, rpc_record())
    store.save(captured.run, expected_revision=0)

    restored = store.get(run.run_id)
    assert restored is not None
    assert restored.evidence == [captured.reference]
    assert restored.revision == 1


def test_duplicate_evidence_identifiers_are_rejected() -> None:
    captured = evidence_service().capture(scenario_run(), rpc_record())

    with pytest.raises(ValueError, match="already been recorded"):
        captured.run.record_evidence_reference(captured.reference, now=NOW)
