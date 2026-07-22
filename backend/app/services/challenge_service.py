from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.errors import BitScopeError
from app.models.curriculum import (
    ChallengeCatalogResponse,
    ChallengeDefinition,
    ChallengeEvidenceReference,
    ChallengeHint,
    ChallengeVerificationCheck,
    ChallengeVerificationResult,
)
from app.models.scenario import AssertionResultStatus, CleanupStatus, ScenarioFinalResult
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_run_store import ScenarioRunStore


@dataclass(frozen=True)
class ChallengeSpec:
    definition: ChallengeDefinition
    hints: tuple[str, ...]
    required_assertion_ids: tuple[str, ...]
    required_evidence_ids: tuple[str, ...]
    completion_explanation: str


def _challenge(
    challenge_id: str,
    title: str,
    difficulty: str,
    objective: str,
    allowed_actions: tuple[str, ...],
    relevant_pages: tuple[str, ...],
    scenario_id: str,
    verification_summary: str,
    hints: tuple[str, ...],
    required_assertion_ids: tuple[str, ...],
    required_evidence_ids: tuple[str, ...],
    completion_explanation: str,
) -> ChallengeSpec:
    return ChallengeSpec(
        definition=ChallengeDefinition(
            challenge_id=challenge_id,
            version="1.0.0",
            title=title,
            difficulty=difficulty,
            objective=objective,
            allowed_actions=list(allowed_actions),
            relevant_pages=list(relevant_pages),
            scenario_id=scenario_id,
            hint_count=len(hints),
            verification_summary=verification_summary,
        ),
        hints=hints,
        required_assertion_ids=required_assertion_ids,
        required_evidence_ids=required_evidence_ids,
        completion_explanation=completion_explanation,
    )


