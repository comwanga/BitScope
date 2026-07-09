from typing import Any

from pydantic import BaseModel


class AddressUtxo(BaseModel):
    txid: str
    vout: int
    amount_btc: float
    confirmations: int
    spendable: bool | None = None
    solvable: bool | None = None
    safe: bool | None = None
    descriptor: str | None = None


class AddressResponse(BaseModel):
    address: str
    is_valid: bool
    network: str | None = None
    address_type: str | None = None
    script_pub_key: str | None = None
    witness_version: int | None = None
    witness_program: str | None = None
    is_mine: bool | None = None
    is_watch_only: bool | None = None
    solvable: bool | None = None
    wallet_name: str | None = None
    received_btc: float | None = None
    utxos: list[AddressUtxo]
    limitation: str | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
