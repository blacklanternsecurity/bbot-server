"""Database utility functions."""

from pymongo import ASCENDING


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
