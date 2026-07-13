from app.config import Settings


def test_cors_origins_parse_from_comma_separated_string() -> None:
    settings = Settings(backend_cors_origins="http://localhost:3000,http://127.0.0.1:3000")

    assert settings.backend_cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_trusted_hosts_parse_from_comma_separated_string() -> None:
    settings = Settings(backend_trusted_hosts="localhost,127.0.0.1,backend")

    assert settings.backend_trusted_hosts == ["localhost", "127.0.0.1", "backend"]


def test_public_config_does_not_expose_rpc_password() -> None:
    settings = Settings(bitcoin_rpc_password="super-secret", bitscope_local_access_token="local-secret")

    public_config = settings.public_dict()

    assert "bitcoin_rpc_password" not in public_config
    assert "bitscope_local_access_token" not in public_config
    assert "super-secret" not in str(public_config)
    assert "local-secret" not in str(public_config)
    assert public_config["local_access_token_configured"] is True
    assert public_config["app_version"] == "0.1.0"


def test_public_config_exposes_zmq_configured_flags_only() -> None:
    settings = Settings(bitcoin_zmq_rawblock="tcp://127.0.0.1:28332", bitcoin_zmq_rawtx="")

    public_config = settings.public_dict()

    assert public_config["bitcoin_zmq_rawblock_configured"] is True
    assert public_config["bitcoin_zmq_rawtx_configured"] is False


def test_rpc_url_uses_host_and_port() -> None:
    settings = Settings(bitcoin_rpc_host="localhost", bitcoin_rpc_port=38332)

    assert settings.rpc_url == "http://localhost:38332"
