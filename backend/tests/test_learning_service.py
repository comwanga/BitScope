from app.services.learning_service import LearningService


def test_list_concepts_returns_categories_and_rpc_links() -> None:
    result = LearningService().list_concepts()

    concept_ids = {concept["id"] for concept in result["concepts"]}  # type: ignore[index]
    assert "utxo-set" in concept_ids
    assert "bitcoin-core-limits" in concept_ids
    assert "Transactions" in result["categories"]
    assert "getblockchaininfo" in result["rpc_methods"]


def test_list_rpc_methods_reuses_safe_rpc_catalog() -> None:
    result = LearningService().list_rpc_methods()
    method_names = {method["name"] for method in result["methods"]}  # type: ignore[index]

    assert "getblockchaininfo" in method_names
    assert "getblockhash" in method_names
    assert "sendtoaddress" not in method_names
