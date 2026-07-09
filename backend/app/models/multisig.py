from typing import Any

from pydantic import BaseModel, Field


class MultisigCreateRequest(BaseModel):
    wallet_name: str = Field(min_length=1, max_length=128)
    required_signatures: int = Field(ge=1, le=15)
    signer_count: int = Field(ge=1, le=15)
    address_type: str = "bech32"


class MultisigFundRequest(BaseModel):
    wallet_name: str = Field(min_length=1, max_length=128)
    multisig_address: str = Field(min_length=1)
    amount_btc: float = Field(gt=0)
    mine_confirmation: bool = True


class MultisigSpendRequest(BaseModel):
    wallet_name: str = Field(min_length=1, max_length=128)
    multisig_address: str = Field(min_length=1)
    destination_address: str = Field(min_length=1)
    amount_btc: float = Field(gt=0)
    extract: bool = False


class MultisigCreateResponse(BaseModel):
    wallet_name: str
    required_signatures: int
    signer_count: int
    address_type: str
    source_addresses: list[str]
    pubkeys: list[str]
    multisig_address: str
    redeem_script: str | None = None
    descriptor: str | None = None
    warnings: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class MultisigFundResponse(BaseModel):
    wallet_name: str
    multisig_address: str
    amount_btc: float
    txid: str
    confirmation_block_hashes: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class MultisigSpendResponse(BaseModel):
    wallet_name: str
    multisig_address: str
    destination_address: str
    amount_btc: float
    input_count: int
    psbt: str
    processed_psbt: str
    complete: bool
    hex: str | None = None
    final_psbt: str | None = None
    fee_btc: float | None = None
    change_position: int | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