CHALLENGES: tuple[ChallengeSpec, ...] = (
    _challenge(
        "signal-opt-in-rbf",
        "Create an opt-in RBF transaction",
        "intermediate",
        "Produce a transaction whose inputs explicitly signal replaceability and prove its policy state through Bitcoin Core.",
        ("Create and run a disposable regtest lab", "Use the reviewed RBF scenario", "Inspect transaction and mempool evidence"),
        ("/tx-control", "/mempool", "/scenarios"),
        "rbf-replacement",
        "A completed run must contain the passed original_signaled_rbf assertion and its persisted original-transaction evidence.",
        (
            "Start by distinguishing an input sequence from a transaction fee.",
            "Inspect the original transaction's decoded input sequences and Core's bip125-replaceable mempool field.",
            "Run the reviewed RBF scenario, then submit its run ID and owning lab session ID here.",
        ),
        ("original_signaled_rbf",),
        ("rbf.original",),
        "Bitcoin Core observed replaceable input signaling and reported the original transaction as BIP125-replaceable in the mempool evidence.",
    ),
    _challenge(
        "replace-rbf-higher-fee",
        "Replace a transaction with a higher fee",
        "intermediate",
        "Replace an opt-in transaction with a distinct higher-fee transaction, prove original eviction, and confirm the replacement.",
        ("Use the reviewed RBF scenario", "Inspect fee and txid evidence", "Mine only on disposable regtest"),
        ("/tx-control", "/mempool", "/fees", "/scenarios"),
        "rbf-replacement",
        "Core-backed assertions must prove original replacement, replacement mempool presence, and confirmation.",
        (
            "A replacement must conflict with the original and pay enough additional fee for local policy.",
            "Compare the original txid with bumpfee's txid, then inspect both mempool lookups.",
            "The reviewed scenario first records an insufficient bump, then applies a higher requested fee rate.",
        ),
        ("original_replaced", "replacement_in_mempool", "replacement_confirmed"),
        ("rbf.replacement", "rbf.confirmed"),
        "The replacement has a distinct transaction ID, Core no longer finds the original in its mempool, and the higher-fee replacement confirms.",
    ),
    _challenge(
        "complete-two-of-three-psbt",
        "Complete a 2-of-3 PSBT",
        "intermediate",
        "Progress from an incomplete one-signature PSBT to a finalized and accepted 2-of-3 spend without exporting private keys.",
        ("Use session-owned regtest wallets", "Use the reviewed multisig PSBT scenario", "Inspect PSBT and final transaction evidence"),
        ("/multisig", "/psbt", "/scenarios"),
        "multisig-psbt",
        "Passed threshold, PSBT completion, mempool acceptance, and confirmation assertions are required.",
        (
            "Keep PSBT signing separate from final extraction so partial signatures remain inspectable.",
            "Check that one signer remains incomplete, then add a different signer before finalizepsbt.",
            "Submit a verified multisig-psbt run after Core has accepted and confirmed the finalized spend.",
        ),
        ("threshold_met", "psbt_complete", "spend_accepted", "spend_confirmed"),
        ("psbt.complete", "multisig.confirmed"),
        "The evidence preserves the incomplete partial state, proves the 2-of-3 threshold, and shows Core accepting and confirming the finalized transaction.",
    ),
    _challenge(
        "prove-premature-cltv-failure",
        "Prove a premature CLTV failure",
        "advanced",
        "Create a correctly signed absolute-height CLTV spend and prove Core rejects it before the recorded maturity height.",
        ("Use the reviewed CLTV scenario", "Inspect locktime and sequence", "Use testmempoolaccept before broadcast"),
        ("/timelocks", "/script-lab", "/scenarios"),
        "cltv-timelock",
        "The premature_rejected and timelock_immature assertions must pass against persisted Core preflight evidence.",
        (
            "A CLTV spend needs both an adequate nLockTime and a non-final input sequence.",
            "Compare the current height with the policy lock height; do not alter the correctly signed transaction between tests.",
            "Submit the completed CLTV scenario whose premature evidence contains Core's reviewed non-final result.",
        ),
        ("premature_rejected", "timelock_immature"),
        ("cltv.premature",),
        "Core rejected the correctly structured spend before its absolute lock height, and the scenario separately proved the unchanged transaction at maturity.",
    ),
    _challenge(
        "diagnose-mempool-rejection",
        "Diagnose a mempool rejection",
        "intermediate",
        "Use Core's structured testmempoolaccept result to identify a value-conservation failure rather than guessing from frontend state.",
        ("Use the transaction lifecycle scenario", "Inspect only redacted Core evidence", "Compare input and output amounts"),
        ("/transactions", "/mempool", "/scenarios"),
        "transaction-lifecycle",
        "The overspend_rejected assertion and transaction.overspend-rejection artifact must be present and valid.",
        (
            "Start with the sum of inputs and outputs, including the implied fee.",
            "Look for allowed=false and the reviewed reject-reason in testmempoolaccept evidence.",
            "Submit a verified transaction-lifecycle run that includes the deliberately one-satoshi overspend.",
        ),
        ("overspend_rejected",),
        ("transaction.overspend-rejection",),
        "Core's preflight evidence identifies the deliberately invalid one-satoshi overspend, and the typed scenario assertion classifies that exact rejection.",
    ),
    _challenge(
        "complete-treasury-recovery",
        "Complete treasury recovery",
        "advanced",
        "Prove the Community Treasury Recovery branch is incomplete below threshold, rejected before its CSV delay, and spendable unchanged after maturity.",
        ("Use the flagship Verified Scenario", "Use public policy and PSBT evidence", "Keep all activity on disposable regtest"),
        ("/scenarios", "/multisig", "/psbt", "/timelocks"),
        "community-treasury-recovery",
        "Recovery threshold, premature rejection, maturity, acceptance, confirmation, and cleanup must all be proved.",
        (
            "Treat signature threshold and relative timelock as independent requirements.",
            "Inspect the recovery sequence and the funding output's confirmation age before the mature preflight.",
            "Submit the verified flagship run after its Proof of Spendability reports the recovery branch and cleanup as successful.",
        ),
        ("recovery_threshold_met", "premature_recovery_rejected", "recovery_timelock_mature", "recovery_accepted", "recovery_confirmed"),
        ("treasury.recovery-partial", "treasury.recovery-premature", "treasury.recovery-mature"),
        "The public policy, threshold signatures, exact premature rejection, recorded CSV maturity, accepted unchanged spend, confirmation, and cleanup jointly prove the recovery path.",
    ),
)


