import orjson
import logging
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, create_model, Field


log = logging.getLogger("bbot_server.utils.misc")


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


def combine_pydantic_models(models, model_name, base_model=BaseModel, make_optional=False):
    """
    Combines multiple pydantic models into a single model.

    Args:
        models: list of pydantic models to combine
        model_name: name of the new model
        make_optional: if True, make all fields optional
    """
    combined_fields = {field_name: (field.annotation, field) for field_name, field in base_model.model_fields.items()}

    for model in models:
        try:
            model_fields = model.model_fields
        except AttributeError as e:
            raise ValueError(f"Model {model.__name__} has no attribute 'model_fields'") from e

        for field_name, field in model_fields.items():
            annotation = Optional[field.annotation] if make_optional else field.annotation

            if make_optional:
                field.default = None

            if field_name in combined_fields:
                current_annotation, _ = combined_fields[field_name]
                if annotation != current_annotation:
                    raise ValueError(
                        f"Field '{field_name}' on {model.__name__} already exists, but with a different annotation: ({current_annotation} vs {annotation})"
                    )
            else:
                combined_fields[field_name] = (annotation, field)

    # Create the new model with all collected fields
    combined_model = create_model(
        model_name,
        __base__=base_model,
        **combined_fields,
    )
    return combined_model
