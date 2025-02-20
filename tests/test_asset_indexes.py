from tests.test_applets.base import BaseAppletTest


class TestAssetIndexes(BaseAppletTest):
    async def setup(self):
        assert self.bbot_server.assets.open_ports.model.indexed_fields() == {
            "host": "indexed",
            "open_ports": "indexed",
            "reverse_host": "indexed",
            "type": "indexed",
        }
        indexes = await self.bbot_server.assets.collection.list_indexes().to_list()
        indexed_fields = [list(idx["key"].keys())[0] for idx in indexes]
        for applet in self.bbot_server.all_child_applets:
            if applet.model is not None:
                for field in applet.model.indexed_fields():
                    assert field in indexed_fields
