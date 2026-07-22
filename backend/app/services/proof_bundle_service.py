from __future__ import annotations

import io
import json
import re
import shlex
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Literal
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from app.errors import BitScopeError
from app.models.evidence import EvidenceRecord
from app.models.lifecycle import TransactionLifecycleTimeline
from app.models.proof import (
    ProofBundle,
    ProofFileManifestEntry,
    ProofManifest,
    ScenarioEvidenceResponse,
    SpendabilityCheckStatus,
    TreasuryProofOfSpendability,
    TreasuryProofPolicy,
    TreasurySpendabilityCheck,
)
from app.models.scenario import (
    AssertionResultStatus,
    CleanupStatus,
    EvidenceKind,
    ScenarioDefinition,
    ScenarioFailure,
    ScenarioFinalResult,
    ScenarioRun,
)
from app.models.treasury import MaterializedTreasuryPolicy
from app.services.evidence_service import EvidenceRedactor
from app.services.lifecycle_recorder import LifecycleRecorder
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_catalog import ScenarioCatalog
from app.services.scenario_run_store import ScenarioRunStore


JSON_MEDIA_TYPE = "application/json"
MARKDOWN_MEDIA_TYPE = "text/markdown; charset=utf-8"
SHELL_MEDIA_TYPE = "text/x-shellscript; charset=utf-8"
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


