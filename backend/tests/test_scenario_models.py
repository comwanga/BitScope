from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.models.scenario import (
    AssertionResult,
    AssertionResultStatus,
    CleanupStatus,
    EvidenceReference,
    FailureCategory,
    ScenarioDefinition,
    ScenarioFailure,
    ScenarioRun,
    ScenarioRunState,
    ScenarioStepResult,
    ScenarioStepResultStatus,
)


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def valid_definition_data() -> dict[str, object]:
    return {
        "scenario_id": "transaction-lifecycle",
        "version": "1.0.0",
        "name": "Transaction lifecycle",
        "summary": "Prepare an isolated wallet and verify that Bitcoin Core is ready for a transaction workflow.",
        "difficulty": "beginner",
        "related_lbcli_chapters": [3, 4],
        "concepts": ["Transactions", "Wallets", "Regtest"],
        "required_network": "regtest",
        "required_capabilities": ["read_only", "regtest_mutation"],
        "estimated_run_steps": 6,
        "steps": [
            {
                "step_id": "verify_chain",
                "type": "verify_runtime_chain",
                "phase": "setup",
                "title": "Verify runtime chain",
                "description": "Fail closed unless Bitcoin Core reports regtest.",
                "output_context_ref": "node.context",
            },
            {
                "step_id": "prepare_wallet",
                "type": "prepare_isolated_wallet",
                "phase": "setup",
                "title": "Prepare wallet",
                "description": "Create a session-owned wallet for the run.",
                "depends_on": ["verify_chain"],
                "wallet_role": "operator",
                "output_wallet_ref": "wallet.operator",
            },
            {
                "step_id": "generate_address",
                "type": "generate_address",
                "phase": "execution",
                "title": "Generate address",
                "description": "Generate a fresh address from the isolated wallet.",
                "depends_on": ["prepare_wallet"],
                "wallet_ref": "wallet.operator",
                "output_address_ref": "address.recipient",
            },
            {
                "step_id": "verify_setup",
                "type": "evaluate_assertions",
                "phase": "verification",
                "title": "Verify setup",
                "description": "Evaluate the required setup assertion.",
                "depends_on": ["generate_address"],
                "assertion_ids": ["wallet_ready"],
            },
            {
                "step_id": "export_proof",
                "type": "export_evidence",
                "phase": "export",
                "title": "Export evidence",
                "description": "Export the evidence collected by the run.",
                "depends_on": ["verify_setup"],
                "output_bundle_ref": "proof.bundle",
            },
            {
                "step_id": "cleanup",
                "type": "cleanup_lab",
                "phase": "cleanup",
                "title": "Clean up",
                "description": "Unload only wallets owned by the lab session.",
                "depends_on": ["export_proof"],
            },
        ],
        "assertions": [
            {
                "assertion_id": "wallet_ready",
                "kind": "rpc_succeeded",
                "after_step_id": "generate_address",
                "subject_ref": "address.recipient",
                "description": "Bitcoin Core generated a fresh recipient address.",
            }
        ],
        "cleanup_rules": {
            "unload_owned_wallets": True,
            "preserve_unowned_wallets": True,
            "fail_run_on_cleanup_error": True,
        },
    }


def valid_definition() -> ScenarioDefinition:
    return ScenarioDefinition.model_validate(valid_definition_data())


def test_valid_scenario_definition_uses_closed_typed_steps() -> None:
    definition = valid_definition()

    assert definition.required_network == "regtest"
    assert [step.type for step in definition.steps] == [
        "verify_runtime_chain",
        "prepare_isolated_wallet",
        "generate_address",
        "evaluate_assertions",
        "export_evidence",
        "cleanup_lab",
    ]
    assert definition.assertions[0].assertion_id == "wallet_ready"


