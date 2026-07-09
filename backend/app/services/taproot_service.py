from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.types import JsonValue


class TaprootService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def inspect(self, address: str | None = None, script_hex: str | None = None) -> dict[str, object]:
        clean_address = self._optional_clean(address)
        clean_script = self._optional_clean(script_hex)
        if clean_address is None and clean_script is None:
            raise BitScopeError(
                code="TAPROOT_INPUT_REQUIRED",
                message="Provide a Taproot address or scriptPubKey hex.",
                status_code=400,
            )

        validation: dict[str, object] = {}
        decoded: dict[str, object] = {}
        commands: list[str] = []
        rpc_methods: list[str] = []
        notes: list[str] = []

        if clean_address is not None:
            validation = self._as_dict(self.rpc_client.call("validateaddress", [clean_address]))
            commands.append(f"bitcoin-cli validateaddress {clean_address}")
            rpc_methods.append("validateaddress")
            if validation.get("isvalid") is not True:
                raise BitScopeError(
                    code="INVALID_ADDRESS",
                    message="Bitcoin Core says this address is invalid for the current network.",
                    status_code=400,
                    details={"address": clean_address},
                )
            if clean_script is None:
                clean_script = self._optional_str(validation.get("scriptPubKey"))

        if clean_script is not None:
            clean_script = clean_script.lower()
            self._validate_hex(clean_script)
            decoded = self._as_dict(self.rpc_client.call("decodescript", [clean_script]))
            commands.append(f"bitcoin-cli decodescript {clean_script}")
            rpc_methods.append("decodescript")

        script_program = self._taproot_program_from_script(clean_script)
        validation_version = self._optional_int(validation.get("witness_version"))
        validation_program = self._optional_str(validation.get("witness_program"))
        witness_version = validation_version if validation_version is not None else 1 if script_program else None
        witness_program = validation_program or script_program
        script_type = self._optional_str(decoded.get("type")) or self._optional_str(validation.get("type"))
        asm = self._optional_str(decoded.get("asm"))
        is_taproot = witness_version == 1 and isinstance(witness_program, str) and len(witness_program) == 64

        if is_taproot:
            notes.append("P2TR outputs are native SegWit version 1 outputs with a 32-byte x-only output key.")
            notes.append("The output key may represent a key-path spend only or a key tweaked with a hidden script tree.")
        elif clean_script:
            notes.append("This script is not shaped like a standard P2TR scriptPubKey: OP_1 followed by a 32-byte push.")
        else:
            notes.append("Bitcoin Core did not identify this address as a witness v1 Taproot address.")

        return {
            "address": clean_address,
            "script_hex": clean_script,
            "is_taproot": is_taproot,
            "witness_version": witness_version,
            "witness_program": witness_program,
            "output_key": witness_program if is_taproot else None,
            "script_type": script_type,
            "asm": asm,
            "notes": notes,
            "cli_commands": commands,
            "rpc_methods": rpc_methods,
            "concepts": ["Taproot", "P2TR", "SegWit v1", "X-only public key", "Key-path spend", "Script-path spend"],
            "explanation": (
                "Taproot pay-to-Taproot outputs use SegWit version 1 and commit to a 32-byte x-only output key. "
                "That key can be spent directly with a Schnorr signature or reveal a script path when a Taproot tree was committed."
            ),
            "raw": {"validateaddress": validation, "decodescript": decoded},
        }

    @staticmethod
    def _taproot_program_from_script(script_hex: str | None) -> str | None:
        if not script_hex:
            return None
        if len(script_hex) == 68 and script_hex.startswith("5120"):
            return script_hex[4:]
        return None

    @staticmethod
    def _validate_hex(value: str) -> None:
        if len(value) % 2 != 0:
            raise BitScopeError(
                code="INVALID_SCRIPT",
                message="Script hex must have an even number of characters.",
                status_code=400,
            )
        try:
            bytes.fromhex(value)
        except ValueError as exc:
            raise BitScopeError(
                code="INVALID_SCRIPT",
                message="Script hex contains non-hexadecimal characters.",
                status_code=400,
            ) from exc

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _optional_clean(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_str(value: object) -> str | None:
        return value if isinstance(value, str) and value else None
