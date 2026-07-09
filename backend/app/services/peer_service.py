from app.rpc.client import BitcoinRpcClient
from app.rpc.types import JsonValue


class PeerService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def summary(self) -> dict[str, object]:
        network = self._as_dict(self.rpc_client.call("getnetworkinfo"))
        raw_peers = self.rpc_client.call("getpeerinfo")
        peers = [self._normalize_peer(peer) for peer in raw_peers if isinstance(peer, dict)] if isinstance(raw_peers, list) else []
        local_addresses = self._normalize_local_addresses(network.get("localaddresses"))
        networks = self._normalize_networks(network.get("networks"))

        tor_peer_count = len([peer for peer in peers if peer["network"] == "onion"])
        i2p_peer_count = len([peer for peer in peers if peer["network"] == "i2p"])
        inbound_count = len([peer for peer in peers if peer["inbound"] is True])
        outbound_count = len([peer for peer in peers if peer["inbound"] is False])
        reachable_networks = [item["name"] for item in networks if item["reachable"] is True]
        warnings = self._privacy_warnings(peers, local_addresses, networks)

        return {
            "peer_count": len(peers),
            "inbound_count": inbound_count,
            "outbound_count": outbound_count,
            "tor_peer_count": tor_peer_count,
            "i2p_peer_count": i2p_peer_count,
            "local_address_count": len(local_addresses),
            "network_active": self._optional_bool(network.get("networkactive")),
            "reachable_networks": reachable_networks,
            "networks": networks,
            "local_addresses": local_addresses,
            "peers": peers,
            "warnings": warnings,
            "cli_commands": ["bitcoin-cli getpeerinfo", "bitcoin-cli getnetworkinfo"],
            "rpc_methods": ["getpeerinfo", "getnetworkinfo"],
            "concepts": ["Peer-to-peer network", "Tor", "I2P", "Service flags", "Inbound peers", "Privacy"],
            "explanation": (
                "Bitcoin Core reports connected peers, supported address networks, local advertised addresses, "
                "and service flags. Tor or I2P visibility requires Bitcoin Core configuration; BitScope only reports what your node tells it."
            ),
            "raw": {"getpeerinfo": raw_peers, "getnetworkinfo": network},
        }

    def _normalize_peer(self, peer: dict[str, object]) -> dict[str, object]:
        services_names = peer.get("servicesnames")
        mapped_services = [item for item in services_names if isinstance(item, str)] if isinstance(services_names, list) else []
        addr = self._optional_str(peer.get("addr"))
        network = self._optional_str(peer.get("network")) or self._infer_network(addr)
        return {
            "id": self._optional_int(peer.get("id")),
            "addr": addr,
            "addr_bind": self._optional_str(peer.get("addrbind")),
            "addr_local": self._optional_str(peer.get("addrlocal")),
            "network": network,
            "inbound": self._optional_bool(peer.get("inbound")),
            "relay_transactions": self._optional_bool(peer.get("relaytxes")),
            "services": self._optional_str(peer.get("services")),
            "services_names": mapped_services,
            "subver": self._optional_str(peer.get("subver")),
            "starting_height": self._optional_int(peer.get("startingheight")),
            "synced_headers": self._optional_int(peer.get("synced_headers")),
            "synced_blocks": self._optional_int(peer.get("synced_blocks")),
            "ping_time": self._optional_float(peer.get("pingtime")),
            "min_ping": self._optional_float(peer.get("minping")),
            "connection_type": self._optional_str(peer.get("connection_type")),
            "permissions": [item for item in peer.get("permissions", []) if isinstance(item, str)] if isinstance(peer.get("permissions"), list) else [],
            "bytes_sent": self._optional_int(peer.get("bytessent")),
            "bytes_received": self._optional_int(peer.get("bytesrecv")),
        }

    def _normalize_local_addresses(self, value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        addresses: list[dict[str, object]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            address = self._optional_str(item.get("address"))
            addresses.append(
                {
                    "address": address,
                    "port": self._optional_int(item.get("port")),
                    "score": self._optional_int(item.get("score")),
                    "network": self._infer_network(address),
                }
            )
        return addresses

    def _normalize_networks(self, value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        networks: list[dict[str, object]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            networks.append(
                {
                    "name": self._optional_str(item.get("name")),
                    "limited": self._optional_bool(item.get("limited")),
                    "reachable": self._optional_bool(item.get("reachable")),
                    "proxy": self._optional_str(item.get("proxy")),
                    "proxy_randomize_credentials": self._optional_bool(item.get("proxy_randomize_credentials")),
                }
            )
        return networks

    def _privacy_warnings(
        self,
        peers: list[dict[str, object]],
        local_addresses: list[dict[str, object]],
        networks: list[dict[str, object]],
    ) -> list[str]:
        warnings: list[str] = []
        if not peers:
            warnings.append("Your node currently has no connected peers. This is normal for an isolated regtest node.")
        if not any(peer["inbound"] is True for peer in peers):
            warnings.append("No inbound peers are connected. Your node may not be reachable from other nodes.")
        if not any(item["network"] == "onion" for item in peers + local_addresses):
            warnings.append("No Tor onion peers or local onion addresses are visible in Bitcoin Core RPC.")
        if not any(item["network"] == "i2p" for item in peers + local_addresses):
            warnings.append("No I2P peers or local I2P addresses are visible in Bitcoin Core RPC.")

        reachable = {item["name"] for item in networks if item["reachable"] is True}
        if "onion" not in reachable:
            warnings.append("Bitcoin Core does not report the onion network as reachable.")
        if "i2p" not in reachable:
            warnings.append("Bitcoin Core does not report the I2P network as reachable.")
        return warnings

    @staticmethod
    def _infer_network(address: str | None) -> str | None:
        if not address:
            return None
        lowered = address.lower()
        if ".onion" in lowered:
            return "onion"
        if ".b32.i2p" in lowered or lowered.endswith(".i2p"):
            return "i2p"
        if ":" in lowered:
            return "ipv6"
        return "ipv4"

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        return value if isinstance(value, bool) else None

    @staticmethod
    def _optional_float(value: object) -> float | None:
        return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_str(value: object) -> str | None:
        return value if isinstance(value, str) and value else None
