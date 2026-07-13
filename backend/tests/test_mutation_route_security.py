from fastapi.routing import APIRoute

from app.main import create_app
from app.security import require_mutation_access


EXPECTED_PROTECTED_MUTATIONS = {
    ("POST", "/api/demo/run"),
    ("POST", "/api/multisig/create"),
    ("POST", "/api/multisig/fund"),
    ("POST", "/api/multisig/spend-psbt"),
    ("POST", "/api/psbt/create"),
    ("POST", "/api/psbt/wallet-process"),
    ("POST", "/api/regtest/faucet"),
    ("POST", "/api/regtest/mine"),
    ("POST", "/api/scripts/create-op-return"),
    ("POST", "/api/timelocks/transaction"),
    ("POST", "/api/transactions/cpfp-child"),
    ("POST", "/api/transactions/create-regtest"),
    ("POST", "/api/transactions/rbf-bump"),
    ("POST", "/api/transactions/send-regtest"),
    ("POST", "/api/wallets/create"),
    ("POST", "/api/wallets/load"),
    ("POST", "/api/wallets/{wallet_name}/address"),
}


def test_mutation_routes_have_local_access_dependency() -> None:
    protected: set[tuple[str, str]] = set()
    for route in create_app().routes:
        if not isinstance(route, APIRoute):
            continue
        if any(dependency.call is require_mutation_access for dependency in route.dependant.dependencies):
            protected.update((method, route.path) for method in route.methods)

    assert protected == EXPECTED_PROTECTED_MUTATIONS
