def test_asset_model_fields():
    from bbot_server.assets import ASSET_FIELD_MODELS
    from bbot_server.assets.custom_fields import CustomAssetFields

    assert len(ASSET_FIELD_MODELS) > 0
    for model in ASSET_FIELD_MODELS:
        assert CustomAssetFields in model.mro()
