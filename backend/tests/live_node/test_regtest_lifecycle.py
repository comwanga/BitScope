from app.rpc.client import BitcoinRpcClient


def test_live_regtest_wallet_can_send_after_coinbase_maturity(
    live_rpc_client: BitcoinRpcClient,
    mature_wallet: str,
) -> None:
    destination = live_rpc_client.call("getnewaddress", ["bitscope-test-destination", "bech32"], wallet_name=mature_wallet)
    assert isinstance(destination, str)

    validation = live_rpc_client.call("validateaddress", [destination])
    assert isinstance(validation, dict)
    assert validation.get("isvalid") is True

    txid = live_rpc_client.call("sendtoaddress", [destination, 0.1], wallet_name=mature_wallet)
    assert isinstance(txid, str)
    assert len(txid) == 64

    mining_address = live_rpc_client.call("getnewaddress", ["bitscope-test-confirm", "bech32"], wallet_name=mature_wallet)
    assert isinstance(mining_address, str)
    block_hashes = live_rpc_client.call("generatetoaddress", [1, mining_address])
    assert isinstance(block_hashes, list)
    assert len(block_hashes) == 1
