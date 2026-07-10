from typing import Any

from pydantic import BaseModel, Field


class DemoRunRequest(BaseModel):
    wallet_name: str = Field(default="bitscope-demo", min_length=1, max_length=96)
    fresh_wallet: bool = True
    mine_blocks: int = Field(default=101, ge=101, le=500)
    send_amount_btc: float = Field(default=1.0, gt=0)
    include_script_sample: bool = True


class DemoStep(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    raw: dict[str, Any]


class DemoRunResponse(BaseModel):
    session_id: str
    wallet_name: str
    mining_address: str
    recipient_address: str
    txid: str | None = None
    block_hashes: list[str]
    confirmation_block_hashes: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    steps: list[DemoStep]
    export_markdown: str
    explanation: str
