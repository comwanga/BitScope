from datetime import UTC, datetime

from app.models.evidence import EvidenceRecord
from app.models.lifecycle import LifecycleEventType, MempoolRelationshipType
from app.models.scenario import ScenarioRun
from app.services.evidence_service import EvidenceRedactor
from app.services.lifecycle_recorder import LifecycleRecorder
from app.services.rbf_scenario import RBF_REPLACEMENT_SCENARIO


NOW = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
ORIGINAL_TXID = "a" * 64
REPLACEMENT_TXID = "b" * 64


def evidence(run: ScenarioRun, evidence_id: str, result: object) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        kind="transaction",
        label="Recorded Core result",
        scenario_id=run.scenario_id,
        scenario_version=run.scenario_version,
        run_id=run.run_id,
        lab_session_id=run.lab_session_id,
        step_id="replace_transaction",
        captured_at=NOW,
        core_output={"safe_parameters": [], "result": result},
        bitscope_interpretation={"summary": "Recorded by the test.", "facts": [], "limitations": []},
    )


def test_recorder_emits_only_evidence_backed_rbf_events_and_relationships() -> None:
    run = ScenarioRun.create(RBF_REPLACEMENT_SCENARIO, "lifecycle_test", "/Satoshi:28.1.0/", NOW)
    recorder = LifecycleRecorder(EvidenceRedactor(("do-not-export",)))
    replacement = evidence(
        run,
        "rbf.replacement",
        {
            "original_txid": ORIGINAL_TXID,
            "replacement_txid": REPLACEMENT_TXID,
            "requested_fee_rate_sat_vb": 12.5,
            "bumpfee": {"replacement_fee_btc": 0.00002},
            "password": "do-not-export",
        },
    )

    events = recorder.record(run, [replacement])

    assert [event.event_type for event in events] == [
        LifecycleEventType.TRANSACTION_REPLACED,
        LifecycleEventType.TRANSACTION_ENTERED_MEMPOOL,
    ]
    assert all(event.evidence_id == "rbf.replacement" for event in events)
    replaced = events[0]
    assert replaced.transaction_id == REPLACEMENT_TXID
    assert replaced.relationship is not None
    assert replaced.relationship.relationship_type == MempoolRelationshipType.REPLACES
    assert replaced.relationship.related_txid == ORIGINAL_TXID
    assert replaced.raw_safe_core_result["password"] == "[REDACTED]"


def test_persisted_timeline_orders_recorded_events_and_cleanup() -> None:
    run = ScenarioRun.create(RBF_REPLACEMENT_SCENARIO, "lifecycle_test", "/Satoshi:28.1.0/", NOW)
    recorder = LifecycleRecorder()
    events = recorder.record(
        run,
        [
            evidence(
                run,
                "rbf.replacement",
                {"original_txid": ORIGINAL_TXID, "replacement_txid": REPLACEMENT_TXID},
            )
        ],
    )
    timeline_record = recorder.evidence(run, events, NOW)
    cleanup_record = recorder.cleanup_evidence(run, NOW, len(events) + 1)

    timeline = recorder.timeline(run, [cleanup_record, timeline_record])

    assert [event.ordinal for event in timeline.events] == [1, 2, 3]
    assert timeline.events[-1].event_type == LifecycleEventType.SCENARIO_CLEANED_UP
    assert timeline.events[-1].evidence_id == "lifecycle.cleanup"


def test_cpfp_child_is_explicitly_linked_to_its_recorded_parent() -> None:
    event = LifecycleRecorder().child_transaction_event(
        ordinal=4,
        timestamp=NOW,
        step_id="create_child",
        track_id="cpfp.child",
        child_txid=REPLACEMENT_TXID,
        parent_txid=ORIGINAL_TXID,
        evidence_id="cpfp.child-created",
        raw_safe_core_result={"child_txid": REPLACEMENT_TXID},
    )

    assert event.event_type == LifecycleEventType.CHILD_TRANSACTION_CREATED
    assert event.relationship is not None
    assert event.relationship.relationship_type == MempoolRelationshipType.CHILD_OF
    assert event.relationship.related_txid == ORIGINAL_TXID
