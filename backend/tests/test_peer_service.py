from app.services.peer_service import PeerService


class FakeRpcClient:
    def __init__(self, peers: list[dict[str, object]], network: dict[str, object]) -> None:
        self.peers = peers
        self.network = network
        self.calls: list[str] = []

    def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
        self.calls.append(method)
        if method == "getpeerinfo":
            return self.peers
        if method == "getnetworkinfo":
            return self.network
        raise AssertionError(f"unexpected method {method}")


def test_peer_summary_counts_transports_and_services() -> None:
    rpc = FakeRpcClient(
        peers=[
            {
                "id": 1,
                "addr": "192.0.2.10:8333",
                "network": "ipv4",
                "inbound": False,
                "relaytxes": True,
                "services": "0000000000000409",
                "servicesnames": ["NETWORK", "WITNESS", "NETWORK_LIMITED"],
                "subver": "/Satoshi:31.0.0/",
                "pingtime": 0.01,
                "connection_type": "outbound-full-relay",
            },
            {"id": 2, "addr": "exampleabcdefghijklmnop.onion:8333", "network": "onion", "inbound": True, "servicesnames": ["NETWORK"]},
            {"id": 3, "addr": "example.b32.i2p:0", "network": "i2p", "inbound": False, "servicesnames": ["WITNESS"]},
        ],
        network={
            "networkactive": True,
            "networks": [
                {"name": "ipv4", "reachable": True, "limited": False},
                {"name": "onion", "reachable": True, "limited": False, "proxy": "127.0.0.1:9050", "proxy_randomize_credentials": True},
                {"name": "i2p", "reachable": True, "limited": False},
            ],
            "localaddresses": [{"address": "exampleabcdefghijklmnop.onion", "port": 8333, "score": 4}],
        },
    )

    result = PeerService(rpc).summary()  # type: ignore[arg-type]

    assert result["peer_count"] == 3
    assert result["inbound_count"] == 1
    assert result["outbound_count"] == 2
    assert result["tor_peer_count"] == 1
    assert result["i2p_peer_count"] == 1
    assert result["reachable_networks"] == ["ipv4", "onion", "i2p"]
    assert result["peers"][0]["services_names"] == ["NETWORK", "WITNESS", "NETWORK_LIMITED"]  # type: ignore[index]
    assert result["warnings"] == []
    assert rpc.calls == ["getnetworkinfo", "getpeerinfo"]


def test_peer_summary_warns_for_isolated_regtest_node() -> None:
    rpc = FakeRpcClient(
        peers=[],
        network={
            "networkactive": True,
            "networks": [{"name": "ipv4", "reachable": True}, {"name": "onion", "reachable": False}, {"name": "i2p", "reachable": False}],
            "localaddresses": [],
        },
    )

    result = PeerService(rpc).summary()  # type: ignore[arg-type]

    assert result["peer_count"] == 0
    assert "Your node currently has no connected peers. This is normal for an isolated regtest node." in result["warnings"]
    assert "Bitcoin Core does not report the onion network as reachable." in result["warnings"]
    assert "Bitcoin Core does not report the I2P network as reachable." in result["warnings"]


def test_peer_summary_infers_transport_from_address_when_network_field_missing() -> None:
    rpc = FakeRpcClient(
        peers=[
            {"addr": "abcdefghijklmnop.onion:8333", "inbound": False},
            {"addr": "peer.b32.i2p:0", "inbound": False},
        ],
        network={"networks": [], "localaddresses": []},
    )

    result = PeerService(rpc).summary()  # type: ignore[arg-type]

    assert result["peers"][0]["network"] == "onion"  # type: ignore[index]
    assert result["peers"][1]["network"] == "i2p"  # type: ignore[index]
