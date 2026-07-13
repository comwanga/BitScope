import json
from pathlib import Path

import pytest

from app.errors import BitScopeError
from app.models.lab import LabSession
from app.services.lab_session_service import LabSessionService
from app.services.lab_session_store import LabSessionStore


class FakeSettings:
    bitcoin_network = "regtest"


class FakeRpcClient:
    def __init__(self) -> None:
        self.settings = FakeSettings()
        self.height = 200
        self.loaded: list[str] = []
        self.calls: list[tuple[str, object, str | None]] = []

    def call(self, method: str, params: object = None, wallet_name: str | None = None) -> object:
        if method == "getblockchaininfo":
            return {"chain": "regtest"}
        self.calls.append((method, params, wallet_name))
        if method == "getblockcount":
            return self.height
        if method == "createwallet":
            name = str(params[0])  # type: ignore[index]
            self.loaded.append(name)
            return {"name": name}
        if method == "listwallets":
            return list(self.loaded)
        if method == "unloadwallet":
            assert wallet_name is not None
            self.loaded.remove(wallet_name)
            return None
        raise AssertionError(f"unexpected RPC method {method}")


def service(database: Path, rpc: FakeRpcClient) -> LabSessionService:
    return LabSessionService(rpc, LabSessionStore(str(database)))  # type: ignore[arg-type]


def test_sessions_are_isolated_and_resume_after_store_restart(tmp_path: Path) -> None:
    database = tmp_path / "labs.sqlite3"
    rpc = FakeRpcClient()
    first = service(database, rpc).create("intro")
    second = service(database, rpc).create("intro")

    assert first.session_id != second.session_id
    assert first.wallet_name != second.wallet_name
    resumed = service(database, rpc).get(first.session_id)
    assert resumed == first
    assert resumed.lesson_progress == {"intro": "not_started"}


def test_reset_rotates_wallet_and_clears_reconstructible_artifacts(tmp_path: Path) -> None:
    rpc = FakeRpcClient()
    sessions = service(tmp_path / "labs.sqlite3", rpc)
    original = sessions.create("intro")
    original.created_addresses = ["bcrt1qexample"]
    original.transaction_ids = ["11" * 32]
    original.block_hashes = ["22" * 32]
    original.expected_utxos = [{"txid": "11" * 32, "vout": 0}]
    original.lesson_progress["intro"] = "in_progress"
    sessions.store.save(original)

    reset, previous_wallet = sessions.reset(original.session_id)

    assert previous_wallet == original.owned_wallets[0]
    assert reset.wallet_name == f"bitscope-session-{original.session_id}-r1"
    assert reset.owned_wallets == [previous_wallet, reset.wallet_name]
    assert reset.created_addresses == []
    assert reset.transaction_ids == []
    assert reset.block_hashes == []
    assert reset.expected_utxos == []
    assert reset.lesson_progress == {"intro": "not_started"}
    assert previous_wallet not in rpc.loaded


def test_exports_have_stable_structure_and_no_credentials(tmp_path: Path) -> None:
    sessions = service(tmp_path / "labs.sqlite3", FakeRpcClient())
    session = sessions.create()

    exported = sessions.export_json(session.session_id)
    assert set(exported) == set(LabSession.model_fields)
    serialized = json.dumps(exported)
    assert "rpc_password" not in serialized
    assert "local_access_token" not in serialized
    markdown = sessions.export_markdown(session.session_id)
    assert markdown.startswith(f"# BitScope lab session {session.session_id}")
    assert "`session_created`" in markdown


def test_cleanup_only_unloads_recorded_session_namespace_wallets(tmp_path: Path) -> None:
    rpc = FakeRpcClient()
    sessions = service(tmp_path / "labs.sqlite3", rpc)
    session = sessions.create()
    rpc.loaded.append("developer-wallet")

    cleaned, unloaded = sessions.cleanup(session.session_id)

    assert unloaded == [session.wallet_name]
    assert "developer-wallet" in rpc.loaded
    assert cleaned.status == "cleaned"


def test_cleanup_rejects_tampered_owned_wallet_record(tmp_path: Path) -> None:
    rpc = FakeRpcClient()
    sessions = service(tmp_path / "labs.sqlite3", rpc)
    session = sessions.create()
    session.owned_wallets.append("developer-wallet")
    rpc.loaded.append("developer-wallet")
    sessions.store.save(session)

    with pytest.raises(BitScopeError) as error:
        sessions.cleanup(session.session_id)

    assert error.value.code == "LAB_WALLET_OWNERSHIP_VIOLATION"
    assert "developer-wallet" in rpc.loaded
