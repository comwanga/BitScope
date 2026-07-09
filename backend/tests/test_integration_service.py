from app.config import Settings
from app.services.integration_service import IntegrationService


def test_zmq_status_reports_unconfigured_state() -> None:
    status = IntegrationService(Settings(bitcoin_zmq_rawblock="", bitcoin_zmq_rawtx="")).zmq_status()

    assert status["configured"] is False
    assert status["rawblock_endpoint"] is None
    assert status["rawtx_endpoint"] is None
    assert status["zmq_listener_available"] is False
    assert status["warnings"]
    assert "getzmqnotifications" in status["rpc_methods"]


def test_zmq_status_reports_configured_endpoints() -> None:
    status = IntegrationService(
        Settings(bitcoin_zmq_rawblock="tcp://127.0.0.1:28332", bitcoin_zmq_rawtx="tcp://127.0.0.1:28333")
    ).zmq_status()

    assert status["configured"] is True
    assert status["rawblock_endpoint"] == "tcp://127.0.0.1:28332"
    assert status["rawtx_endpoint"] == "tcp://127.0.0.1:28333"
    assert status["warnings"] == []


def test_rpc_examples_use_placeholders_not_real_credentials() -> None:
    examples = IntegrationService(Settings(bitcoin_rpc_user="alice", bitcoin_rpc_password="secret")).rpc_examples()

    rendered = str(examples)
    assert "<rpcuser>" in rendered
    assert "<rpcpassword>" in rendered
    assert "alice" not in rendered
    assert "secret" not in rendered
    assert len(examples["examples"]) >= 5
