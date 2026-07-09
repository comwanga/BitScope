class KeyEducationService:
    def guide(self) -> dict[str, object]:
        derivation_paths = [
            {
                "purpose": "BIP44 legacy",
                "path": "m/44h/coin_typeh/accounth/change/index",
                "descriptor": "pkh([f23a9c01/44h/1h/0h]tpub.../0/*)",
                "script_type": "P2PKH",
                "notes": "Legacy wallets use larger scriptSigs and are mostly here for historical context.",
            },
            {
                "purpose": "BIP49 nested SegWit",
                "path": "m/49h/coin_typeh/accounth/change/index",
                "descriptor": "sh(wpkh([f23a9c01/49h/1h/0h]upub.../0/*))",
                "script_type": "P2SH-P2WPKH",
                "notes": "Nested SegWit wraps a witness program in P2SH for older wallet compatibility.",
            },
            {
                "purpose": "BIP84 native SegWit",
                "path": "m/84h/coin_typeh/accounth/change/index",
                "descriptor": "wpkh([f23a9c01/84h/1h/0h]vpub.../0/*)",
                "script_type": "P2WPKH",
                "notes": "Native SegWit is the common default for modern single-sig wallets.",
            },
            {
                "purpose": "BIP86 single-key Taproot",
                "path": "m/86h/coin_typeh/accounth/change/index",
                "descriptor": "tr([f23a9c01/86h/1h/0h]vpub.../0/*)",
                "script_type": "P2TR",
                "notes": "BIP86 describes key-path-only Taproot receive addresses.",
            },
        ]

        psbt_flow = [
            {
                "step": 1,
                "role": "Coordinator",
                "action": "Build a funded PSBT from watch-only descriptors or wallet UTXOs.",
                "bitcoin_core_rpc": "walletcreatefundedpsbt",
                "private_key_boundary": "No private keys required.",
            },
            {
                "step": 2,
                "role": "Reviewer",
                "action": "Decode the PSBT and verify inputs, outputs, change, fee, and locktime.",
                "bitcoin_core_rpc": "decodepsbt",
                "private_key_boundary": "Review can happen on an online machine.",
            },
            {
                "step": 3,
                "role": "Hardware wallet",
                "action": "Sign only after displaying the destination and amount on the device screen.",
                "bitcoin_core_rpc": "walletprocesspsbt or external signer flow",
                "private_key_boundary": "Private keys remain on the hardware device.",
            },
            {
                "step": 4,
                "role": "Finalizer",
                "action": "Combine signatures if needed, finalize scripts and witnesses, then extract raw transaction hex.",
                "bitcoin_core_rpc": "combinepsbt, finalizepsbt",
                "private_key_boundary": "Finalization does not require private keys once signatures are present.",
            },
            {
                "step": 5,
                "role": "Broadcaster",
                "action": "Broadcast only after policy checks and final human review.",
                "bitcoin_core_rpc": "testmempoolaccept, sendrawtransaction",
                "private_key_boundary": "Broadcasting reveals the signed transaction to the network.",
            },
        ]

        descriptor_recipes = [
            {
                "name": "Native SegWit receive",
                "descriptor": "wpkh([f23a9c01/84h/1h/0h]vpub.../0/*)",
                "change_descriptor": "wpkh([f23a9c01/84h/1h/0h]vpub.../1/*)",
                "purpose": "Public receive/change address derivation for a testnet or regtest account.",
            },
            {
                "name": "Taproot receive",
                "descriptor": "tr([f23a9c01/86h/1h/0h]vpub.../0/*)",
                "change_descriptor": "tr([f23a9c01/86h/1h/0h]vpub.../1/*)",
                "purpose": "Public BIP86 single-key Taproot derivation.",
            },
            {
                "name": "Sorted multisig watch-only",
                "descriptor": "wsh(sortedmulti(2,[f23a9c01/48h/1h/0h/2h]vpubA.../0/*,[a1b2c3d4/48h/1h/0h/2h]vpubB.../0/*,[deadbeef/48h/1h/0h/2h]vpubC.../0/*))",
                "change_descriptor": "wsh(sortedmulti(2,[f23a9c01/48h/1h/0h/2h]vpubA.../1/*,[a1b2c3d4/48h/1h/0h/2h]vpubB.../1/*,[deadbeef/48h/1h/0h/2h]vpubC.../1/*))",
                "purpose": "Watch-only multisig coordination without importing signer private keys.",
            },
        ]

        return {
            "safety_model": {
                "handles_private_keys": False,
                "allowed_inputs": ["xpub/tpub/vpub placeholders", "master fingerprint", "derivation path", "descriptor text", "PSBT text"],
                "blocked_inputs": ["seed words", "xprv/tprv private extended keys", "WIF private keys", "hardware-wallet PINs"],
                "message": "This page is educational only. It never asks for seed words, private extended keys, WIF keys, or device PINs.",
            },
            "derivation_paths": derivation_paths,
            "descriptor_recipes": descriptor_recipes,
            "psbt_flow": psbt_flow,
            "watch_only_commands": [
                "bitcoin-cli createwallet watch-only true true '' false true",
                "bitcoin-cli -rpcwallet=watch-only importdescriptors '[{\"desc\":\"wpkh([f23a9c01/84h/1h/0h]vpub.../0/*)#checksum\",\"active\":true,\"range\":[0,1000],\"timestamp\":\"now\"}]'",
                "bitcoin-cli -rpcwallet=watch-only walletcreatefundedpsbt [] '[{\"bcrt1...\":0.01000000}]'",
                "bitcoin-cli decodepsbt <base64-psbt>",
            ],
            "hardware_wallet_notes": [
                "Verify the destination address and amount on the hardware-wallet display, not only in host software.",
                "Export public descriptors or xpubs from the device; never type seed words into BitScope.",
                "Use PSBT files or QR handoff when possible so the signing device remains isolated.",
                "A watch-only wallet can construct PSBTs and track addresses without private keys.",
            ],
            "cli_commands": [
                "bitcoin-cli getdescriptorinfo '<descriptor>'",
                "bitcoin-cli deriveaddresses '<descriptor>#checksum' '[0,2]'",
                "bitcoin-cli decodepsbt <base64-psbt>",
                "bitcoin-cli finalizepsbt <base64-psbt>",
            ],
            "rpc_methods": ["getdescriptorinfo", "deriveaddresses", "importdescriptors", "walletcreatefundedpsbt", "decodepsbt", "finalizepsbt"],
            "concepts": ["Descriptor", "xpub", "Key origin", "Derivation path", "Watch-only wallet", "Hardware wallet", "PSBT"],
            "explanation": (
                "Descriptors combine script templates, public keys, origin fingerprints, and derivation paths. Extended public "
                "keys can derive addresses but cannot sign. PSBTs let an online coordinator build and review a transaction while "
                "a hardware wallet keeps private keys isolated."
            ),
        }