class ProofBundleService:
    """Read verified artifacts and render deterministic, ownership-scoped exports."""

    def __init__(
        self,
        run_store: ScenarioRunStore,
        artifact_store: ScenarioArtifactStore,
        catalog: ScenarioCatalog,
        redactor: EvidenceRedactor | None = None,
        max_bundle_bytes: int = 10_485_760,
    ) -> None:
        if max_bundle_bytes < 1_024:
            raise ValueError("Proof bundle limits must be at least 1024 bytes.")
        self.run_store = run_store
        self.artifact_store = artifact_store
        self.catalog = catalog
        self.redactor = redactor or EvidenceRedactor()
        self.max_bundle_bytes = max_bundle_bytes
        self.lifecycle_recorder = LifecycleRecorder(self.redactor)

    def evidence(self, run_id: UUID, lab_session_id: str) -> ScenarioEvidenceResponse:
        run = self._get_run(run_id, lab_session_id)
        return ScenarioEvidenceResponse(
            run_id=run.run_id,
            revision=run.revision,
            evidence=self.artifact_store.list_evidence(run, self.max_bundle_bytes),
        )

    def report(self, run_id: UUID, lab_session_id: str) -> str:
        run = self._get_run(run_id, lab_session_id)
        definition = self.catalog.get_version(run.scenario_id, run.scenario_version)
        records = self.artifact_store.list_evidence(run, self.max_bundle_bytes)
        safe_run = self._redact_run(run)
        proof = self._proof_of_spendability(safe_run, records)
        if proof is not None:
            return self._render_proof_of_spendability(proof)
        return self._render_report(definition, safe_run, records)

    def lifecycle(self, run_id: UUID, lab_session_id: str) -> TransactionLifecycleTimeline:
        run = self._get_run(run_id, lab_session_id)
        records = self.artifact_store.list_evidence(run, self.max_bundle_bytes)
        return self.lifecycle_recorder.timeline(self._redact_run(run), records)

    def bundle(self, run_id: UUID, lab_session_id: str) -> ProofBundle:
        run = self._get_run(run_id, lab_session_id)
        definition = self.catalog.get_version(run.scenario_id, run.scenario_version)
        records = self.artifact_store.list_evidence(run, self.max_bundle_bytes)
        safe_run = self._redact_run(run)
        proof = self._proof_of_spendability(safe_run, records)
        report = (
            self._render_proof_of_spendability(proof)
            if proof is not None
            else self._render_report(definition, safe_run, records)
        )
        files = self._bundle_files(definition, safe_run, records, report, proof)
        self._require_bundle_size(files)

        entries = [
            ProofFileManifestEntry(
                path=path,
                content_sha256=sha256(content).hexdigest(),
                content_bytes=len(content),
                media_type=self._media_type(path),
            )
            for path, content in sorted(files.items())
        ]
        manifest = ProofManifest(
            scenario_id=run.scenario_id,
            scenario_version=run.scenario_version,
            run_id=run.run_id,
            lab_session_id=run.lab_session_id,
            generated_from_revision=run.revision,
            generated_at=run.updated_at,
            run_state=run.current_state,
            final_result=run.final_result,
            files=entries,
        )
        files["manifest.json"] = self._canonical_json(manifest.model_dump(mode="json"))
        self._require_bundle_size(files)
        ordered_files = dict(sorted(files.items()))
        zip_bytes = self._build_zip(ordered_files)
        if len(zip_bytes) > self.max_bundle_bytes:
            raise self._bundle_too_large(len(zip_bytes))
        return ProofBundle(
            manifest=manifest,
            report_markdown=report,
            proof_of_spendability=proof,
            files=ordered_files,
            zip_bytes=zip_bytes,
        )

    def _redact_run(self, run: ScenarioRun) -> ScenarioRun:
        document = run.model_dump(mode="json")
        for result in document["step_results"]:
            failure = result.get("failure")
            if isinstance(failure, dict):
                failure["safe_message"] = self.redactor.redact(failure["safe_message"])
        for result in document["assertion_results"]:
            result["explanation"] = self.redactor.redact(result["explanation"])
        for collection in ("expected_failures", "unexpected_failures"):
            for failure in document[collection]:
                failure["safe_message"] = self.redactor.redact(failure["safe_message"])
                failure["raw_safe_details"] = self.redactor.redact(
                    failure.get("raw_safe_details")
                )
        for reference in document["evidence"]:
            reference["label"] = self.redactor.redact(reference["label"])
        return ScenarioRun.model_validate(document)

    def _get_run(self, run_id: UUID, lab_session_id: str) -> ScenarioRun:
        run = self.run_store.get_for_session(run_id, lab_session_id)
        if run is None:
            raise BitScopeError(
                code="SCENARIO_RUN_NOT_FOUND",
                message="The requested scenario run does not exist.",
                status_code=404,
                details={"run_id": str(run_id)},
            )
        return run

    def _bundle_files(
        self,
        definition: ScenarioDefinition,
        run: ScenarioRun,
        records: list[EvidenceRecord],
        report: str,
        proof_of_spendability: TreasuryProofOfSpendability | None,
    ) -> dict[str, bytes]:
        files: dict[str, bytes] = {
            "scenario.json": self._canonical_json(definition.model_dump(mode="json")),
            "run.json": self._canonical_json(run.model_dump(mode="json")),
            "report.md": report.encode("utf-8"),
        }
        if proof_of_spendability is not None:
            files["proof-of-spendability.json"] = self._canonical_json(
                proof_of_spendability.model_dump(mode="json")
            )
        lifecycle = self.lifecycle_recorder.timeline(run, records)
        if lifecycle.events:
            files["lifecycle.json"] = self._canonical_json(
                lifecycle.model_dump(mode="json")
            )
        for record in records:
            path = f"evidence/{record.evidence_id}.json"
            self._require_safe_bundle_path(path)
            files[path] = self._canonical_json(record.model_dump(mode="json"))

        commands = [command for record in records for command in record.commands]
        if commands:
            rendered = ["#!/usr/bin/env sh", "set -eu", ""]
            for command in commands:
                rendered.append(f"# {command.description}")
                rendered.append(shlex.join([command.executable, *command.arguments]))
            files["commands.sh"] = ("\n".join(rendered) + "\n").encode("utf-8")

        rpc_records = [record for record in records if record.core_output is not None]
        if rpc_records:
            files["rpc-transcript.json"] = self._canonical_json(
                [
                    {
                        "evidence_id": record.evidence_id,
                        "captured_at": record.captured_at.isoformat(),
                        "core_output": record.core_output.model_dump(mode="json"),
                    }
                    for record in rpc_records
                ]
            )

        node_records = [record for record in records if record.kind == EvidenceKind.NODE_CONTEXT]
        if node_records:
            files["node-context.json"] = self._canonical_json(
                [record.model_dump(mode="json") for record in node_records]
            )

        assertion_records = [record for record in records if record.kind == EvidenceKind.ASSERTION]
        if run.assertion_results or assertion_records:
            files["assertions.json"] = self._canonical_json(
                {
                    "results": [result.model_dump(mode="json") for result in run.assertion_results],
                    "evidence": [record.model_dump(mode="json") for record in assertion_records],
                }
            )
        return files

    def _proof_of_spendability(
        self,
        run: ScenarioRun,
        records: list[EvidenceRecord],
    ) -> TreasuryProofOfSpendability | None:
        if run.scenario_id != "community-treasury-recovery":
            return None

        assertions = {result.assertion_id: result for result in run.assertion_results}
        failures = {failure.code: failure for failure in run.expected_failures}

        def check(
            check_id: str,
            label: str,
            assertion_ids: tuple[str, ...],
            expected_failure_code: str | None = None,
        ) -> TreasurySpendabilityCheck:
            results = [assertions.get(assertion_id) for assertion_id in assertion_ids]
            assertions_passed = all(
                result is not None and result.status == AssertionResultStatus.PASSED
                for result in results
            )
            failure_observed = expected_failure_code is None or expected_failure_code in failures
            passed = assertions_passed and failure_observed
            if not passed:
                status = SpendabilityCheckStatus.FAIL
            elif expected_failure_code is not None:
                status = SpendabilityCheckStatus.REJECTED_AS_EXPECTED
            else:
                status = SpendabilityCheckStatus.PASS
            evidence_ids = sorted(
                {
                    evidence_id
                    for result in results
                    if result is not None
                    for evidence_id in result.evidence_ids
                }
            )
            if expected_failure_code is not None and expected_failure_code in failures:
                evidence_ids = sorted(
                    set(evidence_ids) | set(failures[expected_failure_code].evidence_ids)
                )
            return TreasurySpendabilityCheck(
                check_id=check_id,
                label=label,
                status=status,
                assertion_ids=list(assertion_ids),
                expected_failure_code=expected_failure_code,
                evidence_ids=evidence_ids,
            )

        checks = [
            check(
                "immediate.spend",
                "Normal 2-of-3 operator spend",
                ("immediate_threshold_met", "immediate_accepted", "immediate_confirmed"),
            ),
            check(
                "immediate.insufficient-signatures",
                "Insufficient operator signature attempt",
                ("immediate_insufficient", "immediate_psbt_incomplete", "immediate_threshold_not_met"),
                "insufficient-immediate-signatures",
            ),
            check(
                "recovery.insufficient-signatures",
                "Insufficient recovery signature attempt",
                ("recovery_insufficient", "recovery_psbt_incomplete", "recovery_threshold_not_met"),
                "insufficient-recovery-signatures",
            ),
            check(
                "recovery.premature",
                "Premature recovery attempt",
                ("premature_recovery_rejected", "recovery_timelock_immature"),
                "non-BIP68-final",
            ),
            check(
                "recovery.incorrect-sequence",
                "Incorrect recovery sequence",
                ("wrong_sequence_incomplete",),
                "incorrect-sequence-incomplete",
            ),
            check(
                "recovery.mature-spend",
                "Mature recovery path",
                (
                    "recovery_threshold_met",
                    "recovery_timelock_mature",
                    "recovery_accepted",
                    "recovery_confirmed",
                ),
            ),
            check(
                "emergency.insufficient-signatures",
                "Insufficient emergency signature attempt",
                ("emergency_insufficient", "emergency_psbt_incomplete", "emergency_threshold_not_met"),
                "insufficient-emergency-signatures",
            ),
            check(
                "emergency.premature",
                "Premature emergency attempt",
                ("premature_emergency_rejected", "emergency_timelock_immature"),
                "non-BIP68-final-emergency",
            ),
            check(
                "emergency.mature-spend",
                "Mature emergency path",
                (
                    "emergency_threshold_met",
                    "emergency_timelock_mature",
                    "emergency_accepted",
                    "emergency_confirmed",
                ),
            ),
        ]
        cleanup_passed = run.cleanup_status == CleanupStatus.COMPLETED
        checks.append(
            TreasurySpendabilityCheck(
                check_id="cleanup",
                label="Session-owned cleanup",
                status=(
                    SpendabilityCheckStatus.PASS
                    if cleanup_passed
                    else SpendabilityCheckStatus.FAIL
                ),
            )
        )

        materialized = self._materialized_treasury_policy(records)
        policy = None
        if materialized is not None:
            policy = TreasuryProofPolicy(
                descriptor=materialized.normalized_descriptor,
                address=materialized.address,
                recovery_delay_blocks=materialized.policy.recovery_delay_blocks,
                emergency_delay_blocks=materialized.policy.emergency_delay_blocks,
                decision_tree=materialized.decision_tree,
            )
        core_compatible = self._is_core_28_1(run.bitcoin_core_version)
        all_checks_passed = all(check.status != SpendabilityCheckStatus.FAIL for check in checks)
        verified = (
            run.final_result == ScenarioFinalResult.VERIFIED
            and cleanup_passed
            and all_checks_passed
            and core_compatible
            and policy is not None
        )
        if verified:
            result: Literal["VERIFIED", "INCOMPLETE", "FAILED"] = "VERIFIED"
        elif run.final_result in {ScenarioFinalResult.FAILED, ScenarioFinalResult.CLEANUP_FAILED}:
            result = "FAILED"
        else:
            result = "INCOMPLETE"

        return TreasuryProofOfSpendability(
            scenario_version=run.scenario_version,
            run_id=run.run_id,
            lab_session_id=run.lab_session_id,
            generated_at=run.updated_at,
            result=result,
            bitcoin_core_version=run.bitcoin_core_version,
            bitcoin_core_compatibility="verified" if core_compatible else "unverified",
            policy=policy,
            checks=checks,
            cleanup_status=run.cleanup_status.value,
            evidence_ids=sorted(record.evidence_id for record in records),
            limitations=[
                "All participant wallets are controlled by one local Bitcoin Core process and one BitScope lab session.",
                "The proof demonstrates regtest policy spendability, not independent custody, hardware-wallet isolation, or production safety.",
                "The five-block and ten-block delays are bounded demonstration values, not production recommendations.",
                "This report is reproducible evidence, not a signature, audit, attestation, or spend approval.",
            ],
        )

    @staticmethod
    def _materialized_treasury_policy(
        records: list[EvidenceRecord],
    ) -> MaterializedTreasuryPolicy | None:
        record = next(
            (record for record in records if record.evidence_id == "treasury.policy"),
            None,
        )
        result = record.core_output.result if record is not None and record.core_output is not None else None
        policy = result.get("policy") if isinstance(result, dict) else None
        if not isinstance(policy, dict):
            return None
        try:
            return MaterializedTreasuryPolicy.model_validate(policy)
        except ValueError:
            return None

    @staticmethod
    def _is_core_28_1(version: str | None) -> bool:
        return isinstance(version, str) and (
            version == "280100"
            or re.fullmatch(r"/Satoshi:28\.1(?:\.0)?/", version) is not None
        )

    @staticmethod
    def _render_proof_of_spendability(proof: TreasuryProofOfSpendability) -> str:
        lines = [
            "# Proof of Spendability: Community Treasury Recovery",
            "",
            f"Scenario: {proof.scenario}",
            f"Result: {proof.result}",
            "",
            f"Runtime network: {proof.runtime_network}",
            f"Bitcoin Core: {proof.bitcoin_core_version or 'unknown'}",
            f"Bitcoin Core compatibility: {proof.bitcoin_core_compatibility}",
            "",
            "## Policy",
            "",
        ]
        if proof.policy is None:
            lines.append("The public treasury policy was not available in the captured evidence.")
        else:
            lines.extend(
                [
                    f"- Script type: `{proof.policy.script_type}`",
                    f"- Treasury address: `{proof.policy.address}`",
                    f"- Recovery delay: `{proof.policy.recovery_delay_blocks}` blocks",
                    f"- Emergency delay: `{proof.policy.emergency_delay_blocks}` blocks",
                    f"- Public descriptor: `{proof.policy.descriptor}`",
                    "",
                    "### Decision tree",
                    "",
                    proof.policy.decision_tree.root_label,
                    *[
                        (
                            f"- {branch.path.value}: {branch.required_signatures}-of-{len(branch.participant_ids)}"
                            + (
                                f" after {branch.relative_delay_blocks} blocks"
                                if branch.relative_delay_blocks is not None
                                else " immediately"
                            )
                        )
                        for branch in proof.policy.decision_tree.branches
                    ],
                ]
            )
        lines.extend(["", "## Spendability checks", ""])
        lines.extend(
            f"- {check.label}: **{check.status.value.replace('_', ' ')}**"
            for check in proof.checks
        )
        lines.extend(
            [
                "",
                "## Cleanup",
                "",
                f"Cleanup: **{proof.cleanup_status.upper().replace('_', ' ')}**",
                "",
                "## Educational signer model and limitations",
                "",
                f"Signer model: {proof.signer_model}.",
                *[f"- {limitation}" for limitation in proof.limitations],
                "",
                "## Evidence inventory",
                "",
                *[f"- `{evidence_id}`" for evidence_id in proof.evidence_ids],
                "",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def _render_report(
        cls,
        definition: ScenarioDefinition,
        run: ScenarioRun,
        records: list[EvidenceRecord],
    ) -> str:
        overall = run.final_result.value.upper().replace("_", " ") if run.final_result else run.current_state.value.upper()
        lines = [
            f"# BitScope proof report: {definition.name}",
            "",
            "## Scenario objective",
            "",
            definition.summary,
            "",
            "## Runtime context",
            "",
            f"- Scenario: `{run.scenario_id}` version `{run.scenario_version}`",
            f"- Run: `{run.run_id}`",
            f"- Lab session: `{run.lab_session_id}`",
            f"- Runtime network: `{run.runtime_chain}`",
            f"- Bitcoin Core: `{run.bitcoin_core_version or 'unknown'}`",
            f"- Run revision: `{run.revision}`",
            "",
            "## Actions performed",
            "",
        ]
        if run.step_results:
            lines.extend(
                f"- `{result.step_id}`: **{result.status.value.upper().replace('_', ' ')}**"
                for result in run.step_results
            )
        else:
            lines.append("No scenario steps have been recorded.")

        lines.extend(["", "## Assertions", ""])
        if run.assertion_results:
            lines.extend(
                f"- `{result.assertion_id}`: **{result.status.value.upper()}** - {result.explanation}"
                for result in run.assertion_results
            )
        else:
            lines.append("No assertions have been recorded.")

        lines.extend(cls._failure_section("Expected failures", run.expected_failures))
        lines.extend(cls._failure_section("Unexpected failures", run.unexpected_failures))
        lines.extend(["", "## Bitcoin Core output", ""])
        core_records = [record for record in records if record.core_output is not None]
        if core_records:
            lines.extend(
                f"- `{record.evidence_id}`: RPC `{record.core_output.rpc_method or 'not applicable'}`; "
                "see the redacted RPC transcript and evidence record."
                for record in core_records
            )
        else:
            lines.append("No Bitcoin Core output has been captured.")

        lines.extend(["", "## BitScope interpretation", ""])
        if records:
            lines.extend(
                f"- `{record.evidence_id}`: {record.bitscope_interpretation.summary}"
                for record in records
            )
        else:
            lines.append("No BitScope interpretation has been captured.")

        transaction_records = [
            record for record in records if record.kind in {EvidenceKind.TRANSACTION, EvidenceKind.PSBT}
        ]
        lines.extend(["", "## Transaction, script, timelock, and mempool summary", ""])
        if transaction_records:
            lines.extend(f"- `{record.evidence_id}`: {record.label}" for record in transaction_records)
        else:
            lines.append("No transaction-specific evidence has been captured.")

        lines.extend(
            [
                "",
                "## Cleanup result",
                "",
                f"- Cleanup status: **{run.cleanup_status.value.upper().replace('_', ' ')}**",
                "",
                "## Overall status",
                "",
                f"**{overall}**",
                "",
                "## Reproduction instructions",
                "",
            ]
        )
        commands = [command for record in records for command in record.commands]
        if commands:
            lines.append("Run the reviewed commands in `commands.sh` against an isolated regtest node.")
        else:
            lines.append("No reproduction commands have been captured yet.")
        lines.extend(
            [
                "",
                "## Known limitations",
                "",
                "- Generated transaction identifiers, addresses, block hashes, and wallet names can differ on another run.",
                "- This bundle is reproducible BitScope evidence, not a signature, attestation, formal proof, audit, or production approval.",
                "",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _failure_section(title: str, failures: list[ScenarioFailure]) -> list[str]:
        lines = ["", f"## {title}", ""]
        if failures:
            lines.extend(
                f"- `{failure.step_id}` / `{failure.code}`: {failure.safe_message}"
                for failure in failures
            )
        else:
            lines.append(f"No {title.casefold()} were recorded.")
        return lines

    @staticmethod
    def _canonical_json(value: object) -> bytes:
        return (
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
        ).encode("utf-8")

    @staticmethod
    def _media_type(path: str) -> str:
        suffix = PurePosixPath(path).suffix
        if suffix == ".json":
            return JSON_MEDIA_TYPE
        if suffix == ".md":
            return MARKDOWN_MEDIA_TYPE
        if suffix == ".sh":
            return SHELL_MEDIA_TYPE
        return "application/octet-stream"

    @staticmethod
    def _require_safe_bundle_path(path: str) -> None:
        candidate = PurePosixPath(path)
        if "\\" in path or candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
            raise BitScopeError(
                code="PROOF_BUNDLE_PATH_INVALID",
                message="Refusing to export an unsafe proof bundle path.",
                status_code=409,
                details={"path": path},
            )

    def _require_bundle_size(self, files: dict[str, bytes]) -> None:
        size = sum(len(content) for content in files.values())
        if size > self.max_bundle_bytes:
            raise self._bundle_too_large(size)

    def _bundle_too_large(self, size: int) -> BitScopeError:
        return BitScopeError(
            code="PROOF_BUNDLE_TOO_LARGE",
            message="The proof bundle exceeds the configured export limit.",
            status_code=413,
            details={"content_bytes": size, "max_content_bytes": self.max_bundle_bytes},
        )

    @classmethod
    def _build_zip(cls, files: dict[str, bytes]) -> bytes:
        output = io.BytesIO()
        with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for path, content in sorted(files.items()):
                cls._require_safe_bundle_path(path)
                info = ZipInfo(f"bitscope-proof/{path}", date_time=ZIP_EPOCH)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content, compresslevel=9)
        return output.getvalue()
