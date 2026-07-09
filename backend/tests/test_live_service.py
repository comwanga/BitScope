import json

from app.services.live_service import error_event, node_event_from_status, sse_event


def test_node_event_from_status_keeps_live_status_subset() -> None:
    event = node_event_from_status(
        {
            "chain": "regtest",
            "blocks": 12,
            "headers": 12,
            "verification_progress": 0.95,
            "initial_block_download": False,
            "peer_count": 1,
            "network_active": True,
            "mempool_tx_count": 3,
            "mempool_usage": 2048,
            "warnings": ["pruned", 3],
            "raw": {"rpc": "not streamed"},
        },
        timestamp="2026-07-09T00:00:00+00:00",
    )

    assert event == {
        "timestamp": "2026-07-09T00:00:00+00:00",
        "chain": "regtest",
        "blocks": 12,
        "headers": 12,
        "verification_progress": 0.95,
        "initial_block_download": False,
        "peer_count": 1,
        "network_active": True,
        "mempool_tx_count": 3,
        "mempool_usage": 2048,
        "warnings": ["pruned"],
    }


def test_sse_event_formats_named_event_with_json_payload() -> None:
    rendered = sse_event("node", {"chain": "regtest", "blocks": 1})

    assert rendered.startswith("event: node\ndata: ")
    assert rendered.endswith("\n\n")
    payload = rendered.split("data: ", 1)[1].strip()
    assert json.loads(payload) == {"chain": "regtest", "blocks": 1}


def test_error_event_uses_generic_secret_safe_shape() -> None:
    event = error_event("Node unavailable.")

    assert event["code"] == "LIVE_NODE_UNAVAILABLE"
    assert event["message"] == "Node unavailable."
    assert "timestamp" in event
