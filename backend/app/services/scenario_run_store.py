import sqlite3
from pathlib import Path
from threading import RLock
from uuid import UUID

from app.errors import BitScopeError
from app.models.lab import LabSession
from app.models.scenario import CleanupStatus, ScenarioRun, TERMINAL_RUN_STATES
from app.services.lab_session_store import LabSessionStore


SCHEMA_VERSION = 1


class ScenarioRunStore:
    """Persist scenario runs transactionally beside their owning lab sessions."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        self._lock = RLock()
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        LabSessionStore(database_path)
        with self._lock, self._connect() as connection:
            self._create_schema(connection)

    def create(self, run: ScenarioRun) -> None:
        if run.revision != 0:
            raise BitScopeError(
                code="SCENARIO_RUN_INVALID_REVISION",
                message="A new scenario run must begin at revision zero.",
                status_code=409,
                details={"run_id": str(run.run_id), "revision": run.revision},
            )

        with self._lock, self._connect() as connection:
            self._require_active_lab_session(connection, run.lab_session_id)
            try:
                connection.execute(
                    """
                    INSERT INTO scenario_runs(
                        run_id,
                        lab_session_id,
                        scenario_id,
                        scenario_version,
                        current_state,
                        revision,
                        created_at,
                        updated_at,
                        document
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._run_row(run),
                )
            except sqlite3.IntegrityError as exc:
                raise BitScopeError(
                    code="SCENARIO_RUN_ALREADY_EXISTS",
                    message="A scenario run with this identifier already exists.",
                    status_code=409,
                    details={"run_id": str(run.run_id)},
                ) from exc
            self._replace_child_documents(connection, run)

    def get(self, run_id: UUID | str) -> ScenarioRun | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT document FROM scenario_runs WHERE run_id = ?",
                (str(run_id),),
            ).fetchone()
        return ScenarioRun.model_validate_json(row[0]) if row else None

    def get_for_session(self, run_id: UUID | str, lab_session_id: str) -> ScenarioRun | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT document FROM scenario_runs WHERE run_id = ? AND lab_session_id = ?",
                (str(run_id), lab_session_id),
            ).fetchone()
        return ScenarioRun.model_validate_json(row[0]) if row else None

    def list_for_session(self, lab_session_id: str) -> list[ScenarioRun]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT document
                FROM scenario_runs
                WHERE lab_session_id = ?
                ORDER BY created_at ASC, run_id ASC
                """,
                (lab_session_id,),
            ).fetchall()
        return [ScenarioRun.model_validate_json(row[0]) for row in rows]

    def save(self, run: ScenarioRun, expected_revision: int) -> None:
        if expected_revision < 0 or run.revision != expected_revision + 1:
            raise BitScopeError(
                code="SCENARIO_RUN_INVALID_REVISION",
                message="Scenario run updates must advance exactly one revision.",
                status_code=409,
                details={
                    "run_id": str(run.run_id),
                    "expected_revision": expected_revision,
                    "submitted_revision": run.revision,
                },
            )

        with self._lock, self._connect() as connection:
            existing = connection.execute(
                """
                SELECT lab_session_id, scenario_id, scenario_version, revision, document
                FROM scenario_runs
                WHERE run_id = ?
                """,
                (str(run.run_id),),
            ).fetchone()
            if existing is None:
                raise BitScopeError(
                    code="SCENARIO_RUN_NOT_FOUND",
                    message="The requested scenario run does not exist.",
                    status_code=404,
                    details={"run_id": str(run.run_id)},
                )

            stored_session, stored_scenario, stored_version, stored_revision, stored_document = existing
            if (
                stored_session != run.lab_session_id
                or stored_scenario != run.scenario_id
                or stored_version != run.scenario_version
            ):
                raise BitScopeError(
                    code="SCENARIO_RUN_IDENTITY_MISMATCH",
                    message="A persisted scenario run cannot change its session, scenario, or version.",
                    status_code=409,
                    details={"run_id": str(run.run_id)},
                )
            if stored_revision != expected_revision:
                raise self._revision_conflict(run, expected_revision, int(stored_revision))
            stored_run = ScenarioRun.model_validate_json(stored_document)
            self._validate_update(stored_run, run)

            updated = connection.execute(
                """
                UPDATE scenario_runs
                SET current_state = ?, revision = ?, updated_at = ?, document = ?
                WHERE run_id = ? AND revision = ?
                """,
                (
                    run.current_state.value,
                    run.revision,
                    run.updated_at.isoformat(),
                    run.model_dump_json(),
                    str(run.run_id),
                    expected_revision,
                ),
            )
            if updated.rowcount != 1:
                current = connection.execute(
                    "SELECT revision FROM scenario_runs WHERE run_id = ?",
                    (str(run.run_id),),
                ).fetchone()
                actual_revision = int(current[0]) if current else -1
                raise self._revision_conflict(run, expected_revision, actual_revision)
            self._replace_child_documents(connection, run)

    def delete(self, run_id: UUID | str, lab_session_id: str) -> bool:
        with self._lock, self._connect() as connection:
            deleted = connection.execute(
                "DELETE FROM scenario_runs WHERE run_id = ? AND lab_session_id = ?",
                (str(run_id), lab_session_id),
            )
        return deleted.rowcount == 1

    @staticmethod
    def _run_row(run: ScenarioRun) -> tuple[object, ...]:
        return (
            str(run.run_id),
            run.lab_session_id,
            run.scenario_id,
            run.scenario_version,
            run.current_state.value,
            run.revision,
            run.created_at.isoformat(),
            run.updated_at.isoformat(),
            run.model_dump_json(),
        )

    @staticmethod
    def _replace_child_documents(connection: sqlite3.Connection, run: ScenarioRun) -> None:
        run_id = str(run.run_id)
        for table in (
            "scenario_step_runs",
            "scenario_assertions",
            "scenario_evidence",
            "scenario_failures",
        ):
            connection.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))

        connection.executemany(
            """
            INSERT INTO scenario_step_runs(run_id, step_id, ordinal, status, document)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (run_id, result.step_id, ordinal, result.status.value, result.model_dump_json())
                for ordinal, result in enumerate(run.step_results, start=1)
            ],
        )
        connection.executemany(
            """
            INSERT INTO scenario_assertions(run_id, assertion_id, status, document)
            VALUES (?, ?, ?, ?)
            """,
            [
                (run_id, result.assertion_id, result.status.value, result.model_dump_json())
                for result in run.assertion_results
            ],
        )
        connection.executemany(
            """
            INSERT INTO scenario_evidence(run_id, evidence_id, kind, document)
            VALUES (?, ?, ?, ?)
            """,
            [
                (run_id, reference.evidence_id, reference.kind.value, reference.model_dump_json())
                for reference in run.evidence
            ],
        )
        failures = [*run.expected_failures, *run.unexpected_failures]
        connection.executemany(
            """
            INSERT INTO scenario_failures(run_id, failure_id, expected, category, document)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    failure.failure_id,
                    int(failure.expected),
                    failure.category.value,
                    failure.model_dump_json(),
                )
                for failure in failures
            ],
        )

    @staticmethod
    def _require_active_lab_session(connection: sqlite3.Connection, lab_session_id: str) -> LabSession:
        row = connection.execute(
            "SELECT document FROM lab_sessions WHERE session_id = ?",
            (lab_session_id,),
        ).fetchone()
        if row is None:
            raise BitScopeError(
                code="LAB_SESSION_NOT_FOUND",
                message="A scenario run requires an existing lab session.",
                status_code=404,
                details={"lab_session_id": lab_session_id},
            )
        session = LabSession.model_validate_json(row[0])
        if session.status != "active":
            raise BitScopeError(
                code="LAB_SESSION_NOT_ACTIVE",
                message="A scenario run can only be created for an active lab session.",
                status_code=409,
                details={"lab_session_id": lab_session_id, "status": session.status},
            )
        return session

    @staticmethod
    def _revision_conflict(run: ScenarioRun, expected_revision: int, actual_revision: int) -> BitScopeError:
        return BitScopeError(
            code="SCENARIO_RUN_REVISION_CONFLICT",
            message="The scenario run changed after it was loaded. Reload it before advancing again.",
            status_code=409,
            details={
                "run_id": str(run.run_id),
                "expected_revision": expected_revision,
                "actual_revision": actual_revision,
            },
        )

    @staticmethod
    def _validate_update(stored: ScenarioRun, submitted: ScenarioRun) -> None:
        if stored.current_state in TERMINAL_RUN_STATES:
            raise BitScopeError(
                code="SCENARIO_RUN_TERMINAL",
                message="A terminal scenario run cannot be modified.",
                status_code=409,
                details={"run_id": str(submitted.run_id), "state": stored.current_state.value},
            )

        if submitted.current_state != stored.current_state:
            allowed = ScenarioRun.ALLOWED_TRANSITIONS.get(stored.current_state, frozenset())
            if submitted.current_state not in allowed:
                raise BitScopeError(
                    code="SCENARIO_RUN_INVALID_TRANSITION",
                    message="The submitted scenario run state does not follow the state machine.",
                    status_code=409,
                    details={
                        "run_id": str(submitted.run_id),
                        "current_state": stored.current_state.value,
                        "submitted_state": submitted.current_state.value,
                    },
                )

        immutable_fields = (
            "runtime_chain",
            "bitcoin_core_version",
            "start_state",
            "defined_step_ids",
            "required_assertion_ids",
            "created_at",
        )
        changed_fields = [
            field_name
            for field_name in immutable_fields
            if getattr(stored, field_name) != getattr(submitted, field_name)
        ]
        if changed_fields:
            raise BitScopeError(
                code="SCENARIO_RUN_IDENTITY_MISMATCH",
                message="Persisted scenario run context cannot be rewritten.",
                status_code=409,
                details={"run_id": str(submitted.run_id), "changed_fields": changed_fields},
            )

        append_only_fields = (
            "step_results",
            "assertion_results",
            "expected_failures",
            "unexpected_failures",
            "evidence",
        )
        rewritten = [
            field_name
            for field_name in append_only_fields
            if not ScenarioRunStore._is_prefix(getattr(stored, field_name), getattr(submitted, field_name))
        ]
        if rewritten:
            raise BitScopeError(
                code="SCENARIO_RUN_HISTORY_REWRITE",
                message="Recorded scenario results and evidence are append-only.",
                status_code=409,
                details={"run_id": str(submitted.run_id), "rewritten_fields": rewritten},
            )

        allowed_cleanup: dict[CleanupStatus, frozenset[CleanupStatus]] = {
            CleanupStatus.NOT_STARTED: frozenset(
                {CleanupStatus.NOT_STARTED, CleanupStatus.IN_PROGRESS, CleanupStatus.COMPLETED, CleanupStatus.FAILED}
            ),
            CleanupStatus.IN_PROGRESS: frozenset(
                {CleanupStatus.IN_PROGRESS, CleanupStatus.COMPLETED, CleanupStatus.FAILED}
            ),
            CleanupStatus.COMPLETED: frozenset({CleanupStatus.COMPLETED}),
            CleanupStatus.FAILED: frozenset({CleanupStatus.FAILED}),
        }
        if submitted.cleanup_status not in allowed_cleanup[stored.cleanup_status]:
            raise BitScopeError(
                code="SCENARIO_CLEANUP_INVALID_TRANSITION",
                message="Scenario cleanup status cannot move backward.",
                status_code=409,
                details={
                    "run_id": str(submitted.run_id),
                    "current_status": stored.cleanup_status.value,
                    "submitted_status": submitted.cleanup_status.value,
                },
            )

    @staticmethod
    def _is_prefix(stored: list[object], submitted: list[object]) -> bool:
        return len(submitted) >= len(stored) and submitted[: len(stored)] == stored

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS bitscope_schema_migrations (
                component TEXT PRIMARY KEY,
                version INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scenario_runs (
                run_id TEXT PRIMARY KEY,
                lab_session_id TEXT NOT NULL,
                scenario_id TEXT NOT NULL,
                scenario_version TEXT NOT NULL,
                current_state TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK(revision >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                document TEXT NOT NULL,
                FOREIGN KEY(lab_session_id) REFERENCES lab_sessions(session_id) ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS scenario_runs_by_session
                ON scenario_runs(lab_session_id, created_at, run_id);
            CREATE INDEX IF NOT EXISTS scenario_runs_by_scenario
                ON scenario_runs(scenario_id, scenario_version, current_state);

            CREATE TABLE IF NOT EXISTS scenario_step_runs (
                run_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
                status TEXT NOT NULL,
                document TEXT NOT NULL,
                PRIMARY KEY(run_id, step_id),
                FOREIGN KEY(run_id) REFERENCES scenario_runs(run_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS scenario_assertions (
                run_id TEXT NOT NULL,
                assertion_id TEXT NOT NULL,
                status TEXT NOT NULL,
                document TEXT NOT NULL,
                PRIMARY KEY(run_id, assertion_id),
                FOREIGN KEY(run_id) REFERENCES scenario_runs(run_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS scenario_evidence (
                run_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                document TEXT NOT NULL,
                PRIMARY KEY(run_id, evidence_id),
                FOREIGN KEY(run_id) REFERENCES scenario_runs(run_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS scenario_failures (
                run_id TEXT NOT NULL,
                failure_id TEXT NOT NULL,
                expected INTEGER NOT NULL CHECK(expected IN (0, 1)),
                category TEXT NOT NULL,
                document TEXT NOT NULL,
                PRIMARY KEY(run_id, failure_id),
                FOREIGN KEY(run_id) REFERENCES scenario_runs(run_id) ON DELETE CASCADE
            );
            """
        )
        row = connection.execute(
            "SELECT version FROM bitscope_schema_migrations WHERE component = ?",
            ("scenario_runs",),
        ).fetchone()
        if row is not None and int(row[0]) > SCHEMA_VERSION:
            raise BitScopeError(
                code="SCENARIO_SCHEMA_TOO_NEW",
                message="The scenario database schema is newer than this BitScope version supports.",
                status_code=500,
                details={"supported_version": SCHEMA_VERSION, "database_version": int(row[0])},
            )
        connection.execute(
            """
            INSERT INTO bitscope_schema_migrations(component, version)
            VALUES (?, ?)
            ON CONFLICT(component) DO UPDATE SET version = excluded.version
            """,
            ("scenario_runs", SCHEMA_VERSION),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection
