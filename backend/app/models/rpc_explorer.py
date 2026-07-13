from typing import Any

from pydantic import BaseModel, Field


class RpcMethodInfo(BaseModel):
    name: str
    category: str
    description: str
    example_params: list[Any] | dict[str, Any]
    concepts: list[str]


class RpcMethodsResponse(BaseModel):
    methods: list[RpcMethodInfo]
    cli_command: str
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str


class RpcExecuteRequest(BaseModel):
    method: str = Field(min_length=1, max_length=64)
    params: list[Any] | dict[str, Any] | None = None


class RpcExecuteResponse(BaseModel):
    method: str
    category: str
    params: list[Any] | dict[str, Any]
    result: Any
    cli_command: str
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
    raw: dict[str, Any]
