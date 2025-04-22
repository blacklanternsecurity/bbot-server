import orjson
import logging
from pydantic import BaseModel, create_model
from datetime import datetime, timezone, timedelta

log = logging.getLogger("bbot_server.utils.misc")


def utc_now() -> float:
    return datetime.now(timezone.utc).timestamp()


def seconds_to_human(seconds: float) -> str:
    """
    Convert seconds to a human-friendly string representation using timedelta.
    Only includes time units that are non-zero, from largest to smallest.

    Args:
        seconds: Number of seconds to convert

    Returns:
        Human-readable string like "2 days, 5 hours, 30 minutes"
    """
    # Convert seconds to timedelta
    delta = timedelta(seconds=seconds)

    # Extract components
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Build the string parts
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 or not parts:  # Include seconds if non-zero or if all other units are zero
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    # Join the parts with commas
    return ", ".join(parts)


def timestamp_to_human(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def smart_encode(obj):
    # handle both python and pydantic objects, as well as strings
    if isinstance(obj, BaseModel):
        return obj.model_dump_json().encode()
    elif isinstance(obj, str):
        return obj.encode()
    elif isinstance(obj, bytes):
        return obj
    else:
        return orjson.dumps(obj)


def combine_pydantic_models(models, model_name, base_model=BaseModel):
    """
    Combines multiple pydantic models into a single model.

    Args:
        models: list of pydantic models to combine
        model_name: name of the new model
    """
    combined_fields = {field_name: (field.annotation, field) for field_name, field in base_model.model_fields.items()}

    for model in models:
        try:
            model_fields = model.model_fields
        except AttributeError as e:
            raise ValueError(f"Model {model.__name__} has no attribute 'model_fields'") from e

        for field_name, field in model_fields.items():
            if field_name in combined_fields:
                current_annotation, _ = combined_fields[field_name]
                if field.annotation != current_annotation:
                    raise ValueError(
                        f"Field '{field_name}' on {model.__name__} already exists, but with a different annotation: ({current_annotation} vs {field.annotation})"
                    )
            else:
                combined_fields[field_name] = (field.annotation, field)

    # Create the new model with all collected fields
    combined_model = create_model(
        model_name,
        __base__=base_model,
        **combined_fields,
    )
    return combined_model
