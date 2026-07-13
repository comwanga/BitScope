from typing import Any

from pydantic import BaseModel
from pydantic import Field


class TransactionInput(BaseModel):
    coinbase: str | None = None
    previous_txid: str | None = None
    vout: int | None = None
    sequence: int | None = None
    script_sig_asm: str | None = None
    script_sig_hex: str | None = None
    witness: list[str]


class TransactionOutput(BaseModel):
    n: int
    value_btc: float
    script_pub_key_asm: str | None = None
    script_pub_key_hex: str | None = None
    script_type: str | None = None
    address: str | None = None


class TransactionResponse(BaseModel):
    txid: str
    hash: str | None = None
    version: int | None = None
    size: int | None = None
    vsize: int | None = None
    weight: int | None = None
    locktime: int | None = None
    confirmations: int | None = None
    block_hash: str | None = None
    block_time: int | None = None
    time: int | None = None
    in_mempool: bool
    fee_btc: float | None = None
    fee_source: str | None = None
    inputs: list[TransactionInput]
    outputs: list[TransactionOutput]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class RegtestTransactionBuildRequest(BaseModel):
    wallet_name: str = Field(min_length=1, max_length=128)
    address: str = Field(min_length=1, max_length=128)
    amount_btc: float = Field(gt=0)


class RegtestTransactionSendRequest(RegtestTransactionBuildRequest):
    mine_confirmation: bool = True


class RegtestTransactionBuildResponse(BaseModel):
    wallet_name: str
    address: str
    amount_btc: float
    unsigned_hex: str
    funded_hex: str
    signed_hex: str | None = None
    complete: bool
    txid: str | None = None
    fee_btc: float | None = None
    change_position: int | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class RegtestTransactionSendResponse(RegtestTransactionBuildResponse):
    txid: str
    confirmation_block_hashes: list[str]


class TransactionPolicyResponse(BaseModel):
    txid: str
    in_mempool: bool
    bip125_replaceable: bool | None = None
    can_rbf: bool
    can_cpfp: bool
    fee_btc: float | None = None
    modified_fee_btc: float | None = None
    vsize: int | None = None
    fee_rate_sat_vb: float | None = None
    ancestor_count: int | None = None
    ancestor_size: int | None = None
    ancestor_fees_btc: float | None = None
    descendant_count: int | None = None
    descendant_size: int | None = None
    descendant_fees_btc: float | None = None
    warnings: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class RbfBumpRequest(BaseModel):
    wallet_name: str = Field(min_length=1, max_length=128)
    txid: str = Field(min_length=64, max_length=64)
    fee_rate_sat_vb: float | None = Field(default=None, gt=0)
    conf_target: int | None = Field(default=None, ge=1, le=1008)


class RbfBumpResponse(BaseModel):
    wallet_name: str
    original_txid: str
    replacement_txid: str | None = None
    original_fee_btc: float | None = None
    replacement_fee_btc: float | None = None
    fee_delta_btc: float | None = None
    errors: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class CpfpChildRequest(BaseModel):
    wallet_name: str = Field(min_length=1, max_length=128)
    parent_txid: str = Field(min_length=64, max_length=64)
    parent_vout: int = Field(ge=0)
    destination_address: str = Field(min_length=1, max_length=128)
    amount_btc: float = Field(gt=0)
    fee_rate_sat_vb: float | None = Field(default=None, gt=0)
    broadcast: bool = False


class CpfpChildResponse(BaseModel):
    wallet_name: str
    parent_txid: str
    parent_vout: int
    destination_address: str
    amount_btc: float
    unsigned_hex: str
    funded_hex: str
    signed_hex: str | None = None
    complete: bool
    child_txid: str | None = None
    fee_btc: float | None = None
    change_position: int | None = None
    broadcast: bool
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
