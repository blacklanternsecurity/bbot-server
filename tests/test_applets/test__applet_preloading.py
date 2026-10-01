def test_asset_model_fields():
    from bbot_server.assets import CustomAssetFields
    from bbot_server.modules import ASSET_FIELD_MODELS

    assert len(ASSET_FIELD_MODELS) > 0
    for model in ASSET_FIELD_MODELS:
        assert CustomAssetFields in model.mro()


# every module-level CustomAssetFields subclass in an *_api.py file
# must end up as a field on the merged asset model
def test_custom_asset_fields_merged_into_asset_model():
    from bbot_server.assets import Asset

    # EmailsFields was previously nested inside EmailsApplet, where the AST
    # preloader could not see it, so its field was silently missing from Asset
    assert "emails" in Asset.model_fields
