from app.errors import BitScopeError
from app.rpc.client import BitcoinRpcClient
from app.rpc.types import JsonValue


class DescriptorService:
    def __init__(self, rpc_client: BitcoinRpcClient) -> None:
        self.rpc_client = rpc_client

    def analyze(self, descriptor: str, derive_start: int | None = None, derive_end: int | None = None) -> dict[str, object]:
        clean_descriptor = descriptor.strip()
        if not clean_descriptor:
            raise BitScopeError(
                code="INVALID_DESCRIPTOR",
                message="Provide a descriptor to inspect.",
                status_code=400,
            )

        info = self._as_dict(self.rpc_client.call("getdescriptorinfo", [clean_descriptor]))
        normalized = self._optional_str(info.get("descriptor"))
        is_range = self._optional_bool(info.get("isrange"))
        addresses: list[str] = []
        raw: dict[str, JsonValue] = {"getdescriptorinfo": info}
        cli_commands = [f"bitcoin-cli getdescriptorinfo '{clean_descriptor}'"]
        rpc_methods = ["getdescriptorinfo"]

        if derive_start is not None or derive_end is not None:
            if not is_range:
                raise BitScopeError(
                    code="DESCRIPTOR_NOT_RANGE",
                    message="Only ranged descriptors can be derived with an index range.",
                    status_code=400,
                    details={"descriptor": clean_descriptor},
                )
            start = derive_start if derive_start is not None else 0
            end = derive_end if derive_end is not None else start
            if end < start:
                raise BitScopeError(
                    code="INVALID_DESCRIPTOR_RANGE",
                    message="Descriptor derive end must be greater than or equal to derive start.",
                    status_code=400,
                    details={"derive_start": start, "derive_end": end},
                )
            if end - start > 20:
                raise BitScopeError(
                    code="DESCRIPTOR_RANGE_TOO_LARGE",
                    message="Derive at most 21 addresses at a time.",
                    status_code=400,
                    details={"derive_start": start, "derive_end": end},
                )

            derived = self.rpc_client.call("deriveaddresses", [normalized or clean_descriptor, [start, end]])
            addresses = [address for address in derived if isinstance(address, str)] if isinstance(derived, list) else []
            raw["deriveaddresses"] = derived
            cli_commands.append(f"bitcoin-cli deriveaddresses '{normalized or clean_descriptor}' '[{start},{end}]'")
            rpc_methods.append("deriveaddresses")

        return {
            "descriptor": clean_descriptor,
            "normalized_descriptor": normalized,
            "checksum": self._optional_str(info.get("checksum")),
            "is_range": is_range,
            "is_solvable": self._optional_bool(info.get("issolvable")),
            "has_private_keys": self._optional_bool(info.get("hasprivatekeys")),
            "derived_addresses": addresses,
            "cli_commands": cli_commands,
            "rpc_methods": rpc_methods,
            "concepts": ["Descriptor", "Checksum", "Key origin", "Ranged descriptor", "Address derivation"],
            "explanation": (
                "Bitcoin Core descriptors describe scripts and key derivation paths in a wallet-independent format. "
                "getdescriptorinfo normalizes the descriptor and adds checksum metadata; deriveaddresses previews addresses for ranged descriptors."
            ),
            "raw": raw,
        }

    def wallet_descriptors(self, wallet_name: str) -> dict[str, object]:
        clean_wallet = wallet_name.strip()
        if not clean_wallet:
            raise BitScopeError(
                code="INVALID_WALLET_NAME",
                message="Provide a wallet name.",
                status_code=400,
            )

        listed = self._as_dict(self.rpc_client.call("listdescriptors", [False], wallet_name=clean_wallet))
        raw_descriptors = listed.get("descriptors")
        descriptors = [
            self._normalize_wallet_descriptor(item)
            for item in raw_descriptors
            if isinstance(item, dict)
        ] if isinstance(raw_descriptors, list) else []

        return {
            "wallet_name": clean_wallet,
            "descriptors": descriptors,
            "cli_commands": [f"bitcoin-cli -rpcwallet={clean_wallet} listdescriptors false"],
            "rpc_methods": ["listdescriptors"],
            "concepts": ["Descriptor wallet", "External chain", "Internal change", "Key origin", "Address pool"],
            "explanation": (
                "Descriptor wallets store receive and change scripts as descriptors. BitScope requests public descriptors only, "
                "so private keys are not returned to the browser."
            ),
            "raw": {"listdescriptors": listed},
        }

    def _normalize_wallet_descriptor(self, descriptor: dict[object, object]) -> dict[str, object]:
        value = self._optional_str(descriptor.get("desc")) or self._optional_str(descriptor.get("descriptor")) or ""
        range_value = descriptor.get("range")
        return {
            "descriptor": value,
            "active": self._optional_bool(descriptor.get("active")),
            "internal": self._optional_bool(descriptor.get("internal")),
            "range": [int(item) for item in range_value if isinstance(item, int) and not isinstance(item, bool)]
            if isinstance(range_value, list)
            else None,
            "next_index": self._optional_int(descriptor.get("next")),
            "timestamp": descriptor.get("timestamp") if isinstance(descriptor.get("timestamp"), int | str) else None,
        }

    @staticmethod
    def _as_dict(value: JsonValue) -> dict[str, object]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        return value if isinstance(value, bool) else None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _optional_str(value: object) -> str | None:
        return value if isinstance(value, str) and value else None
