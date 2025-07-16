from bbot_server import BBOTServer
from pydantic import computed_field
from typing import Annotated
from bbot_server.models.base import BaseBBOTServerModel


class IndexTestModel(BaseBBOTServerModel):
    # Regular fields with different index types
    regular_field: Annotated[str, "indexed"] = "test"
    text_field: Annotated[str, "indexed-text"] = "test"
    compound_field: Annotated[str, "indexed", "unique"] = "test"
    non_indexed: str = "test"

    # Computed fields with different index types
    @computed_field
    @property
    def computed_field_test(self) -> Annotated[str, "indexed"]:
        return "test"

    @computed_field
    @property
    def computed_text(self) -> Annotated[str, "indexed-text"]:
        return "test"

    @computed_field
    @property
    def computed_compound(self) -> Annotated[str, "indexed", "unique"]:
        return "test"

    @computed_field
    @property
    def computed_non_indexed(self) -> str:
        return "test"


async def test_indexed_fields():
    # Test both regular and computed fields
    indexed = IndexTestModel.indexed_fields()

    # Check regular fields
    assert "regular_field" in indexed
    assert indexed["regular_field"] == ["indexed"]

    assert "text_field" in indexed
    assert indexed["text_field"] == ["indexed-text"]

    assert "compound_field" in indexed
    assert set(indexed["compound_field"]) == {"indexed", "unique"}

    assert "non_indexed" not in indexed

    # Check computed fields
    assert "computed_field_test" in indexed
    assert indexed["computed_field_test"] == ["indexed"]

    assert "computed_text" in indexed
    assert indexed["computed_text"] == ["indexed-text"]

    assert "computed_compound" in indexed
    assert set(indexed["computed_compound"]) == {"indexed", "unique"}

    assert "computed_non_indexed" not in indexed


async def test_asset_indexes():
    bbot_server = BBOTServer()
    await bbot_server.setup()

    assert bbot_server.assets.model.indexed_fields() == {
        "host": ["indexed"],
        "scope": ["indexed"],
        "created": ["indexed"],
        "modified": ["indexed"],
        "dns_links": ["indexed"],
        "open_ports": ["indexed"],
        "netloc": ["indexed"],
        "reverse_host": ["indexed"],
        "type": ["indexed"],
        "port": ["indexed"],
        "technologies": ["indexed", "indexed-text"],
        "url": ["indexed"],
        "cloud_providers": ["indexed"],
        "findings": ["indexed", "indexed-text"],
        "finding_max_severity_score": ["indexed"],
        "finding_severities": ["indexed"],
    }
    for applet in bbot_server.all_child_applets(include_self=True):
        if applet.model is not None:
            index_cursor = await applet.collection.list_indexes()
            indexes = await index_cursor.to_list()
            indexed_fields = []
            for idx in indexes:
                # Handle text indexes specially
                if "_fts" in idx["key"] and "_ftsx" in idx["key"]:
                    # For text indexes, the field name is in the weights
                    if "weights" in idx:
                        indexed_fields.extend(idx["weights"].keys())
                else:
                    # For regular indexes, get the first key
                    indexed_fields.extend(idx["key"].keys())

            for field in applet.model.indexed_fields():
                assert field in indexed_fields, (
                    f"{applet.name} (model: {applet.model.__name__}) has no index on {field}. indexes: {indexes}"
                )
