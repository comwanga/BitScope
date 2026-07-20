from __future__ import annotations

import io
import json
import shlex
from hashlib import sha256
from pathlib import PurePosixPath
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from app.errors import BitScopeError
from app.models.evidence import EvidenceRecord
from app.models.proof import ProofBundle, ProofFileManifestEntry, ProofManifest, ScenarioEvidenceResponse
from app.models.scenario import EvidenceKind, ScenarioDefinition, ScenarioFailure, ScenarioRun
from app.services.evidence_service import EvidenceRedactor
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
        return self._render_report(definition, self._redact_run(run), records)

    def bundle(self, run_id: UUID, lab_session_id: str) -> ProofBundle:
        run = self._get_run(run_id, lab_session_id)
        definition = self.catalog.get_version(run.scenario_id, run.scenario_version)
        records = self.artifact_store.list_evidence(run, self.max_bundle_bytes)
        safe_run = self._redact_run(run)
        report = self._render_report(definition, safe_run, records)
        files = self._bundle_files(definition, safe_run, records, report)
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
    ) -> dict[str, bytes]:
        files: dict[str, bytes] = {
            "scenario.json": self._canonical_json(definition.model_dump(mode="json")),
            "run.json": self._canonical_json(run.model_dump(mode="json")),
            "report.md": report.encode("utf-8"),
        }
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
