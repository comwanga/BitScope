from app.services.key_service import KeyEducationService


def test_key_guide_is_educational_and_private_key_free() -> None:
    guide = KeyEducationService().guide()

    assert guide["safety_model"]["handles_private_keys"] is False  # type: ignore[index]
    rendered = str(guide).lower()
    assert "seed words" in rendered
    assert "xprv" in rendered
    assert "wif" in rendered
    assert "xpub" in rendered
    assert "psbt" in rendered


def test_key_guide_includes_derivation_descriptors_and_hardware_flow() -> None:
    guide = KeyEducationService().guide()

    assert len(guide["derivation_paths"]) >= 4  # type: ignore[arg-type]
    assert len(guide["descriptor_recipes"]) >= 3  # type: ignore[arg-type]
    assert len(guide["psbt_flow"]) >= 5  # type: ignore[arg-type]
    assert "getdescriptorinfo" in guide["rpc_methods"]  # type: ignore[operator]
    assert "decodepsbt" in guide["rpc_methods"]  # type: ignore[operator]
