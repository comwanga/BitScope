from typing import Any

from pydantic import BaseModel, Field


class WalletActionRequest(BaseModel):
    wallet_name: str = Field(min_length=1, max_length=128)


class NewAddressRequest(BaseModel):
    label: str = Field(default="", max_length=128)
    address_type: str = Field(default="bech32", max_length=32)


class WalletInfo(BaseModel):
    wallet_name: str
    loaded: bool
    scanning: bool | None = None
    private_keys_enabled: bool | None = None
    descriptors: bool | None = None
    blank: bool | None = None
    birthtime: int | None = None
    warnings: list[str]


class WalletSummaryResponse(BaseModel):
    loaded_wallets: list[str]
    available_wallets: list[WalletInfo]
    configured_wallet: str | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class WalletActionResponse(BaseModel):
    wallet_name: str
    message: str
    warning: str | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class WalletBalanceResponse(BaseModel):
    wallet_name: str
    trusted_btc: float | None = None
    untrusted_pending_btc: float | None = None
    immature_btc: float | None = None
    total_btc: float | None = None
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class WalletAddressResponse(BaseModel):
    wallet_name: str
    address: str
    label: str
    address_type: str
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class WalletUtxo(BaseModel):
    txid: str
    vout: int
    address: str | None = None
    label: str | None = None
    amount_btc: float
    confirmations: int
    spendable: bool | None = None
    solvable: bool | None = None
    safe: bool | None = None


class WalletUtxosResponse(BaseModel):
    wallet_name: str
    utxos: list[WalletUtxo]
    total_btc: float
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]


class WalletTransaction(BaseModel):
    txid: str
    category: str | None = None
    address: str | None = None
    amount_btc: float | None = None
    fee_btc: float | None = None
    confirmations: int | None = None
    time: int | None = None
    trusted: bool | None = None


class WalletTransactionsResponse(BaseModel):
    wallet_name: str
    transactions: list[WalletTransaction]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
