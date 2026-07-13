import pytest

from app.errors import BitScopeError
from app.services.script_service import ScriptService


class FakeRpcClient:
    def __init__(self, decoded: object | None = None, network: str = "regtest") -> None:
        self.decoded = decoded or {}
        self.calls: list[tuple[str, list[object]]] = []
        self.settings = type("Settings", (), {"bitcoin_network": network})()

    def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
        if method == "getblockchaininfo":
            return {"chain": {"mainnet": "main", "testnet": "test"}.get(self.settings.bitcoin_network, self.settings.bitcoin_network)}
        self.calls.append((method, params))
        if method == "validateaddress":
            return {"isvalid": True}
        if method == "getbalances":
            return {"mine": {"trusted": 2.0, "immature": 0.0}}
        if method == "createrawtransaction":
            return "00aa"
        if method == "fundrawtransaction":
            return {"hex": "00bb", "fee": 0.00001, "changepos": 1}
        if method == "signrawtransactionwithwallet":
            return {"hex": "00cc", "complete": True}
        if method == "decoderawtransaction":
            return {"txid": "11" * 32, "vout": [{"n": 0, "value": 0, "scriptPubKey": {"type": "nulldata", "hex": "6a046c616273"}}]}
        if method == "testmempoolaccept":
            return [{"txid": "11" * 32, "allowed": True}]
        if method == "sendrawtransaction":
            return "22" * 32
        if method == "getnewaddress":
            return "bcrt1qmine"
        if method == "generatetoaddress":
            return ["block-0"]
        return self.decoded


def test_decode_standard_p2pkh_script() -> None:
    script_hex = "76a91489abcdefabbaabbaabbaabbaabbaabbaabbaabba88ac"
    rpc = FakeRpcClient(
        {
            "asm": "OP_DUP OP_HASH160 89abcdefabbaabbaabbaabbaabbaabbaabbaabba OP_EQUALVERIFY OP_CHECKSIG",
            "type": "pubkeyhash",
            "reqSigs": 1,
            "addresses": ["mipcBbFg9gMiCh81Kj8tqqdgoZub1ZJRfn"],
            "p2sh": "2N7...",
        }
    )

    result = ScriptService(rpc).decode(script_hex)  # type: ignore[arg-type]

    assert result["script_type"] == "pubkeyhash"
    assert result["req_sigs"] == 1
    assert result["addresses"] == ["mipcBbFg9gMiCh81Kj8tqqdgoZub1ZJRfn"]
    assert [opcode["opcode"] for opcode in result["opcodes"]] == [
        "OP_DUP",
        "OP_HASH160",
        "OP_PUSHBYTES_20",
        "OP_EQUALVERIFY",
        "OP_CHECKSIG",
    ]
    assert rpc.calls == [("decodescript", [script_hex])]


def test_decode_op_return_data_push() -> None:
    script_hex = "6a046c616273"
    result = ScriptService(FakeRpcClient({"asm": "OP_RETURN 6c616273", "type": "nulldata"})).decode(script_hex)  # type: ignore[arg-type]

    assert result["script_type"] == "nulldata"
    assert result["opcodes"][0]["opcode"] == "OP_RETURN"  # type: ignore[index]
    assert result["opcodes"][1]["data_hex"] == "6c616273"  # type: ignore[index]
    assert result["opcodes"][1]["description"] == "Pushes 4 byte(s) onto the stack."  # type: ignore[index]


def test_decode_rejects_non_hex_input() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        ScriptService(FakeRpcClient()).decode("not-hex")  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_SCRIPT"


def test_decode_rejects_odd_length_hex() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        ScriptService(FakeRpcClient()).decode("abc")  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_SCRIPT"


def test_decode_rejects_truncated_push() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        ScriptService(FakeRpcClient()).decode("04aabb")  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_SCRIPT"
    assert exc_info.value.details["expected_bytes"] == 4


def test_template_builds_p2pkh_script() -> None:
    rpc = FakeRpcClient({"asm": "OP_DUP OP_HASH160 89abcdefabbaabbaabbaabbaabbaabbaabbaabba OP_EQUALVERIFY OP_CHECKSIG", "type": "pubkeyhash", "p2sh": "2N7..."})

    result = ScriptService(rpc).template("p2pkh", pubkey_hash_hex="89abcdefabbaabbaabbaabbaabbaabbaabbaabba")  # type: ignore[arg-type]

    assert result["script_hex"] == "76a91489abcdefabbaabbaabbaabbaabbaabbaabbaabba88ac"
    assert result["template"] == "p2pkh"
    assert result["p2sh"] == "2N7..."
    assert [opcode["opcode"] for opcode in result["opcodes"]] == [
        "OP_DUP",
        "OP_HASH160",
        "OP_PUSHBYTES_20",
        "OP_EQUALVERIFY",
        "OP_CHECKSIG",
    ]
    assert rpc.calls == [("decodescript", [result["script_hex"]])]