def test_scenario_definition_rejects_unsupported_step_type() -> None:
    payload = valid_definition_data()
    payload["steps"][1] = {  # type: ignore[index]
        "step_id": "arbitrary",
        "type": "arbitrary_rpc",
        "phase": "execution",
        "title": "Call anything",
        "description": "This must never validate.",
        "rpc_method": "stop",
    }

    with pytest.raises(ValidationError, match="union_tag_invalid"):
        ScenarioDefinition.model_validate(payload)


def test_scenario_step_rejects_arbitrary_rpc_fields() -> None:
    payload = valid_definition_data()
    payload["steps"][1]["rpc_method"] = "dumpprivkey"  # type: ignore[index]

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ScenarioDefinition.model_validate(payload)


def test_scenario_definition_rejects_non_regtest_network() -> None:
    payload = valid_definition_data()
    payload["required_network"] = "mainnet"

    with pytest.raises(ValidationError, match="regtest"):
        ScenarioDefinition.model_validate(payload)


def test_scenario_definition_rejects_duplicate_steps() -> None:
    payload = valid_definition_data()
    payload["steps"][1]["step_id"] = "verify_chain"  # type: ignore[index]

    with pytest.raises(ValidationError, match="Duplicate scenario step identifier"):
        ScenarioDefinition.model_validate(payload)


def test_scenario_definition_rejects_missing_or_later_dependencies() -> None:
    payload = valid_definition_data()
    payload["steps"][1]["depends_on"] = ["export_proof"]  # type: ignore[index]

    with pytest.raises(ValidationError, match="missing or later steps"):
        ScenarioDefinition.model_validate(payload)


def test_scenario_definition_rejects_unknown_artifact_references() -> None:
    payload = valid_definition_data()
    payload["steps"][2]["wallet_ref"] = "wallet.missing"  # type: ignore[index]

    with pytest.raises(ValidationError, match="not produced by earlier steps"):
        ScenarioDefinition.model_validate(payload)


def test_scenario_definition_rejects_out_of_order_phases() -> None:
    payload = valid_definition_data()
    generate_address = payload["steps"].pop(2)  # type: ignore[union-attr]
    payload["steps"].insert(3, generate_address)  # type: ignore[union-attr]

    with pytest.raises(ValidationError, match="must follow setup, execution, attack"):
        ScenarioDefinition.model_validate(payload)


def test_scenario_definition_requires_cleanup_as_final_step() -> None:
    payload = valid_definition_data()
    payload["steps"] = payload["steps"][:-1]  # type: ignore[index]
    payload["estimated_run_steps"] = 5

    with pytest.raises(ValidationError, match="cleanup"):
        ScenarioDefinition.model_validate(payload)


def test_mutating_steps_require_regtest_mutation_capability() -> None:
    payload = valid_definition_data()
    payload["required_capabilities"] = ["read_only"]

    with pytest.raises(ValidationError, match="regtest mutation RPC capability"):
        ScenarioDefinition.model_validate(payload)


def test_assertions_must_reference_known_steps() -> None:
    payload = valid_definition_data()
    payload["assertions"][0]["after_step_id"] = "missing_step"  # type: ignore[index]

    with pytest.raises(ValidationError, match="references unknown step"):
        ScenarioDefinition.model_validate(payload)


def test_evaluation_steps_must_reference_known_assertions() -> None:
    payload = valid_definition_data()
    payload["steps"][3]["assertion_ids"] = ["missing_assertion"]  # type: ignore[index]

    with pytest.raises(ValidationError, match="references unknown assertions"):
        ScenarioDefinition.model_validate(payload)


def test_required_assertions_must_be_assigned_to_an_evaluation_step() -> None:
    payload = valid_definition_data()
    payload["assertions"].append(  # type: ignore[union-attr]
        {
            "assertion_id": "optional_wallet_note",
            "kind": "rpc_succeeded",
            "after_step_id": "generate_address",
            "subject_ref": "address.recipient",
            "required": False,
            "description": "An optional wallet observation.",
        }
    )
    payload["steps"][3]["assertion_ids"] = ["optional_wallet_note"]  # type: ignore[index]

    with pytest.raises(ValidationError, match="Required assertions are not assigned"):
        ScenarioDefinition.model_validate(payload)


