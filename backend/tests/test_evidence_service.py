import json
from io import BytesIO
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.errors import BitScopeError
from app.main import create_app
from app.models.evidence import EvidenceRecord, SafeBitcoinCliCommand
from app.models.lab import LabSession
from app.models.scenario import EvidenceReference, ScenarioDefinition, ScenarioRun
from app.routes.scenarios import get_proof_bundle_service
from app.services.evidence_service import REDACTED, EvidenceService, ScenarioEvidenceRecorder
from app.services.lab_session_store import LabSessionStore
from app.services.proof_bundle_service import ProofBundleService
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_catalog import RegisteredScenario, ScenarioCatalog
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
        defined_step_ids=[
            "verify_chain",
            "prepare_wallet",
            "inspect_transaction",
            "verify_transaction",
            "export_proof",
            "cleanup",
        ],
        created_at=NOW,
        updated_at=NOW,
    )


def scenario_definition() -> ScenarioDefinition:
    return ScenarioDefinition.model_validate(
        {
            "scenario_id": "transaction-lifecycle",
            "version": "1.0.0",
            "name": "Transaction lifecycle",
            "summary": "Inspect a generated transaction value, preserve reproducible evidence, and clean up.",
            "difficulty": "beginner",
            "related_lbcli_chapters": [3, 4],
            "concepts": ["Transactions", "Wallets", "Regtest"],
            "required_capabilities": ["read_only", "regtest_mutation"],
            "estimated_run_steps": 6,
            "steps": [
                {
                    "step_id": "verify_chain",
                    "type": "verify_runtime_chain",
                    "phase": "setup",
                    "title": "Verify chain",
                    "description": "Verify that Bitcoin Core reports regtest.",
                    "output_context_ref": "node.context",
                },
                {
                    "step_id": "prepare_wallet",
                    "type": "prepare_isolated_wallet",
                    "phase": "setup",
                    "title": "Prepare wallet",
                    "description": "Prepare a session-owned wallet.",
                    "depends_on": ["verify_chain"],
                    "wallet_role": "operator",
                    "output_wallet_ref": "wallet.operator",
                },
                {
                    "step_id": "inspect_transaction",
                    "type": "generate_address",
                    "phase": "execution",
                    "title": "Generate public value",
                    "description": "Generate a safe run-specific public value for inspection.",
                    "depends_on": ["prepare_wallet"],
                    "wallet_ref": "wallet.operator",
                    "output_address_ref": "address.recipient",
                },
                {
                    "step_id": "verify_transaction",
                    "type": "evaluate_assertions",
                    "phase": "verification",
                    "title": "Verify output",
                    "description": "Verify the generated public value.",
                    "depends_on": ["inspect_transaction"],
                    "assertion_ids": ["output_ready"],
                },
                {
                    "step_id": "export_proof",
                    "type": "export_evidence",
                    "phase": "export",
                    "title": "Export evidence",
                    "description": "Export the redacted proof bundle.",
                    "depends_on": ["verify_transaction"],
                    "output_bundle_ref": "proof.bundle",
                },
                {
                    "step_id": "cleanup",
                    "type": "cleanup_lab",
                    "phase": "cleanup",
                    "title": "Clean up",
                    "description": "Unload session-owned wallets.",
                    "depends_on": ["export_proof"],
                },
            ],
            "assertions": [
                {
                    "assertion_id": "output_ready",
                    "kind": "rpc_succeeded",
                    "after_step_id": "inspect_transaction",
                    "subject_ref": "address.recipient",
                    "description": "Bitcoin Core generated the public value.",
                }
            ],
        }
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


def test_artifact_store_writes_idempotently_and_detects_conflicts_and_tampering(tmp_path: Path) -> None:
    artifacts = ScenarioArtifactStore(str(tmp_path / "artifacts"))
    captured = evidence_service().capture(scenario_run(), rpc_record())

    artifacts.write_evidence(captured)
    artifacts.write_evidence(captured)
    target = tmp_path / "artifacts" / str(RUN_ID) / "evidence" / "rpc.transaction.json"
    assert target.read_text(encoding="utf-8") == captured.canonical_json
    assert artifacts.read_evidence(captured.run, captured.reference) == captured.record

    conflicting = evidence_service().capture(
        scenario_run(),
        rpc_record(label="Different content for the same identifier"),
    )
    with pytest.raises(BitScopeError) as conflict:
        artifacts.write_evidence(conflicting)
    assert conflict.value.code == "EVIDENCE_ARTIFACT_CONFLICT"

    target.write_text(captured.canonical_json.replace("Decoded transaction", "Tampered transaction"), encoding="utf-8")
    with pytest.raises(BitScopeError) as tampered:
        artifacts.read_evidence(captured.run, captured.reference)
    assert tampered.value.code == "EVIDENCE_ARTIFACT_HASH_MISMATCH"


def test_artifact_store_rejects_non_server_generated_paths(tmp_path: Path) -> None:
    captured = evidence_service().capture(scenario_run(), rpc_record())
    unsafe_reference = EvidenceReference(
        evidence_id=captured.reference.evidence_id,
        kind=captured.reference.kind,
        label=captured.reference.label,
        relative_path="evidence/different.json",
        content_sha256=captured.reference.content_sha256,
    )
    unsafe_capture = type(captured)(
        run=captured.run,
        reference=unsafe_reference,
        record=captured.record,
        canonical_json=captured.canonical_json,
    )

    with pytest.raises(BitScopeError) as unsafe:
        ScenarioArtifactStore(str(tmp_path / "artifacts")).write_evidence(unsafe_capture)
    assert unsafe.value.code == "EVIDENCE_ARTIFACT_PATH_INVALID"


def build_persisted_evidence(tmp_path: Path) -> tuple[ScenarioRunStore, ScenarioArtifactStore, ScenarioRun]:
    database = tmp_path / "proof.sqlite3"
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
    run_store = ScenarioRunStore(str(database))
    run_store.create(scenario_run())
    artifact_store = ScenarioArtifactStore(str(tmp_path / "artifacts"))
    recorder = ScenarioEvidenceRecorder(evidence_service(), artifact_store, run_store)
    captured = recorder.record(
        RUN_ID,
        "session_alpha",
        0,
        rpc_record(
            bitscope_interpretation={
                "summary": "Decoded without retaining scenario-rpc-password.",
                "facts": [],
            }
        ),
    )
    return run_store, artifact_store, captured.run


def proof_service(tmp_path: Path) -> tuple[ProofBundleService, ScenarioRun]:
    run_store, artifact_store, run = build_persisted_evidence(tmp_path)
    catalog = ScenarioCatalog((RegisteredScenario(scenario_definition()),))
    return ProofBundleService(run_store, artifact_store, catalog), run


def test_recorder_persists_redacted_artifact_and_revisioned_reference(tmp_path: Path) -> None:
    run_store, artifact_store, updated = build_persisted_evidence(tmp_path)

    restored = run_store.get(RUN_ID)
    assert restored == updated
    assert restored is not None
    assert restored.revision == 1
    assert restored.evidence[0].relative_path == "evidence/rpc.transaction.json"
    assert artifact_store.list_evidence(restored)[0].evidence_id == "rpc.transaction"

    recorder = ScenarioEvidenceRecorder(evidence_service(), artifact_store, run_store)
    with pytest.raises(BitScopeError) as stale:
        recorder.record(RUN_ID, "session_alpha", 0, rpc_record())
    assert stale.value.code == "SCENARIO_RUN_REVISION_CONFLICT"
    with pytest.raises(BitScopeError) as hidden:
        recorder.record(RUN_ID, "session_other", 1, rpc_record())
    assert hidden.value.code == "SCENARIO_RUN_NOT_FOUND"


def test_proof_bundle_is_deterministic_and_manifest_hashes_every_payload(tmp_path: Path) -> None:
    service, run = proof_service(tmp_path)

    first = service.bundle(run.run_id, run.lab_session_id)
    second = service.bundle(run.run_id, run.lab_session_id)

    assert first.zip_bytes == second.zip_bytes
    assert "scenario-rpc-password" not in first.report_markdown
    assert first.report_markdown == second.report_markdown
    assert "## Bitcoin Core output" in first.report_markdown
    assert "## BitScope interpretation" in first.report_markdown
    assert "## Expected failures" in first.report_markdown
    assert "## Unexpected failures" in first.report_markdown
    assert set(entry.path for entry in first.manifest.files) == set(first.files) - {"manifest.json"}
    for entry in first.manifest.files:
        content = first.files[entry.path]
        assert entry.content_bytes == len(content)
        assert entry.content_sha256 == sha256(content).hexdigest()

    with ZipFile(BytesIO(first.zip_bytes)) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert names == [f"bitscope-proof/{path}" for path in sorted(first.files)]
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
        assert all(".." not in Path(name).parts for name in names)
        assert all(b"scenario-rpc-password" not in archive.read(name) for name in names)
        manifest = json.loads(archive.read("bitscope-proof/manifest.json"))
        assert manifest["hash_scope"] == "all_bundle_files_except_manifest"
        assert manifest["generated_from_revision"] == 1
        commands = archive.read("bitscope-proof/commands.sh").decode("utf-8")
        assert "bitcoin-cli -regtest decoderawtransaction" in commands
        assert "rpcpassword" not in commands.casefold()


def test_proof_reads_are_session_scoped(tmp_path: Path) -> None:
    service, run = proof_service(tmp_path)

    evidence = service.evidence(run.run_id, "session_alpha")
    assert evidence.revision == 1
    assert [record.evidence_id for record in evidence.evidence] == ["rpc.transaction"]
    with pytest.raises(BitScopeError) as hidden:
        service.bundle(run.run_id, "session_other")
    assert hidden.value.code == "SCENARIO_RUN_NOT_FOUND"


def test_evidence_report_and_bundle_routes_stream_owned_redacted_artifacts(tmp_path: Path) -> None:
    service, run = proof_service(tmp_path)
    settings = Settings(app_environment="test")
    app = create_app(settings)
    app.dependency_overrides[get_proof_bundle_service] = lambda: service
    client = TestClient(app)
    query = {"lab_session_id": "session_alpha"}

    evidence = client.get(f"/api/scenario-runs/{run.run_id}/evidence", params=query)
    assert evidence.status_code == 200
    assert evidence.json()["evidence"][0]["evidence_id"] == "rpc.transaction"
    report = client.get(f"/api/scenario-runs/{run.run_id}/report", params=query)
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/markdown")
    bundle = client.get(f"/api/scenario-runs/{run.run_id}/bundle", params=query)
    assert bundle.status_code == 200
    assert bundle.headers["content-type"] == "application/zip"
    assert f"bitscope-proof-{run.run_id}.zip" in bundle.headers["content-disposition"]
    with ZipFile(BytesIO(bundle.content)) as archive:
        assert "bitscope-proof/manifest.json" in archive.namelist()

    hidden = client.get(
        f"/api/scenario-runs/{run.run_id}/evidence",
        params={"lab_session_id": "session_other"},
    )
    assert hidden.status_code == 404
