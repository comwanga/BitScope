from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from app.errors import BitScopeError
from app.models.evidence import CapturedEvidence, EvidenceRecord
from app.models.scenario import (
    CleanupStatus,
    FailureCategory,
    ScenarioFailure,
    ScenarioRun,
    ScenarioRunState,
    ScenarioStepResult,
    ScenarioStepResultStatus,
    TERMINAL_RUN_STATES,
)
from app.rpc.capabilities import ReadOnlyRpcClient, RpcTransport
from app.services.evidence_service import EvidenceService
from app.services.lab_session_store import LabSessionStore
from app.services.network_safety import NetworkSafetyGuard
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_catalog import ScenarioCatalog
from app.services.scenario_run_store import ScenarioRunStore
from app.services.transaction_lifecycle_scenario import TRANSACTION_LIFECYCLE_SCENARIO
from app.services.transaction_lifecycle_service import (
    TransactionLifecycleExecutionError,
    TransactionLifecycleService,
)


class ScenarioService:
    """Coordinate safe run preparation without claiming scenario execution."""

    def __init__(
        self,
        rpc_client: RpcTransport,
        store: ScenarioRunStore,
        catalog: ScenarioCatalog,
        evidence_service: EvidenceService,
        artifact_store: ScenarioArtifactStore,
        lab_store: LabSessionStore | None = None,
    ) -> None:
        self.rpc = ReadOnlyRpcClient(rpc_client)
        self.store = store
        self.catalog = catalog
        self.evidence_service = evidence_service
        self.artifact_store = artifact_store
        self.lifecycle_service = TransactionLifecycleService(
            rpc_client,
            lab_store or LabSessionStore(store.database_path),
        )

    def create_run(self, scenario_id: str, lab_session_id: str) -> ScenarioRun:
        definition = self.catalog.require_available(scenario_id)
        NetworkSafetyGuard(self.rpc).require_regtest()
        run = ScenarioRun.create(
            definition,
            lab_session_id,
            bitcoin_core_version=self._bitcoin_core_version(),
        )
        self.store.create(run)
        return run

    def get_run(self, run_id: UUID, lab_session_id: str) -> ScenarioRun:
        run = self.store.get_for_session(run_id, lab_session_id)
        if run is None:
            raise BitScopeError(
                code="SCENARIO_RUN_NOT_FOUND",
                message="The requested scenario run does not exist.",
                status_code=404,
                details={"run_id": str(run_id)},
            )
        return run

    def advance(self, run_id: UUID, lab_session_id: str, expected_revision: int) -> ScenarioRun:
        run = self.get_run(run_id, lab_session_id)
        self._require_revision(run, expected_revision)
        if run.current_state == ScenarioRunState.READY:
            definition = self.catalog.get_version(run.scenario_id, run.scenario_version)
            if definition != TRANSACTION_LIFECYCLE_SCENARIO:
                raise self._execution_not_available(run)
            return self._execute_transaction_lifecycle(run)
        if run.current_state != ScenarioRunState.CREATED:
            raise self._execution_not_available(run)

        definition = self.catalog.get_version(run.scenario_id, run.scenario_version)
        context, blockchain_info = NetworkSafetyGuard(self.rpc).require_regtest_with_info()
        network_info = self.rpc.get_network_info()
        block_height = self.rpc.get_block_count()
        if not isinstance(network_info, dict):
            raise self._invalid_readiness_response("getnetworkinfo")
        if not isinstance(block_height, int) or isinstance(block_height, bool) or block_height < 0:
            raise self._invalid_readiness_response("getblockcount")

        captured_at = datetime.now(UTC)
        record = EvidenceRecord(
            evidence_id="node.context",
            kind="node_context",
            label="Verified regtest node context",
            scenario_id=run.scenario_id,
            scenario_version=run.scenario_version,
            run_id=run.run_id,
            lab_session_id=run.lab_session_id,
            step_id=definition.steps[0].step_id,
            captured_at=captured_at,
            core_output={
                "safe_parameters": [],
                "result": {
                    "getblockchaininfo": blockchain_info,
                    "getnetworkinfo": network_info,
                    "getblockcount": block_height,
                },
                "run_specific_paths": ["$.result.getblockcount"],
            },
            bitscope_interpretation={
                "summary": "Bitcoin Core and BitScope configuration agree on an isolated regtest runtime.",
                "facts": [
                    {"name": "node.configured_network", "value": context.configured_network},
                    {"name": "node.runtime_chain", "value": context.runtime_chain},
                    {"name": "node.block_height", "value": block_height, "run_specific": True},
                    {"name": "node.core_version", "value": self._bitcoin_core_version_from(network_info)},
                ],
                "limitations": [
                    "Node readiness verifies chain identity and observable node context; it does not execute scenario steps."
                ],
            },
            commands=[
                {"arguments": ["-regtest", "getblockchaininfo"], "description": "Inspect the live chain identity."},
                {"arguments": ["-regtest", "getnetworkinfo"], "description": "Inspect the Bitcoin Core version."},
                {"arguments": ["-regtest", "getblockcount"], "description": "Inspect the current block height."},
            ],
        )
        captured = self.evidence_service.capture(run, record)
        ready = run.transition_to(
            ScenarioRunState.READY,
            now=captured_at,
            evidence_reference=captured.reference,
        )
        persisted = replace(captured, run=ready)
        created = self.artifact_store.write_evidence(persisted)
        try:
            self.store.save(ready, expected_revision=expected_revision)
        except Exception:
            if created:
                try:
                    self.artifact_store.delete_evidence(persisted)
                except (BitScopeError, OSError):
                    pass
            raise
        return ready

    def _execute_transaction_lifecycle(self, ready: ScenarioRun) -> ScenarioRun:
        timestamp = datetime.now(UTC)
        running = ready.checkpoint(state=ScenarioRunState.RUNNING, now=timestamp)
        self.store.save(running, expected_revision=ready.revision)

        try:
            execution = self.lifecycle_service.execute(running, TRANSACTION_LIFECYCLE_SCENARIO)
        except TransactionLifecycleExecutionError as exc:
            return self._fail_lifecycle_execution(running, exc)
        except Exception:
            return self._fail_lifecycle_execution(
                running,
                TransactionLifecycleExecutionError(
                    "prepare_wallet",
                    self._internal_execution_error(),
                ),
            )

        try:
            captured = [
                self.evidence_service.capture(running, record)
                for record in execution.evidence_records
            ]
            verifying = running.checkpoint(
                state=ScenarioRunState.VERIFYING,
                step_results=execution.step_results,
                evidence_references=[item.reference for item in captured],
                now=timestamp,
            )
            self._persist_checkpoint_with_evidence(running, verifying, captured)
        except Exception as exc:
            error = exc if isinstance(exc, BitScopeError) else self._internal_execution_error()
            return self._fail_lifecycle_execution(
                running,
                TransactionLifecycleExecutionError("export_proof", error),
            )

        verification_results = [
            ScenarioStepResult(
                step_id="verify_results",
                status=ScenarioStepResultStatus.COMPLETED,
                started_at=timestamp,
                completed_at=timestamp,
                evidence_ids=[
                    reference.evidence_id
                    for reference in verifying.evidence
                    if reference.evidence_id != "node.context"
                ],
            ),
            ScenarioStepResult(
                step_id="export_proof",
                status=ScenarioStepResultStatus.COMPLETED,
                started_at=timestamp,
                completed_at=timestamp,
                output_refs=["proof.bundle"],
            ),
        ]
        cleaning = verifying.checkpoint(
            state=ScenarioRunState.CLEANING,
            step_results=verification_results,
            assertion_results=execution.assertion_results,
            cleanup_status=CleanupStatus.IN_PROGRESS,
            now=datetime.now(UTC),
        )
        try:
            self.store.save(cleaning, expected_revision=verifying.revision)
        except Exception:
            self._best_effort_cleanup(verifying)
            raise

        try:
            self.lifecycle_service.cleanup(cleaning)
        except Exception as exc:
            error = exc if isinstance(exc, BitScopeError) else self._internal_cleanup_error()
            return self._finish_cleanup_failure(cleaning, error)

        completed_at = datetime.now(UTC)
        cleanup_result = ScenarioStepResult(
            step_id="cleanup",
            status=ScenarioStepResultStatus.COMPLETED,
            started_at=completed_at,
            completed_at=completed_at,
        )
        verified = cleaning.checkpoint(
            state=ScenarioRunState.VERIFIED,
            step_results=[cleanup_result],
            cleanup_status=CleanupStatus.COMPLETED,
            now=completed_at,
        )
        self.store.save(verified, expected_revision=cleaning.revision)
        return verified

    def _fail_lifecycle_execution(
        self,
        running: ScenarioRun,
        execution_error: TransactionLifecycleExecutionError,
    ) -> ScenarioRun:
        timestamp = datetime.now(UTC)
        error = execution_error.cause
        failure_record = self.lifecycle_service.failure_evidence(
            running,
            execution_error.step_id,
            error,
            timestamp,
        )
        captured = self.evidence_service.capture(running, failure_record)
        safe_message = self.evidence_service.redactor.redact(
            error.details.get("rpc_message") if isinstance(error.details.get("rpc_message"), str) else error.message
        )
        failure = ScenarioFailure(
            failure_id=f"failure.{execution_error.step_id}",
            step_id=execution_error.step_id,
            category=self._failure_category(error),
            expected=False,
            code=error.code,
            safe_message=str(safe_message)[:2_000],
            rpc_code=error.details.get("rpc_code") if isinstance(error.details.get("rpc_code"), int) else None,
            evidence_ids=[captured.reference.evidence_id],
        )
        failed_step = ScenarioStepResult(
            step_id=execution_error.step_id,
            status=ScenarioStepResultStatus.UNEXPECTED_FAILURE,
            started_at=timestamp,
            completed_at=timestamp,
            evidence_ids=[captured.reference.evidence_id],
            failure=failure,
        )
        cleaning = running.checkpoint(
            state=ScenarioRunState.CLEANING,
            step_results=[failed_step],
            evidence_references=[captured.reference],
            cleanup_status=CleanupStatus.IN_PROGRESS,
            now=timestamp,
        )
        try:
            self._persist_checkpoint_with_evidence(running, cleaning, [captured])
        except Exception:
            self._best_effort_cleanup(running)
            raise
        try:
            self.lifecycle_service.cleanup(cleaning)
        except Exception as exc:
            cleanup_error = exc if isinstance(exc, BitScopeError) else self._internal_cleanup_error()
            return self._finish_cleanup_failure(cleaning, cleanup_error)

        completed_at = datetime.now(UTC)
        cleanup_result = ScenarioStepResult(
            step_id="cleanup",
            status=ScenarioStepResultStatus.COMPLETED,
            started_at=completed_at,
            completed_at=completed_at,
        )
        failed = cleaning.checkpoint(
            state=ScenarioRunState.FAILED,
            step_results=[cleanup_result],
            cleanup_status=CleanupStatus.COMPLETED,
            now=completed_at,
        )
        self.store.save(failed, expected_revision=cleaning.revision)
        return failed

    def _finish_cleanup_failure(self, cleaning: ScenarioRun, error: BitScopeError) -> ScenarioRun:
        timestamp = datetime.now(UTC)
        safe_message = self.evidence_service.redactor.redact(
            error.details.get("rpc_message") if isinstance(error.details.get("rpc_message"), str) else error.message
        )
        failure = ScenarioFailure(
            failure_id="failure.cleanup",
            step_id="cleanup",
            category=self._failure_category(error),
            expected=False,
            code=error.code,
            safe_message=str(safe_message)[:2_000],
            rpc_code=error.details.get("rpc_code") if isinstance(error.details.get("rpc_code"), int) else None,
        )
        cleanup_result = ScenarioStepResult(
            step_id="cleanup",
            status=ScenarioStepResultStatus.UNEXPECTED_FAILURE,
            started_at=timestamp,
            completed_at=timestamp,
            failure=failure,
        )
        failed = cleaning.checkpoint(
            state=ScenarioRunState.CLEANUP_FAILED,
            step_results=[cleanup_result],
            cleanup_status=CleanupStatus.FAILED,
            now=timestamp,
        )
        self.store.save(failed, expected_revision=cleaning.revision)
        return failed

    def _persist_checkpoint_with_evidence(
        self,
        previous: ScenarioRun,
        checkpoint: ScenarioRun,
        captured: list[CapturedEvidence],
    ) -> None:
        persisted = [replace(item, run=checkpoint) for item in captured]
        created: list[CapturedEvidence] = []
        try:
            for item in persisted:
                if self.artifact_store.write_evidence(item):
                    created.append(item)
            self.store.save(checkpoint, expected_revision=previous.revision)
        except Exception:
            for item in created:
                try:
                    self.artifact_store.delete_evidence(item)
                except (BitScopeError, OSError):
                    pass
            raise

    @staticmethod
    def _failure_category(error: BitScopeError) -> FailureCategory:
        if error.code in {"BITCOIN_NETWORK_MISMATCH", "REGTEST_ONLY", "BITCOIN_CHAIN_UNVERIFIED"}:
            return FailureCategory.RUNTIME_NETWORK_SAFETY
        if error.code in {"INVALID_RPC_PARAMETER", "RPC_CAPABILITY_VIOLATION"}:
            return FailureCategory.RPC_PARAMETER
        if error.code in {"TRANSACTION_REJECTED", "TRANSACTION_REJECTED_BY_POLICY"}:
            return FailureCategory.MEMPOOL_POLICY
        if error.code.startswith("SCENARIO_") or error.code.startswith("LAB_"):
            return FailureCategory.BITSCOPE_VALIDATION
        return FailureCategory.UNEXPECTED_APPLICATION

    def _best_effort_cleanup(self, run: ScenarioRun) -> None:
        try:
            self.lifecycle_service.cleanup(run)
        except Exception:
            pass

    @staticmethod
    def _internal_execution_error() -> BitScopeError:
        return BitScopeError(
            code="SCENARIO_EXECUTION_INTERNAL_ERROR",
            message="The transaction lifecycle stopped because of an unexpected internal error.",
            status_code=500,
        )

    @staticmethod
    def _internal_cleanup_error() -> BitScopeError:
        return BitScopeError(
            code="SCENARIO_CLEANUP_INTERNAL_ERROR",
            message="The transaction lifecycle could not complete isolated-wallet cleanup.",
            status_code=500,
        )

    @staticmethod
    def _execution_not_available(run: ScenarioRun) -> BitScopeError:
        return BitScopeError(
            code="SCENARIO_EXECUTION_NOT_AVAILABLE",
            message="No reviewed executor is available for this scenario state and version.",
            status_code=409,
            details={"run_id": str(run.run_id), "state": run.current_state.value},
        )

    def reset(self, run_id: UUID, lab_session_id: str, expected_revision: int) -> ScenarioRun:
        previous = self.get_run(run_id, lab_session_id)
        self._require_revision(previous, expected_revision)
        if not self._can_discard(previous):
            raise self._cleanup_required(previous)

        definition = self.catalog.require_version(previous.scenario_id, previous.scenario_version)
        NetworkSafetyGuard(self.rpc).require_regtest()
        replacement = ScenarioRun.create(
            definition,
            lab_session_id,
            bitcoin_core_version=self._bitcoin_core_version(),
        )
        self.store.create(replacement)
        return replacement

    def delete(self, run_id: UUID, lab_session_id: str, expected_revision: int) -> bool:
        run = self.get_run(run_id, lab_session_id)
        self._require_revision(run, expected_revision)
        if not self._can_discard(run):
            raise self._cleanup_required(run)
        deleted = self.store.delete(run_id, lab_session_id)
        if deleted:
            self.artifact_store.delete_run(run)
        return deleted

    def _bitcoin_core_version(self) -> str | None:
        info = self.rpc.get_network_info()
        if not isinstance(info, dict):
            return None
        return self._bitcoin_core_version_from(info)

    @staticmethod
    def _bitcoin_core_version_from(info: dict[str, object]) -> str | None:
        subversion = info.get("subversion")
        if isinstance(subversion, str) and subversion:
            return subversion[:120]
        version = info.get("version")
        return str(version) if isinstance(version, int) else None

    @staticmethod
    def _invalid_readiness_response(rpc_method: str) -> BitScopeError:
        return BitScopeError(
            code="BITCOIN_CORE_INVALID_RESPONSE",
            message="Bitcoin Core returned invalid node-readiness evidence.",
            status_code=502,
            details={"rpc_method": rpc_method},
        )

    @staticmethod
    def _require_revision(run: ScenarioRun, expected_revision: int) -> None:
        if run.revision != expected_revision:
            raise BitScopeError(
                code="SCENARIO_RUN_REVISION_CONFLICT",
                message="The scenario run changed after it was loaded. Reload it before trying again.",
                status_code=409,
                details={
                    "run_id": str(run.run_id),
                    "expected_revision": expected_revision,
                    "actual_revision": run.revision,
                },
            )

    @staticmethod
    def _can_discard(run: ScenarioRun) -> bool:
        if run.current_state in {ScenarioRunState.CREATED, ScenarioRunState.READY}:
            return True
        return run.current_state in TERMINAL_RUN_STATES and run.cleanup_status == CleanupStatus.COMPLETED

    @staticmethod
    def _cleanup_required(run: ScenarioRun) -> BitScopeError:
        return BitScopeError(
            code="SCENARIO_RUN_CLEANUP_REQUIRED",
            message="This scenario run must complete cleanup before it can be reset or deleted.",
            status_code=409,
            details={
                "run_id": str(run.run_id),
                "state": run.current_state.value,
                "cleanup_status": run.cleanup_status.value,
            },
        )