def test_finalize_psbt_extraction_requires_a_transaction_reference() -> None:
    payload = valid_definition_data()
    payload["steps"].insert(3, {  # type: ignore[union-attr]
        "step_id": "finalize",
        "type": "finalize_psbt",
        "phase": "execution",
        "title": "Finalize PSBT",
        "description": "Extract a complete transaction.",
        "depends_on": ["generate_address"],
        "psbt_ref": "psbt.processed",
        "extract": True,
        "output_psbt_ref": "psbt.finalized",
    })
    payload["estimated_run_steps"] = 7

    with pytest.raises(ValidationError, match="output transaction reference"):
        ScenarioDefinition.model_validate(payload)


def test_evidence_references_reject_traversal_and_untyped_secret_content() -> None:
    with pytest.raises(ValidationError, match="normalized relative paths"):
        EvidenceReference(
            evidence_id="node.context",
            kind="node_context",
            label="Node context",
            relative_path="../rpc-password.json",
        )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EvidenceReference.model_validate(
            {
                "evidence_id": "node.context",
                "kind": "node_context",
                "label": "Node context",
                "rpc_password": "must-not-be-stored",
            }
        )


def test_run_creation_requires_a_valid_lab_session_and_snapshots_assertions() -> None:
    run = ScenarioRun.create(valid_definition(), "session_12345678", "Bitcoin Core 28.1", now=NOW)

    assert run.runtime_chain == "regtest"
    assert run.lab_session_id == "session_12345678"
    assert run.required_assertion_ids == ["wallet_ready"]
    assert run.current_state == ScenarioRunState.CREATED

    with pytest.raises(ValidationError, match="at least 8 characters"):
        ScenarioRun.create(valid_definition(), "short", now=NOW)


def test_run_state_machine_accepts_valid_transitions_and_rejects_invalid_ones() -> None:
    run = ScenarioRun.create(valid_definition(), "session_12345678", now=NOW)

    with pytest.raises(ValueError, match="Invalid scenario run transition"):
        run.transition_to(ScenarioRunState.VERIFIED, now=NOW)

    run = run.transition_to(ScenarioRunState.READY, now=NOW)
    run = run.transition_to(ScenarioRunState.RUNNING, now=NOW)
    run = run.transition_to(ScenarioRunState.VERIFYING, now=NOW)
    run = run.record_assertion_result(
        AssertionResult(
            assertion_id="wallet_ready",
            status=AssertionResultStatus.PASSED,
            required=True,
            explanation="Bitcoin Core created the wallet.",
        ),
        now=NOW,
    )
    run = run.transition_to(ScenarioRunState.CLEANING, now=NOW)
    run = run.with_cleanup_status(CleanupStatus.COMPLETED, now=NOW)
    run = run.transition_to(ScenarioRunState.VERIFIED, now=NOW)

    assert run.final_result == "verified"
    assert run.completed_at == NOW


def test_verified_run_requires_completed_cleanup() -> None:
    run = ScenarioRun.create(valid_definition(), "session_12345678", now=NOW)
    run = run.transition_to(ScenarioRunState.READY, now=NOW)
    run = run.transition_to(ScenarioRunState.RUNNING, now=NOW)
    run = run.transition_to(ScenarioRunState.VERIFYING, now=NOW)
    run = run.record_assertion_result(
        AssertionResult(
            assertion_id="wallet_ready",
            status=AssertionResultStatus.PASSED,
            required=True,
            explanation="The assertion passed.",
        ),
        now=NOW,
    )
    run = run.transition_to(ScenarioRunState.CLEANING, now=NOW)

    with pytest.raises(ValidationError, match="requires completed cleanup"):
        run.transition_to(ScenarioRunState.VERIFIED, now=NOW)