def test_template_builds_hashlock_script() -> None:
    pubkey = "02" + ("aa" * 32)
    hash_hex = "11" * 32

    result = ScriptService(FakeRpcClient({"asm": "OP_SHA256 ... OP_EQUALVERIFY ... OP_CHECKSIG"})).template(  # type: ignore[arg-type]
        "hashlock",
        pubkey_hex=pubkey,
        hash_hex=hash_hex,
    )

    assert result["script_hex"] == f"a820{hash_hex}8821{pubkey}ac"
    assert [opcode["opcode"] for opcode in result["opcodes"]] == [
        "OP_SHA256",
        "OP_PUSHBYTES_32",
        "OP_EQUALVERIFY",
        "OP_PUSHBYTES_33",
        "OP_CHECKSIG",
    ]


def test_template_builds_conditional_script() -> None:
    primary = "02" + ("aa" * 32)
    fallback = "03" + ("bb" * 32)

    result = ScriptService(FakeRpcClient({"asm": "OP_IF ... OP_ELSE ... OP_ENDIF"})).template(  # type: ignore[arg-type]
        "conditional",
        pubkey_hex=primary,
        fallback_pubkey_hex=fallback,
    )

    assert result["script_hex"] == f"6321{primary}ac6721{fallback}ac68"
    assert [opcode["opcode"] for opcode in result["opcodes"]] == [
        "OP_IF",
        "OP_PUSHBYTES_33",
        "OP_CHECKSIG",
        "OP_ELSE",
        "OP_PUSHBYTES_33",
        "OP_CHECKSIG",
        "OP_ENDIF",
    ]


def test_template_rejects_unknown_template() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        ScriptService(FakeRpcClient()).template("vault")  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_SCRIPT_TEMPLATE"


def test_test_spend_uses_testmempoolaccept() -> None:
    tx_hex = "02000000000100"
    rpc = FakeRpcClient([{"txid": "aa", "allowed": True}])

    result = ScriptService(rpc).test_spend(tx_hex)  # type: ignore[arg-type]

    assert result["accepted"] is True
    assert result["transaction_hex"] == tx_hex
    assert rpc.calls == [("testmempoolaccept", [[tx_hex]])]


def test_create_op_return_transaction_builds_funds_signs_and_tests() -> None:
    rpc = FakeRpcClient()

    result = ScriptService(rpc).create_op_return("demo", "labs", "text", None, None, False, False)  # type: ignore[arg-type]

    assert result["data_hex"] == "6c616273"
    assert result["data_bytes"] == 4
    assert result["op_return_script_hex"] == "6a046c616273"
    assert result["unsigned_hex"] == "00aa"
    assert result["funded_hex"] == "00bb"
    assert result["signed_hex"] == "00cc"
    assert result["complete"] is True
    assert result["txid"] == "11" * 32
    assert result["broadcast"] is False
    assert ("getbalances", []) in rpc.calls
    assert ("createrawtransaction", [[], [{"data": "6c616273"}]]) in rpc.calls
    assert ("fundrawtransaction", ["00aa"]) in rpc.calls
    assert ("signrawtransactionwithwallet", ["00bb"]) in rpc.calls
    assert ("testmempoolaccept", [["00cc"]]) in rpc.calls


def test_create_op_return_transaction_can_add_payment_output_and_broadcast() -> None:
    rpc = FakeRpcClient()

    result = ScriptService(rpc).create_op_return("demo", "cafe", "hex", "bcrt1qdest", 0.25, True, True)  # type: ignore[arg-type]

    assert result["data_hex"] == "cafe"
    assert result["destination_address"] == "bcrt1qdest"
    assert result["amount_btc"] == 0.25
    assert result["txid"] == "22" * 32
    assert result["confirmation_block_hashes"] == ["block-0"]
    assert ("validateaddress", ["bcrt1qdest"]) in rpc.calls
    assert ("getbalances", []) in rpc.calls
    assert ("createrawtransaction", [[], [{"bcrt1qdest": 0.25}, {"data": "cafe"}]]) in rpc.calls
    assert ("sendrawtransaction", ["00cc"]) in rpc.calls
    assert ("generatetoaddress", [1, "bcrt1qmine"]) in rpc.calls


def test_create_op_return_transaction_rejects_large_payload() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        ScriptService(FakeRpcClient()).create_op_return("demo", "aa" * 81, "hex")  # type: ignore[arg-type]

    assert exc_info.value.code == "OP_RETURN_DATA_TOO_LARGE"


def test_create_op_return_transaction_blocks_non_regtest() -> None:
    with pytest.raises(BitScopeError) as exc_info:
        ScriptService(FakeRpcClient(network="mainnet")).create_op_return("demo", "labs", "text")  # type: ignore[arg-type]

    assert exc_info.value.code == "REGTEST_ONLY"


def test_create_op_return_transaction_reports_insufficient_mature_balance_before_funding() -> None:
    class ImmatureRpc(FakeRpcClient):
        def call(self, method: str, params: list[object] | None = None, wallet_name: str | None = None) -> object:
            self.calls.append((method, params))
            if method == "getbalances":
                return {"mine": {"trusted": 0.0, "immature": 50.0}}
            return super().call(method, params, wallet_name)

    rpc = ImmatureRpc()

    with pytest.raises(BitScopeError) as exc_info:
        ScriptService(rpc).create_op_return("demo", "labs", "text")  # type: ignore[arg-type]

    assert exc_info.value.code == "OP_RETURN_INSUFFICIENT_MATURE_FUNDS"
    assert ("fundrawtransaction", ["00aa"]) not in rpc.calls