class ChallengeService:
    def __init__(self, run_store: ScenarioRunStore, artifact_store: ScenarioArtifactStore) -> None:
        self.run_store = run_store
        self.artifact_store = artifact_store

    def catalog(self) -> ChallengeCatalogResponse:
        return ChallengeCatalogResponse(
            challenges=[spec.definition for spec in CHALLENGES],
            explanation=(
                "Challenge solutions stay locked until completion. Request hints one at a time, then submit a completed "
                "Verified Scenario run for backend validation against persisted Bitcoin Core evidence."
            ),
        )

    def hint(self, challenge_id: str, level: int) -> ChallengeHint:
        spec = self._spec(challenge_id)
        if level < 1 or level > len(spec.hints):
            raise BitScopeError(
                "CHALLENGE_HINT_NOT_FOUND",
                "That progressive hint level is not available.",
                404,
                {"challenge_id": challenge_id, "hint_count": len(spec.hints)},
            )
        return ChallengeHint(
            challenge_id=challenge_id,
            level=level,
            hint=spec.hints[level - 1],
            remaining_hints=len(spec.hints) - level,
        )

    def verify(self, challenge_id: str, run_id: UUID, lab_session_id: str) -> ChallengeVerificationResult:
        spec = self._spec(challenge_id)
        run = self.run_store.get_for_session(run_id, lab_session_id)
        if run is None:
            raise BitScopeError(
                "SCENARIO_RUN_NOT_FOUND",
                "The scenario run was not found for this lab session.",
                404,
                {"run_id": str(run_id)},
            )
        if run.scenario_id != spec.definition.scenario_id:
            raise BitScopeError(
                "CHALLENGE_SCENARIO_MISMATCH",
                "This challenge requires a different reviewed scenario.",
                409,
                {
                    "challenge_id": challenge_id,
                    "required_scenario_id": spec.definition.scenario_id,
                    "submitted_scenario_id": run.scenario_id,
                },
            )

        records = self.artifact_store.list_evidence(run)
        records_by_id = {record.evidence_id: record for record in records}
        assertions = {result.assertion_id: result for result in run.assertion_results}
        checks: list[ChallengeVerificationCheck] = []

        run_verified = run.final_result == ScenarioFinalResult.VERIFIED
        checks.append(
            ChallengeVerificationCheck(
                check_id="run.verified",
                passed=run_verified,
                explanation=(
                    "The reviewed scenario reached a verified terminal result."
                    if run_verified
                    else "The reviewed scenario has not reached a verified terminal result."
                ),
            )
        )
        cleanup_complete = run.cleanup_status == CleanupStatus.COMPLETED
        checks.append(
            ChallengeVerificationCheck(
                check_id="run.cleanup",
                passed=cleanup_complete,
                explanation=(
                    "Session-owned cleanup completed."
                    if cleanup_complete
                    else "Session-owned cleanup has not completed."
                ),
                evidence_ids=["lifecycle.cleanup"] if "lifecycle.cleanup" in records_by_id else [],
            )
        )
        core_identified = bool(run.bitcoin_core_version) and "node.context" in records_by_id
        checks.append(
            ChallengeVerificationCheck(
                check_id="core.identified",
                passed=core_identified,
                explanation=(
                    f"The run identifies Bitcoin Core {run.bitcoin_core_version} and preserves node context."
                    if core_identified
                    else "The run does not contain both a Bitcoin Core version and node-context evidence."
                ),
                evidence_ids=["node.context"] if "node.context" in records_by_id else [],
            )
        )

        relevant_evidence_ids: set[str] = {"node.context", "lifecycle.cleanup"}
        for assertion_id in spec.required_assertion_ids:
            result = assertions.get(assertion_id)
            passed = result is not None and result.status == AssertionResultStatus.PASSED
            evidence_ids = result.evidence_ids if result is not None else []
            relevant_evidence_ids.update(evidence_ids)
            checks.append(
                ChallengeVerificationCheck(
                    check_id=f"assertion.{assertion_id}",
                    passed=passed,
                    explanation=(
                        f"Scenario assertion {assertion_id} passed using persisted evidence."
                        if passed
                        else f"Scenario assertion {assertion_id} has not passed."
                    ),
                    evidence_ids=evidence_ids,
                )
            )

        for evidence_id in spec.required_evidence_ids:
            present = evidence_id in records_by_id
            relevant_evidence_ids.add(evidence_id)
            checks.append(
                ChallengeVerificationCheck(
                    check_id=f"evidence.{evidence_id}",
                    passed=present,
                    explanation=(
                        f"The canonical {evidence_id} artifact was loaded and identity-checked."
                        if present
                        else f"The required {evidence_id} artifact is absent."
                    ),
                    evidence_ids=[evidence_id] if present else [],
                )
            )

        completed = all(check.passed for check in checks)
        reference_by_id = {reference.evidence_id: reference for reference in run.evidence}
        evidence = [
            ChallengeEvidenceReference(
                evidence_id=evidence_id,
                kind=reference_by_id[evidence_id].kind.value,
                content_sha256=reference_by_id[evidence_id].content_sha256,
            )
            for evidence_id in sorted(relevant_evidence_ids)
            if evidence_id in records_by_id
            and evidence_id in reference_by_id
            and reference_by_id[evidence_id].content_sha256 is not None
        ]
        return ChallengeVerificationResult(
            challenge_id=challenge_id,
            challenge_version=spec.definition.version,
            run_id=run.run_id,
            lab_session_id=run.lab_session_id,
            scenario_id=run.scenario_id,
            scenario_version=run.scenario_version,
            bitcoin_core_version=run.bitcoin_core_version,
            verified_at=run.updated_at,
            completed=completed,
            checks=checks,
            evidence=evidence,
            final_explanation=(
                spec.completion_explanation
                if completed
                else "Completion remains locked because one or more backend scenario, cleanup, Core identity, assertion, or evidence checks have not passed."
            ),
            solution_unlocked=completed,
        )

    @staticmethod
    def _spec(challenge_id: str) -> ChallengeSpec:
        for spec in CHALLENGES:
            if spec.definition.challenge_id == challenge_id:
                return spec
        raise BitScopeError(
            "CHALLENGE_NOT_FOUND",
            "The requested learning challenge does not exist.",
            404,
            {"challenge_id": challenge_id},
        )
