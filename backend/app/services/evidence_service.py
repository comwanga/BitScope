from __future__ import annotations

import json
import re
from hashlib import sha256
from uuid import UUID

from pydantic import JsonValue

from app.config import Settings
from app.errors import BitScopeError
from app.models.evidence import CapturedEvidence, EvidenceRecord
from app.models.scenario import EvidenceReference, ScenarioRun
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_run_store import ScenarioRunStore


REDACTED = "[REDACTED]"

SENSITIVE_KEY_MARKERS = frozenset(
    {
        "authorization",
        "cookie",
        "cookiefile",
        "env",
        "environment",
        "hdseed",
        "mnemonic",
        "passphrase",
        "password",
        "privatekey",
        "privkey",
        "rpcauth",
        "rpcpassword",
        "rpcuser",
        "seed",
        "secret",
        "token",
        "xbitscopetoken",
    }
)

EXTENDED_PRIVATE_KEY_PATTERN = re.compile(r"\b(?:xprv|yprv|zprv|tprv|uprv|vprv)[1-9A-HJ-NP-Za-km-z]{20,}\b")
WIF_PRIVATE_KEY_PATTERN = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])[5KL9c][1-9A-HJ-NP-Za-km-z]{50,51}(?![1-9A-HJ-NP-Za-km-z])")
BASIC_AUTH_PATTERN = re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/=]+")
PRIVATE_KEY_BLOCK_PATTERN = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?-----END [^-\r\n]*PRIVATE KEY-----",
    re.DOTALL,
)


class EvidenceRedactor:
    """Recursively remove credential material while preserving safe protocol data."""

    def __init__(self, sensitive_values: tuple[str, ...] = ()) -> None:
        self.sensitive_values = tuple(
            sorted({value for value in sensitive_values if value and value != REDACTED}, key=len, reverse=True)
        )

    def redact(self, value: JsonValue) -> JsonValue:
        if isinstance(value, dict):
            return {
                key: REDACTED if self._is_sensitive_key(key) else self.redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, str):
            return self._redact_string(value)
        return value

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        normalized = "".join(character for character in key.casefold() if character.isalnum())
        return any(
            normalized == marker or normalized.startswith(marker) or normalized.endswith(marker)
            for marker in SENSITIVE_KEY_MARKERS
        )

    def _redact_string(self, value: str) -> str:
        redacted = PRIVATE_KEY_BLOCK_PATTERN.sub(REDACTED, value)
        redacted = EXTENDED_PRIVATE_KEY_PATTERN.sub(REDACTED, redacted)
        redacted = WIF_PRIVATE_KEY_PATTERN.sub(REDACTED, redacted)
        redacted = BASIC_AUTH_PATTERN.sub(REDACTED, redacted)
        for secret in self.sensitive_values:
            if redacted == secret:
                return REDACTED
            if len(secret) >= 4:
                redacted = redacted.replace(secret, REDACTED)
            else:
                redacted = re.sub(
                    rf"(?<![A-Za-z0-9]){re.escape(secret)}(?![A-Za-z0-9])",
                    REDACTED,
                    redacted,
                )
        return redacted


