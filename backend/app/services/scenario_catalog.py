from dataclasses import dataclass

from app.errors import BitScopeError
from app.models.scenario import ScenarioDefinition
from app.models.scenario_api import ScenarioCatalogEntry, ScenarioDetailResponse
from app.services.multisig_psbt_scenario import MULTISIG_PSBT_SCENARIO
from app.services.rbf_scenario import RBF_REPLACEMENT_SCENARIO
from app.services.transaction_lifecycle_scenario import TRANSACTION_LIFECYCLE_SCENARIO


@dataclass(frozen=True)
class RegisteredScenario:
    definition: ScenarioDefinition
    available: bool = True
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if self.available and self.unavailable_reason is not None:
            raise ValueError("An available scenario cannot have an unavailable reason.")
        if not self.available and not self.unavailable_reason:
            raise ValueError("An unavailable scenario requires a reason.")

    def summary(self) -> ScenarioCatalogEntry:
        definition = self.definition
        return ScenarioCatalogEntry(
            scenario_id=definition.scenario_id,
            version=definition.version,
            name=definition.name,
            summary=definition.summary,
            difficulty=definition.difficulty,
            related_lbcli_chapters=definition.related_lbcli_chapters,
            concepts=definition.concepts,
            required_network=definition.required_network,
            estimated_run_steps=definition.estimated_run_steps,
            step_count=len(definition.steps),
            assertion_count=len(definition.assertions),
            available=self.available,
            unavailable_reason=self.unavailable_reason,
        )

    def detail(self) -> ScenarioDetailResponse:
        return ScenarioDetailResponse(
            definition=self.definition,
            available=self.available,
            unavailable_reason=self.unavailable_reason,
        )


class ScenarioCatalog:
    """Immutable registry of reviewed scenario definitions."""

    def __init__(self, entries: tuple[RegisteredScenario, ...] = ()) -> None:
        by_id: dict[str, RegisteredScenario] = {}
        for entry in entries:
            scenario_id = entry.definition.scenario_id
            if scenario_id in by_id:
                raise ValueError(f"Duplicate scenario identifier: {scenario_id}.")
            by_id[scenario_id] = entry
        self._entries = by_id

    def list(self) -> list[ScenarioCatalogEntry]:
        return [self._entries[scenario_id].summary() for scenario_id in sorted(self._entries)]

    def get(self, scenario_id: str) -> RegisteredScenario:
        entry = self._entries.get(scenario_id)
        if entry is None:
            raise BitScopeError(
                code="SCENARIO_NOT_FOUND",
                message="The requested scenario does not exist.",
                status_code=404,
                details={"scenario_id": scenario_id},
            )
        return entry

    def require_available(self, scenario_id: str) -> ScenarioDefinition:
        entry = self.get(scenario_id)
        if not entry.available:
            raise BitScopeError(
                code="SCENARIO_NOT_AVAILABLE",
                message="The requested scenario is not available to run yet.",
                status_code=409,
                details={
                    "scenario_id": scenario_id,
                    "reason": entry.unavailable_reason,
                },
            )
        return entry.definition

    def require_version(self, scenario_id: str, version: str) -> ScenarioDefinition:
        definition = self.require_available(scenario_id)
        return self._require_matching_version(definition, version)

    def get_version(self, scenario_id: str, version: str) -> ScenarioDefinition:
        """Resolve a historical run definition even when new runs are disabled."""

        definition = self.get(scenario_id).definition
        return self._require_matching_version(definition, version)

    @staticmethod
    def _require_matching_version(definition: ScenarioDefinition, version: str) -> ScenarioDefinition:
        if definition.version != version:
            raise BitScopeError(
                code="SCENARIO_VERSION_NOT_AVAILABLE",
                message="The scenario version used by this run is no longer registered.",
                status_code=409,
                details={
                    "scenario_id": definition.scenario_id,
                    "required_version": version,
                    "available_version": definition.version,
                },
            )
        return definition


DEFAULT_SCENARIO_CATALOG = ScenarioCatalog(
    (
        RegisteredScenario(MULTISIG_PSBT_SCENARIO),
        RegisteredScenario(RBF_REPLACEMENT_SCENARIO),
        RegisteredScenario(TRANSACTION_LIFECYCLE_SCENARIO),
    )
)
