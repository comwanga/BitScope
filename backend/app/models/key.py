from pydantic import BaseModel


class KeySafetyModel(BaseModel):
    handles_private_keys: bool
    allowed_inputs: list[str]
    blocked_inputs: list[str]
    message: str


class DerivationPathInfo(BaseModel):
    purpose: str
    path: str
    descriptor: str
    script_type: str
    notes: str


class DescriptorRecipe(BaseModel):
    name: str
    descriptor: str
    change_descriptor: str
    purpose: str


class PsbtFlowStep(BaseModel):
    step: int
    role: str
    action: str
    bitcoin_core_rpc: str
    private_key_boundary: str


class KeyEducationResponse(BaseModel):
    safety_model: KeySafetyModel
    derivation_paths: list[DerivationPathInfo]
    descriptor_recipes: list[DescriptorRecipe]
    psbt_flow: list[PsbtFlowStep]
    watch_only_commands: list[str]
    hardware_wallet_notes: list[str]
    cli_commands: list[str]
    rpc_methods: list[str]
    concepts: list[str]
    explanation: str
