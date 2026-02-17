"""Tests for index reconciliation idempotency."""

from bbot_server import BBOTServer
from bbot_server.utils.db import (
    desired_indexes_from_model,
    parse_existing_indexes,
    compute_index_diff,
    merge_desired_indexes,
)


async def test_reconcile_indexes_is_idempotent():
    """
    After reconcile_all_indexes runs, a second run should produce no changes.

    This test:
    1. Sets up BBOTServer (which calls reconcile_all_indexes)
    2. Groups applets by collection
    3. For each collection, merges desired indexes from all models
    4. Computes diff against actual state
    5. Asserts the diff is empty
    """
    bbot_server = BBOTServer()
    await bbot_server.setup()

    # Group applets by collection (same logic as reconcile_all_indexes)
    applets_by_collection = {}
    for applet in bbot_server.all_child_applets(include_self=True):
        if applet.collection is None or applet.model is None:
            continue
        collection_name = applet.collection.full_name
        if collection_name not in applets_by_collection:
            applets_by_collection[collection_name] = {"collection": applet.collection, "models": []}
        applets_by_collection[collection_name]["models"].append(applet.model)

    # Check each collection
    for collection_name, data in applets_by_collection.items():
        collection = data["collection"]
        models = data["models"]

        # Merge desired indexes from all models
        all_desired = [desired_indexes_from_model(m) for m in models]
        desired, desired_text = merge_desired_indexes(all_desired)

        # Get actual state from MongoDB
        indexes_cursor = await collection.list_indexes()
        indexes_list = [idx async for idx in indexes_cursor]
        existing, existing_text = parse_existing_indexes(indexes_list)

        # Compute diff
        diff = compute_index_diff(desired, desired_text, existing, existing_text)

        # Assert no changes needed
        assert diff["drop"] == [], f"{collection_name}: unexpected indexes to drop: {diff['drop']}"
        assert diff["create"] == [], f"{collection_name}: unexpected indexes to create: {diff['create']}"
        assert diff["drop_text"] is False, f"{collection_name}: unexpected text index drop"
        assert diff["create_text"] is None, f"{collection_name}: unexpected text index create: {diff['create_text']}"
