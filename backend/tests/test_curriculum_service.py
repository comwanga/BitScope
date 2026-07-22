from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.errors import BitScopeError
from app.services.challenge_service import CHALLENGES, ChallengeService
from app.services.curriculum_service import CurriculumService
from app.services.scenario_artifact_store import ScenarioArtifactStore
from app.services.scenario_catalog import DEFAULT_SCENARIO_CATALOG
from app.services.scenario_run_store import ScenarioRunStore


def test_curriculum_maps_every_chapter_to_only_implemented_features() -> None:
    curriculum = CurriculumService().curriculum()

    assert [entry.chapter for entry in curriculum.chapters] == list(range(3, 14))
    assert all(entry.source_url.startswith(curriculum.course_url + "/blob/master/") for entry in curriculum.chapters)
    assert all(entry.relevant_pages for entry in curriculum.chapters)
    assert all(entry.rpc_methods for entry in curriculum.chapters)
    registered = {entry.scenario_id for entry in DEFAULT_SCENARIO_CATALOG.list()}
    assert all(
        scenario_id in registered
        for entry in curriculum.chapters
        for scenario_id in entry.relevant_scenarios
    )
    chapter_five = curriculum.chapters[2]
    chapter_eight = curriculum.chapters[5]
    assert chapter_five.implementation_note is not None and "deferred" in chapter_five.implementation_note
    assert chapter_eight.implementation_note is not None and "deferred" in chapter_eight.implementation_note


def test_challenge_catalog_keeps_hints_and_solutions_out_of_public_definitions(tmp_path) -> None:
    service = ChallengeService(
        ScenarioRunStore(str(tmp_path / "challenges.sqlite3")),
        ScenarioArtifactStore(str(tmp_path / "artifacts")),
    )

    catalog = service.catalog()
    public_document = catalog.model_dump_json()

    assert len(catalog.challenges) == 6
    assert "Start by distinguishing an input sequence" not in public_document
    assert "completion_explanation" not in public_document
    assert all(challenge.solution_locked for challenge in catalog.challenges)
    first_hint = service.hint("signal-opt-in-rbf", 1)
    second_hint = service.hint("signal-opt-in-rbf", 2)
    assert first_hint.level == 1 and first_hint.remaining_hints == 2
    assert second_hint.level == 2 and second_hint.remaining_hints == 1
    assert first_hint.reveals_solution is False

    with pytest.raises(BitScopeError) as missing:
        service.hint("signal-opt-in-rbf", 4)
    assert missing.value.code == "CHALLENGE_HINT_NOT_FOUND"


def test_challenge_assertions_are_declared_by_their_reviewed_scenarios() -> None:
    for spec in CHALLENGES:
        definition = DEFAULT_SCENARIO_CATALOG.get(spec.definition.scenario_id).definition
        assertion_ids = {assertion.assertion_id for assertion in definition.assertions}
        assert set(spec.required_assertion_ids) <= assertion_ids


def test_incomplete_challenge_keeps_completion_explanation_locked() -> None:
    run_id = uuid4()
    run = SimpleNamespace(
        run_id=run_id,
        lab_session_id="challenge_session",
        scenario_id="rbf-replacement",
        scenario_version="1.0.0",
        bitcoin_core_version=None,
        updated_at=datetime(2026, 7, 22, tzinfo=UTC),
        final_result=None,
        cleanup_status="not_started",
        assertion_results=[],
        evidence=[],
    )
    run_store = SimpleNamespace(get_for_session=lambda submitted_id, session_id: run)
    artifact_store = SimpleNamespace(list_evidence=lambda submitted_run: [])
    service = ChallengeService(run_store, artifact_store)

    result = service.verify("signal-opt-in-rbf", run_id, "challenge_session")

    assert result.completed is False
    assert result.solution_unlocked is False
    assert "Bitcoin Core observed replaceable" not in result.final_explanation
    assert "Completion remains locked" in result.final_explanation
