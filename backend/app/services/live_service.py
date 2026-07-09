from datetime import datetime, timezone
import json


def node_event_from_status(status: dict[str, object], timestamp: str | None = None) -> dict[str, object]:
    return {
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "chain": _optional_str(status.get("chain")),
        "blocks": _optional_int(status.get("blocks")),
        "headers": _optional_int(status.get("headers")),
        "verification_progress": _optional_float(status.get("verification_progress")),
        "initial_block_download": _optional_bool(status.get("initial_block_download")),
        "peer_count": _optional_int(status.get("peer_count")),
        "network_active": _optional_bool(status.get("network_active")),
        "mempool_tx_count": _optional_int(status.get("mempool_tx_count")),
        "mempool_usage": _optional_int(status.get("mempool_usage")),
        "warnings": _string_list(status.get("warnings")),
    }


def error_event(message: str, code: str = "LIVE_NODE_UNAVAILABLE") -> dict[str, object]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "code": code,
        "message": message,
    }


def sse_event(event: str, data: dict[str, object]) -> str:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
    return f"event: {event}\ndata: {payload}\n\n"


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, str)]