class EvidenceService:
    """Validate, redact, canonicalize, and attach evidence metadata to a run."""

    def __init__(self, redactor: EvidenceRedactor, max_content_bytes: int = 1_048_576) -> None:
        if max_content_bytes < 1_024:
            raise ValueError("Evidence content limits must be at least 1024 bytes.")
        self.redactor = redactor
        self.max_content_bytes = max_content_bytes

    @classmethod
    def from_settings(cls, settings: Settings, max_content_bytes: int = 1_048_576) -> EvidenceService:
        return cls(
            EvidenceRedactor(
                (
                    settings.bitcoin_rpc_user,
                    settings.bitcoin_rpc_password,
                    settings.bitscope_local_access_token,
                )
            ),
            max_content_bytes=max_content_bytes,
        )

    def capture(self, run: ScenarioRun, record: EvidenceRecord) -> CapturedEvidence:
        mismatches = self._identity_mismatches(run, record)
        if mismatches:
            raise BitScopeError(
                code="EVIDENCE_RUN_IDENTITY_MISMATCH",
                message="Evidence identity must match the scenario run that owns it.",
                status_code=409,
                details={"run_id": str(run.run_id), "mismatched_fields": mismatches},
            )
        if record.step_id is not None and record.step_id not in run.defined_step_ids:
            raise BitScopeError(
                code="EVIDENCE_STEP_NOT_FOUND",
                message="Evidence cannot reference a step outside its scenario run.",
                status_code=409,
                details={"run_id": str(run.run_id), "step_id": record.step_id},
            )

        safe_record = EvidenceRecord.model_validate(self._redact_record_document(record))
        canonical_json = json.dumps(
            safe_record.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ) + "\n"
        content = canonical_json.encode("utf-8")
        if len(content) > self.max_content_bytes:
            raise BitScopeError(
                code="EVIDENCE_CONTENT_TOO_LARGE",
                message="The redacted evidence record exceeds the configured content limit.",
                status_code=413,
                details={
                    "evidence_id": record.evidence_id,
                    "content_bytes": len(content),
                    "max_content_bytes": self.max_content_bytes,
                },
            )

        reference = EvidenceReference(
            evidence_id=safe_record.evidence_id,
            kind=safe_record.kind,
            label=safe_record.label,
            relative_path=f"evidence/{safe_record.evidence_id}.json",
            content_sha256=sha256(content).hexdigest(),
        )
        updated_run = run.record_evidence_reference(reference, now=safe_record.captured_at)
        return CapturedEvidence(
            run=updated_run,
            reference=reference,
            record=safe_record,
            canonical_json=canonical_json,
        )

    @staticmethod
    def _identity_mismatches(run: ScenarioRun, record: EvidenceRecord) -> list[str]:
        pairs = {
            "run_id": (run.run_id, record.run_id),
            "scenario_id": (run.scenario_id, record.scenario_id),
            "scenario_version": (run.scenario_version, record.scenario_version),
            "lab_session_id": (run.lab_session_id, record.lab_session_id),
        }
        return [field_name for field_name, (expected, submitted) in pairs.items() if expected != submitted]

    def _redact_record_document(self, record: EvidenceRecord) -> dict[str, object]:
        """Redact content fields without rewriting trusted identity or schema fields."""

        document = record.model_dump(mode="json")
        document["label"] = self.redactor.redact(document["label"])

        core_output = document.get("core_output")
        if isinstance(core_output, dict):
            core_output["safe_parameters"] = self.redactor.redact(core_output.get("safe_parameters"))
            core_output["result"] = self.redactor.redact(core_output.get("result"))
            error = core_output.get("error")
            if isinstance(error, dict):
                error["message"] = self.redactor.redact(error.get("message"))

        interpretation = document["bitscope_interpretation"]
        if isinstance(interpretation, dict):
            interpretation["summary"] = self.redactor.redact(interpretation["summary"])
            interpretation["limitations"] = self.redactor.redact(interpretation.get("limitations", []))
            facts = interpretation.get("facts", [])
            if isinstance(facts, list):
                for fact in facts:
                    if isinstance(fact, dict):
                        fact["value"] = self.redactor.redact(fact.get("value"))

        commands = document.get("commands", [])
        if isinstance(commands, list):
            for command in commands:
                if isinstance(command, dict):
                    command["arguments"] = self.redactor.redact(command.get("arguments", []))
                    command["description"] = self.redactor.redact(command.get("description"))
        return document


class ScenarioEvidenceRecorder:
    """Persist redacted content before committing its reference to the run."""

    def __init__(
        self,
        evidence_service: EvidenceService,
        artifact_store: ScenarioArtifactStore,
        run_store: ScenarioRunStore,
    ) -> None:
        self.evidence_service = evidence_service
        self.artifact_store = artifact_store
        self.run_store = run_store

    def record(
        self,
        run_id: UUID,
        lab_session_id: str,
        expected_revision: int,
        record: EvidenceRecord,
    ) -> CapturedEvidence:
        run = self.run_store.get_for_session(run_id, lab_session_id)
        if run is None:
            raise BitScopeError(
                code="SCENARIO_RUN_NOT_FOUND",
                message="The requested scenario run does not exist.",
                status_code=404,
                details={"run_id": str(run_id)},
            )
        if run.revision != expected_revision:
            raise BitScopeError(
                code="SCENARIO_RUN_REVISION_CONFLICT",
                message="The scenario run changed after it was loaded. Reload it before recording evidence.",
                status_code=409,
                details={
                    "run_id": str(run_id),
                    "expected_revision": expected_revision,
                    "actual_revision": run.revision,
                },
            )

        captured = self.evidence_service.capture(run, record)
        created = self.artifact_store.write_evidence(captured)
        try:
            self.run_store.save(captured.run, expected_revision=expected_revision)
        except Exception:
            if created:
                try:
                    self.artifact_store.delete_evidence(captured)
                except (BitScopeError, OSError):
                    pass
            raise
        return captured
