import orjson
from typing import Optional
from pydantic import BaseModel, create_model, Field


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


def combine_pydantic_models(models, model_name, make_optional=False):
    """
    Combines multiple pydantic models into a single model.
    """
    combined_fields = {}
    field_origins = {}  # Track which model each field came from

    for model in models:
        try:
            model_fields = model.model_fields
        except AttributeError as e:
            raise ValueError(f"Model {model.__name__} has no attribute 'model_fields'") from e

        for field_name, field in model_fields.items():
            if field_name in combined_fields:
                existing_field = combined_fields[field_name]
                if existing_field.annotation != field.annotation:
                    raise ValueError(
                        f"Conflicting types for field '{field_name}': "
                        f"{field_origins[field_name]}: {existing_field.annotation} vs "
                        f"{model.__name__}: {field.annotation}"
                    )
            else:
                combined_fields[field_name] = field
                field_origins[field_name] = model.__name__

    # Create the new model with all collected fields
    combined_model = create_model(
        model_name,
        __base__=BaseModel,
        **{
            field_name: (
                (Optional[field.annotation] if make_optional else field.annotation),
                (Field(default=None) if make_optional else field),
            )
            for field_name, field in combined_fields.items()
        },
    )
    return combined_model
