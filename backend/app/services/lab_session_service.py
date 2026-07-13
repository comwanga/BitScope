from datetime import UTC, datetime
from secrets import token_hex

from app.errors import BitScopeError
from app.models.lab import LabAction, LabSession
from app.rpc.client import BitcoinRpcClient
from app.rpc.capabilities import RegtestMutationRpcClient
from app.rpc.errors import RpcError
from app.services.lab_session_store import LabSessionStore
from app.services.network_safety import NetworkSafetyGuard


class LabSessionService:
    def __init__(self, rpc_client: BitcoinRpcClient, store: LabSessionStore) -> None:
        self.rpc_client = RegtestMutationRpcClient(rpc_client)
        self.store = store

    def create(self, lesson_id: str | None = None) -> LabSession:
        NetworkSafetyGuard(self.rpc_client).require_regtest()
        session_id = token_hex(12)
        wallet_name = self._wallet_name(session_id, 0)
        height = self._height()
        now = datetime.now(UTC)
        session = LabSession(
            session_id=session_id,
            wallet_name=wallet_name,
            owned_wallets=[wallet_name],
            wallet_generation=0,
            runtime_chain="regtest",
            starting_height=height,
            lesson_progress={lesson_id: "not_started"} if lesson_id else {},
            actions=[self._action(1, "session_created", {"wallet_name": wallet_name, "starting_height": height})],
            status="creating",
            created_at=now,
            updated_at=now,
        )
        self.store.save(session)
        try:
            self.rpc_client.call("createwallet", [wallet_name])
        except Exception:
            session.status = "cleanup_failed"
            session.cleanup_status = "wallet_creation_failed"
            session.updated_at = datetime.now(UTC)
            self.store.save(session)
            raise
        session.status = "active"
        session.updated_at = datetime.now(UTC)
        self.store.save(session)
        return session

    def get(self, session_id: str) -> LabSession:
        session = self.store.get(session_id)
        if session is None:
            raise BitScopeError("LAB_SESSION_NOT_FOUND", "The requested lab session does not exist.", 404)
        return session

    def reset(self, session_id: str) -> tuple[LabSession, str]:
        NetworkSafetyGuard(self.rpc_client).require_regtest()
        session = self.get(session_id)
        if session.status != "active":
            raise BitScopeError("LAB_SESSION_NOT_ACTIVE", "Only an active lab session can be reset.", 409)
        previous_wallet = session.wallet_name
        generation = session.wallet_generation + 1
        wallet_name = self._wallet_name(session.session_id, generation)
        session.status = "resetting"
        session.updated_at = datetime.now(UTC)
        self.store.save(session)
        self._unload_if_loaded(previous_wallet)
        try:
            self.rpc_client.call("createwallet", [wallet_name])
        except Exception:
            session.status = "cleanup_failed"
            session.cleanup_status = "reset_wallet_creation_failed"
            session.updated_at = datetime.now(UTC)
            self.store.save(session)
            raise
        height = self._height()
        session.wallet_name = wallet_name
        session.owned_wallets.append(wallet_name)
        session.wallet_generation = generation
        session.starting_height = height
        session.created_addresses = []
        session.transaction_ids = []
        session.block_hashes = []
        session.expected_utxos = []
        session.lesson_progress = {key: "not_started" for key in session.lesson_progress}
        session.actions.append(self._action(len(session.actions) + 1, "session_reset", {"previous_wallet": previous_wallet, "wallet_name": wallet_name, "starting_height": height}))
        session.status = "active"
        session.cleanup_status = None
        session.updated_at = datetime.now(UTC)
        self.store.save(session)
        return session, previous_wallet

    def cleanup(self, session_id: str) -> tuple[LabSession, list[str]]:
        NetworkSafetyGuard(self.rpc_client).require_regtest()
        session = self.get(session_id)
        unloaded: list[str] = []
        for wallet_name in session.owned_wallets:
            self._require_owned_name(session.session_id, wallet_name)
        for wallet_name in session.owned_wallets:
            if self._unload_if_loaded(wallet_name):
                unloaded.append(wallet_name)
        session.status = "cleaned"
        session.cleanup_status = "wallets_unloaded"
        session.actions.append(self._action(len(session.actions) + 1, "session_cleaned", {"unloaded_wallets": unloaded}))
        session.updated_at = datetime.now(UTC)
        self.store.save(session)
        return session, unloaded

    def export_json(self, session_id: str) -> dict[str, object]:
        return self.get(session_id).model_dump(mode="json")

    def export_markdown(self, session_id: str) -> str:
        session = self.get(session_id)
        actions = "\n".join(f"{action.sequence}. `{action.kind}` at {action.occurred_at.isoformat()}" for action in session.actions)
        return (
            f"# BitScope lab session {session.session_id}\n\n"
            f"- Status: {session.status}\n- Chain: {session.runtime_chain}\n"
            f"- Wallet: `{session.wallet_name}`\n- Starting height: {session.starting_height}\n\n"
            f"## Actions\n\n{actions or 'No actions recorded.'}\n"
        )

    def _height(self) -> int:
        value = self.rpc_client.call("getblockcount")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise BitScopeError("BITCOIN_CORE_INVALID_RESPONSE", "Bitcoin Core returned an invalid block height.", 502)
        return value

    def _unload_if_loaded(self, wallet_name: str) -> bool:
        loaded = self.rpc_client.call("listwallets")
        if not isinstance(loaded, list) or wallet_name not in loaded:
            return False
        try:
            self.rpc_client.call("unloadwallet", [], wallet_name=wallet_name)
        except RpcError as exc:
            raise BitScopeError("LAB_WALLET_CLEANUP_FAILED", "Bitcoin Core could not unload a session-owned wallet.", 502, {"wallet_name": wallet_name}) from exc
        return True

    @staticmethod
    def _wallet_name(session_id: str, generation: int) -> str:
        base = f"bitscope-session-{session_id}"
        return base if generation == 0 else f"{base}-r{generation}"

    @staticmethod
    def _require_owned_name(session_id: str, wallet_name: str) -> None:
        prefix = f"bitscope-session-{session_id}"
        suffix = wallet_name.removeprefix(f"{prefix}-r")
        if wallet_name != prefix and (suffix == wallet_name or not suffix.isdigit()):
            raise BitScopeError("LAB_WALLET_OWNERSHIP_VIOLATION", "Refusing to clean up a wallet outside this session namespace.", 409)

    @staticmethod
    def _action(sequence: int, kind: str, details: dict[str, object]) -> LabAction:
        return LabAction(sequence=sequence, kind=kind, occurred_at=datetime.now(UTC), details=details)
