def test_asset_model_fields():
    from bbot_server.assets import CustomAssetFields
    from bbot_server.modules import ASSET_FIELD_MODELS

    assert len(ASSET_FIELD_MODELS) > 0
    for model in ASSET_FIELD_MODELS:
        assert CustomAssetFields in model.mro()
