from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from app.errors import BitScopeError
from app.models.evidence import EvidenceRecord
from app.models.scenario import CleanupStatus, ScenarioRun, ScenarioRunState, TERMINAL_RUN_STATES
from app.rpc.capabilities import ReadOnlyRpcClient, RpcTransport
from app.services.evidence_service import EvidenceService
from app.services.network_safety import NetworkSafetyGuard
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_catalog import ScenarioCatalog
from app.services.scenario_run_store import ScenarioRunStore


class ScenarioService:
    """Coordinate safe run preparation without claiming scenario execution."""

    def __init__(
        self,
        rpc_client: RpcTransport,
        store: ScenarioRunStore,
        catalog: ScenarioCatalog,
        evidence_service: EvidenceService,
        artifact_store: ScenarioArtifactStore,
    ) -> None:
        self.rpc = ReadOnlyRpcClient(rpc_client)
        self.store = store
        self.catalog = catalog
        self.evidence_service = evidence_service
        self.artifact_store = artifact_store

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
        if run.current_state != ScenarioRunState.CREATED:
            raise BitScopeError(
                code="SCENARIO_EXECUTION_NOT_AVAILABLE",
                message="Scenario step execution is not available in Phase 1.",
                status_code=409,
                details={"run_id": str(run_id), "state": run.current_state.value},
            )

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
