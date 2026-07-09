from typing import Any

from pydantic import BaseModel


class PeerNetwork(BaseModel):
    name: str | None = None
    limited: bool | None = None
    reachable: bool | None = None
    proxy: str | None = None
    proxy_randomize_credentials: bool | None = None


class LocalAddress(BaseModel):
    address: str | None = None
    port: int | None = None
    score: int | None = None
    network: str | None = None


class PeerInfo(BaseModel):
    id: int | None = None
    addr: str | None = None
    addr_bind: str | None = None
    addr_local: str | None = None
    network: str | None = None
    inbound: bool | None = None
    relay_transactions: bool | None = None
    services: str | None = None
    services_names: list[str]
    subver: str | None = None
    starting_height: int | None = None
    synced_headers: int | None = None
    synced_blocks: int | None = None
    ping_time: float | None = None
    min_ping: float | None = None
    connection_type: str | None = None
    permissions: list[str]
    bytes_sent: int | None = None
    bytes_received: int | None = None


class PeerSummaryResponse(BaseModel):
    peer_count: int
    inbound_count: int
    outbound_count: int
    tor_peer_count: int
    i2p_peer_count: int
    local_address_count: int
    network_active: bool | None = None
    reachable_networks: list[str | None]
    networks: list[PeerNetwork]
    local_addresses: list[LocalAddress]
    peers: list[PeerInfo]
    warnings: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
