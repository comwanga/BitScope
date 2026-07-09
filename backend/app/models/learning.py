from pydantic import BaseModel

from app.models.rpc_explorer import RpcMethodInfo


class LearningConcept(BaseModel):
    id: str
    title: str
    category: str
    summary: str
    details: str
    related_rpc_methods: list[str]
    related_pages: list[str]
    cli_examples: list[str]
    cautions: list[str]


class LearningConceptsResponse(BaseModel):
    concepts: list[LearningConcept]
    categories: list[str]
    rpc_methods: list[str]
    explanation: str


class LearningRpcMethodsResponse(BaseModel):
    methods: list[RpcMethodInfo]
    explanation: str