def test_verified_run_rejects_missing_or_skipped_required_assertions() -> None:
    run = ScenarioRun.create(valid_definition(), "session_12345678", now=NOW)
    run = run.transition_to(ScenarioRunState.READY, now=NOW)
    run = run.transition_to(ScenarioRunState.RUNNING, now=NOW)
    run = run.transition_to(ScenarioRunState.VERIFYING, now=NOW)
    run = run.transition_to(ScenarioRunState.CLEANING, now=NOW)
    run = run.with_cleanup_status(CleanupStatus.COMPLETED, now=NOW)

    with pytest.raises(ValidationError, match="Required assertions were not evaluated"):
        run.transition_to(ScenarioRunState.VERIFIED, now=NOW)

    run = run.record_assertion_result(
        AssertionResult(
            assertion_id="wallet_ready",
            status=AssertionResultStatus.SKIPPED,
            required=True,
            explanation="The required assertion was skipped.",
        ),
        now=NOW,
    )
    with pytest.raises(ValidationError, match="Required assertions did not pass"):
        run.transition_to(ScenarioRunState.VERIFIED, now=NOW)


def test_step_results_distinguish_expected_and_unexpected_failures() -> None:
    run = ScenarioRun.create(valid_definition(), "session_12345678", now=NOW)
    expected = ScenarioFailure(
        failure_id="failure.expected",
        step_id="premature_spend",
        category=FailureCategory.MEMPOOL_POLICY,
        expected=True,
        code="TRANSACTION_REJECTED_BY_POLICY",
        safe_message="Bitcoin Core rejected the premature spend.",
        rpc_code=-26,
    )
    run = run.record_step_result(
        ScenarioStepResult(
            step_id="premature_spend",
            status=ScenarioStepResultStatus.EXPECTED_FAILURE,
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=1),
            failure=expected,
        ),
        now=NOW,
    )
    unexpected = ScenarioFailure(
        failure_id="failure.unexpected",
        step_id="broadcast",
        category=FailureCategory.UNEXPECTED_APPLICATION,
        expected=False,
        code="BITCOIN_CORE_OFFLINE",
        safe_message="Bitcoin Core was unavailable.",
    )
    run = run.record_step_result(
        ScenarioStepResult(
            step_id="broadcast",
            status=ScenarioStepResultStatus.UNEXPECTED_FAILURE,
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=1),
            failure=unexpected,
        ),
        now=NOW,
    )

    assert run.completed_steps == ["premature_spend"]
    assert run.failed_steps == ["broadcast"]
    assert run.expected_failures == [expected]
    assert run.unexpected_failures == [unexpected]


def test_duplicate_step_execution_is_rejected() -> None:
    run = ScenarioRun.create(valid_definition(), "session_12345678", now=NOW)
    result = ScenarioStepResult(
        step_id="verify_chain",
        status=ScenarioStepResultStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
    )
    run = run.record_step_result(result, now=NOW)

    with pytest.raises(ValueError, match="already been recorded"):
        run.record_step_result(result, now=NOW)


def test_cleanup_failure_has_a_distinct_terminal_result() -> None:
    run = ScenarioRun.create(valid_definition(), "session_12345678", now=NOW)
    run = run.transition_to(ScenarioRunState.CLEANING, now=NOW)
    run = run.with_cleanup_status(CleanupStatus.FAILED, now=NOW)
    run = run.transition_to(ScenarioRunState.CLEANUP_FAILED, now=NOW)

    assert run.final_result == "cleanup_failed"
    assert run.cleanup_status == CleanupStatus.FAILED


def test_run_rejects_duplicate_evidence_references() -> None:
    run = ScenarioRun.create(valid_definition(), "session_12345678", now=NOW)
    payload = run.model_dump(mode="python")
    reference = {
        "evidence_id": "node.context",
        "kind": "node_context",
        "label": "Node context",
        "redacted": True,
    }
    payload["evidence"] = [deepcopy(reference), deepcopy(reference)]

    with pytest.raises(ValidationError, match="Evidence identifiers must be unique"):
        ScenarioRun.model_validate(payload)
