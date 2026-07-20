from __future__ import annotations

import json
import os
import shutil
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.errors import BitScopeError
from app.models.evidence import CapturedEvidence, EvidenceRecord
from app.models.scenario import EvidenceReference, ScenarioRun


class ScenarioArtifactStore:
    """Store redacted evidence beneath server-generated, run-scoped paths."""

    def __init__(self, artifact_root: str, max_evidence_bytes: int = 1_048_576) -> None:
        if max_evidence_bytes < 1_024:
            raise ValueError("Evidence artifact limits must be at least 1024 bytes.")
        self.root = Path(artifact_root).resolve()
        self.max_evidence_bytes = max_evidence_bytes

    def write_evidence(self, captured: CapturedEvidence) -> bool:
        reference = captured.reference
        expected_path = self._expected_evidence_path(reference)
        if reference.relative_path != expected_path:
            raise BitScopeError(
                code="EVIDENCE_ARTIFACT_PATH_INVALID",
                message="Evidence artifacts must use the server-generated run path.",
                status_code=409,
                details={"evidence_id": reference.evidence_id},
            )

        content = captured.canonical_json.encode("utf-8")
        self._validate_content(reference, content)
        target = self._resolve_run_path(captured.run, expected_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = self._read_bounded(target, reference.evidence_id)
            if existing == content:
                return False
            raise BitScopeError(
                code="EVIDENCE_ARTIFACT_CONFLICT",
                message="An evidence artifact with this identifier already contains different content.",
                status_code=409,
                details={"evidence_id": reference.evidence_id},
            )

        temporary_name: str | None = None
        created = False
        try:
            with NamedTemporaryFile("wb", dir=target.parent, delete=False) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_name = temporary.name
            try:
                os.link(temporary_name, target)
                created = True
            except FileExistsError:
                existing = self._read_bounded(target, reference.evidence_id)
                if existing != content:
                    raise BitScopeError(
                        code="EVIDENCE_ARTIFACT_CONFLICT",
                        message="An evidence artifact with this identifier already contains different content.",
                        status_code=409,
                        details={"evidence_id": reference.evidence_id},
                    )
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
        return created

    def delete_evidence(self, captured: CapturedEvidence) -> None:
        """Remove only the exact artifact created for a failed metadata commit."""

        reference = captured.reference
        expected_path = self._expected_evidence_path(reference)
        if reference.relative_path != expected_path:
            raise BitScopeError(
                code="EVIDENCE_ARTIFACT_PATH_INVALID",
                message="Refusing to delete an evidence artifact outside its server-generated path.",
                status_code=409,
                details={"evidence_id": reference.evidence_id},
            )
        target = self._resolve_run_path(captured.run, expected_path)
        if not target.exists():
            return
        content = self._read_bounded(target, reference.evidence_id)
        self._validate_content(reference, content)
        target.unlink()

    def delete_run(self, run: ScenarioRun) -> None:
        """Delete only the validated artifact directory owned by one confirmed run."""

        run_root = (self.root / str(run.run_id)).resolve()
        if self.root not in run_root.parents:
            raise self._unsafe_path(run, ".")
        if run_root.exists():
            shutil.rmtree(run_root)

    def read_evidence(self, run: ScenarioRun, reference: EvidenceReference) -> EvidenceRecord:
        expected_path = self._expected_evidence_path(reference)
        if reference.relative_path != expected_path:
            raise BitScopeError(
                code="EVIDENCE_ARTIFACT_PATH_INVALID",
                message="The evidence reference does not use its server-generated path.",
                status_code=409,
                details={"evidence_id": reference.evidence_id},
            )
        target = self._resolve_run_path(run, expected_path)
        if not target.is_file():
            raise BitScopeError(
                code="EVIDENCE_ARTIFACT_MISSING",
                message="A referenced evidence artifact is missing.",
                status_code=409,
                details={"run_id": str(run.run_id), "evidence_id": reference.evidence_id},
            )
        content = self._read_bounded(target, reference.evidence_id)
        self._validate_content(reference, content)
        try:
            record = EvidenceRecord.model_validate_json(content)
        except ValueError as exc:
            raise BitScopeError(
                code="EVIDENCE_ARTIFACT_INVALID",
                message="A referenced evidence artifact is not a valid typed record.",
                status_code=409,
                details={"run_id": str(run.run_id), "evidence_id": reference.evidence_id},
            ) from exc
        canonical = json.dumps(
            record.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8") + b"\n"
        if content != canonical:
            raise BitScopeError(
                code="EVIDENCE_ARTIFACT_NOT_CANONICAL",
                message="A referenced evidence artifact is not in canonical JSON form.",
                status_code=409,
                details={"run_id": str(run.run_id), "evidence_id": reference.evidence_id},
            )
        mismatches = {
            "run_id": str(record.run_id) != str(run.run_id),
            "scenario_id": record.scenario_id != run.scenario_id,
            "scenario_version": record.scenario_version != run.scenario_version,
            "lab_session_id": record.lab_session_id != run.lab_session_id,
            "evidence_id": record.evidence_id != reference.evidence_id,
            "kind": record.kind != reference.kind,
        }
        changed = sorted(field for field, mismatch in mismatches.items() if mismatch)
        if changed:
            raise BitScopeError(
                code="EVIDENCE_ARTIFACT_IDENTITY_MISMATCH",
                message="A stored evidence artifact does not match its owning run and reference.",
                status_code=409,
                details={"run_id": str(run.run_id), "evidence_id": reference.evidence_id, "fields": changed},
            )
        return record

    def list_evidence(self, run: ScenarioRun, max_total_bytes: int = 10_485_760) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        total_bytes = 0
        for reference in sorted(run.evidence, key=lambda item: item.evidence_id):
            record = self.read_evidence(run, reference)
            total_bytes += len(record.model_dump_json().encode("utf-8"))
            if total_bytes > max_total_bytes:
                raise BitScopeError(
                    code="EVIDENCE_COLLECTION_TOO_LARGE",
                    message="The run's evidence exceeds the configured read limit.",
                    status_code=413,
                    details={
                        "run_id": str(run.run_id),
                        "content_bytes": total_bytes,
                        "max_content_bytes": max_total_bytes,
                    },
                )
            records.append(record)
        return records

    @staticmethod
    def _expected_evidence_path(reference: EvidenceReference) -> str:
        return f"evidence/{reference.evidence_id}.json"

    def _resolve_run_path(self, run: ScenarioRun, relative_path: str) -> Path:
        run_root = (self.root / str(run.run_id)).resolve()
        if self.root not in run_root.parents:
            raise self._unsafe_path(run, relative_path)
        candidate = (run_root / relative_path).resolve()
        if run_root not in candidate.parents:
            raise self._unsafe_path(run, relative_path)
        return candidate

    @staticmethod
    def _unsafe_path(run: ScenarioRun, relative_path: str) -> BitScopeError:
        return BitScopeError(
            code="EVIDENCE_ARTIFACT_PATH_INVALID",
            message="Refusing to access an evidence path outside its run directory.",
            status_code=409,
            details={"run_id": str(run.run_id), "relative_path": relative_path},
        )

    def _read_bounded(self, path: Path, evidence_id: str) -> bytes:
        with path.open("rb") as artifact:
            content = artifact.read(self.max_evidence_bytes + 1)
        if len(content) > self.max_evidence_bytes:
            raise BitScopeError(
                code="EVIDENCE_ARTIFACT_TOO_LARGE",
                message="A stored evidence artifact exceeds the configured content limit.",
                status_code=413,
                details={
                    "evidence_id": evidence_id,
                    "content_bytes": len(content),
                    "max_content_bytes": self.max_evidence_bytes,
                },
            )
        return content

    def _validate_content(self, reference: EvidenceReference, content: bytes) -> None:
        if len(content) > self.max_evidence_bytes:
            raise BitScopeError(
                code="EVIDENCE_ARTIFACT_TOO_LARGE",
                message="An evidence artifact exceeds the configured content limit.",
                status_code=413,
                details={
                    "evidence_id": reference.evidence_id,
                    "content_bytes": len(content),
                    "max_content_bytes": self.max_evidence_bytes,
                },
            )
        digest = sha256(content).hexdigest()
        if reference.content_sha256 != digest:
            raise BitScopeError(
                code="EVIDENCE_ARTIFACT_HASH_MISMATCH",
                message="An evidence artifact does not match its recorded SHA-256 hash.",
                status_code=409,
                details={"evidence_id": reference.evidence_id},
            )
