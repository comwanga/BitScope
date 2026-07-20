from uuid import UUID

from app.errors import BitScopeError
from app.models.scenario import CleanupStatus, ScenarioRun, ScenarioRunState, TERMINAL_RUN_STATES
from app.rpc.capabilities import ReadOnlyRpcClient, RpcTransport
from app.services.network_safety import NetworkSafetyGuard
from app.services.scenario_catalog import ScenarioCatalog
from app.services.scenario_run_store import ScenarioRunStore


class ScenarioService:
    """Coordinate the safe Phase 1 lifecycle without executing scenario steps."""

    def __init__(
        self,
        rpc_client: RpcTransport,
        store: ScenarioRunStore,
        catalog: ScenarioCatalog,
    ) -> None:
        self.rpc = ReadOnlyRpcClient(rpc_client)
        self.store = store
        self.catalog = catalog

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

        NetworkSafetyGuard(self.rpc).require_regtest()
        ready = run.transition_to(ScenarioRunState.READY)
        self.store.save(ready, expected_revision=expected_revision)
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
        return self.store.delete(run_id, lab_session_id)

    def _bitcoin_core_version(self) -> str | None:
        info = self.rpc.get_network_info()
        if not isinstance(info, dict):
            return None
        subversion = info.get("subversion")
        if isinstance(subversion, str) and subversion:
            return subversion[:120]
        version = info.get("version")
        return str(version) if isinstance(version, int) else None

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
