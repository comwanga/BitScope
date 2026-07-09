from typing import Any

from pydantic import BaseModel, Field


class AddressIndexScanRequest(BaseModel):
    address: str = Field(min_length=1)
    start_height: int = Field(ge=0)
    end_height: int = Field(ge=0)


class IndexedAddressOutput(BaseModel):
    txid: str
    vout: int
    value_btc: float
    block_height: int
    block_hash: str
    script_type: str | None = None
    script_pub_key_hex: str | None = None


class AddressIndexScanResponse(BaseModel):
    address: str
    start_height: int
    end_height: int
    blocks_scanned: int
    outputs: list[IndexedAddressOutput]
    total_received_btc_in_range: float
    limitation: str
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
