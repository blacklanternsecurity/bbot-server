"""Database utility functions."""

import logging

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, OperationFailure

log = logging.getLogger(__name__)


def merge_desired_indexes(all_desired):
    """
    Merge multiple desired index specs into one.

    Args:
        all_desired: list of (indexes_dict, text_fields_set) tuples

    Returns:
        tuple: (merged_indexes dict, merged_text_fields set)
    """
    merged_indexes = {}
    merged_text = set()

    for indexes, text_fields in all_desired:
        for name, spec in indexes.items():
            existing = merged_indexes.get(name)
            if existing and existing != spec:
                raise ValueError(f"Conflicting index specs for {name}: {existing} vs {spec}")
            merged_indexes[name] = spec
        merged_text.update(text_fields)

    return merged_indexes, merged_text


def desired_indexes_from_model(model):
    """
    Compute desired index specifications from a model's annotations.

    Returns:
        tuple: (indexes dict, text_fields set)
            - indexes: {name: {"key": [...], "unique": bool, "sparse": bool}}
            - text_fields: set of field names for the text index
    """
    indexes = {}
    text_fields = set()

    for fieldname, metadata in model.indexed_fields().items():
        unique = "unique" in metadata
        if "indexed" in metadata:
            name = f"{fieldname}_1"
            indexes[name] = {"key": [(fieldname, ASCENDING)], "unique": unique, "sparse": unique}
        if "indexed-text" in metadata:
            text_fields.add(fieldname)
        for m in metadata:
            if isinstance(m, str) and m.startswith("indexed-compound:"):
                fields = [fieldname] + m.split(":")[-1].split(",")
                key = [(f, ASCENDING) for f in fields]
                name = "_".join(f"{f}_1" for f in fields)
                indexes[name] = {"key": key, "unique": True, "sparse": False}

    return indexes, text_fields


def parse_existing_indexes(indexes_list):
    """
    Parse MongoDB index list into normalized format.

    Returns:
        tuple: (indexes dict, text_fields set)
    """
    indexes = {}
    text_fields = set()

    for idx in indexes_list:
        name = idx["name"]
        if name == "_id_":
            continue
        if "text" in idx["key"].values():
            text_fields = set(idx.get("weights", {}).keys())
            indexes[name] = {"text": True}
        else:
            indexes[name] = {
                "key": list(idx["key"].items()),
                "unique": idx.get("unique", False),
                "sparse": idx.get("sparse", False),
            }

    return indexes, text_fields


def compute_index_diff(desired, desired_text, existing, existing_text):
    """
    Compute the diff between desired and existing indexes.

    Returns:
        dict with keys:
            - drop: list of index names to drop
            - create: list of {"name": ..., "key": ..., "unique": ..., "sparse": ...}
            - drop_text: bool - whether to drop existing text index
            - create_text: list of fields for new text index, or None
    """
    diff = {"drop": [], "create": [], "drop_text": False, "create_text": None}

    # Text index diff
    if desired_text != existing_text:
        if existing_text:
            diff["drop_text"] = True
        if desired_text:
            diff["create_text"] = sorted(desired_text)

    # Find indexes to drop (exist but not desired)
    for name, spec in existing.items():
        if spec.get("text"):
            continue
        if name not in desired:
            diff["drop"].append(name)

    # Find indexes to create or recreate
    for name, spec in desired.items():
        ex = existing.get(name)
        if ex and not ex.get("text"):
            if ex["key"] == spec["key"] and ex["unique"] == spec["unique"] and ex["sparse"] == spec["sparse"]:
                continue
            # needs recreation
            diff["drop"].append(name)
        diff["create"].append({"name": name, **spec})

    return diff


async def apply_index_diff(collection, diff, existing):
    """Apply index diff to a collection."""
    # Apply text index changes
    if diff["drop_text"]:
        text_idx_name = next((n for n, s in existing.items() if s.get("text")), None)
        if text_idx_name:
            log.debug(f"Dropping text index {text_idx_name}")
            await collection.drop_index(text_idx_name)
    if diff["create_text"]:
        key = [(f, "text") for f in diff["create_text"]]
        log.debug(f"Creating text index: {key}")
        await collection.create_index(key)

    # Drop indexes
    for name in diff["drop"]:
        log.debug(f"Dropping index {name}")
        await collection.drop_index(name)

    # Create indexes
    for spec in diff["create"]:
        log.debug(f"Creating index {spec['name']}: {spec['key']}")
        try:
            await collection.create_index(spec["key"], unique=spec["unique"], sparse=spec["sparse"])
        except DuplicateKeyError as e:
            log.error(f"Cannot create unique index {spec['name']}: duplicate values exist. {e}")
        except OperationFailure as e:
            if "already exists" in str(e):
                log.debug(f"Index {spec['name']} already exists")
            else:
                raise
