import orjson
import logging
import inspect
from bson import ObjectId
from functools import wraps
from types import UnionType
from inspect import signature
from pydantic import BaseModel, create_model
from datetime import datetime, timezone, timedelta
from typing import Any, Union, get_origin, get_args, get_type_hints, Annotated

from bbot_server.errors import BBOTServerValueError

log = logging.getLogger("bbot_server.utils.misc")


def unwrap_type_annotation(type_anno) -> Any:
    """
    Recursively unwrap type annotations to get the underlying type.

    Handles:
    - Direct types: returns as-is
    - Annotated types: Annotated[Model, ...] -> Model
    - Optional types: Model | None, Union[Model, None] -> Model
    - Nested: Annotated[Model | None, ...] -> Model

    Returns the unwrapped type, or None if only None was found.
    """
    origin = get_origin(type_anno)

    # Handle Annotated[Type, metadata...] - unwrap to get the actual type
    if origin is Annotated:
        args = get_args(type_anno)
        if args:
            return unwrap_type_annotation(args[0])

    # Handle Union[Type1, Type2, ...] or Type | None
    elif origin in (Union, UnionType):
        for arg in get_args(type_anno):
            # Skip None type
            if arg is type(None):
                continue
            # Recursively unwrap this union member
            return unwrap_type_annotation(arg)

    # Base case: return the type as-is
    return type_anno


def detect_translatable_function(fn):
    """
    Detecth whether a function meets the requirements for human-friendly translation.
        i.e. if the function accepts only one arg that is also a pydantic model, it is eligible for translation

    Returns a two-tuple of the parameter name and pydantic model class, if eligible
    """
    type_hints = get_type_hints(fn)

    # Get all parameters excluding 'self' and 'return'
    params = {k: v for k, v in type_hints.items() if k not in ("self", "return")}

    # If there's exactly one parameter
    if len(params) == 1:
        param_name, type_anno = next(iter(params.items()))
        unwrapped_type = unwrap_type_annotation(type_anno)

        # if the single param's annotation type is a pydantic model
        if isinstance(unwrapped_type, type) and issubclass(unwrapped_type, BaseModel):
            return param_name, unwrapped_type

    return None, None


def convert_human_args(fn, param_name, model_class, *args, **kwargs):
    model_param = kwargs.get(param_name)

    # if the param's name and type match the annotation, we can return as is
    if model_param and isinstance(model_param, BaseModel):
        # Already have the model, pass through
        return args, kwargs

    # Try to bind the arguments to understand what we received
    # This handles the case where the correct model is passed in via args instead of kwargs
    bound = None
    try:
        fn_sig = signature(fn)
        bound = fn_sig.bind_partial(*args, **kwargs)
    except TypeError:
        pass

    # if the bind worked,
    if bound is not None:
        bound.apply_defaults()
        model_param = bound.arguments.get(param_name)

        # Check if the parameter is already in the bound arguments
        if model_param and isinstance(model_param, model_class):
            # The model was passed positionally, pass through
            return args, kwargs

    # Otherwise, assume kwargs are individual model attributes
    # Build the model from those kwargs and call with proper args
    model_instance = model_class(**kwargs)
    return args, {param_name: model_instance}


def human_friendly_kwargs(fn):
    """
    This function wrapper makes BBOT server functions more human-friendly.

    For endpoints that accept only one pydantic model (e.g. an Query object with a bunch of attributes),
    instead of having to import and instantiate this pydantic model, you can simply call the function,
    and the pydantic model will be automatically instantiated from your kwargs.

    E.g. instead, of doing:

        from bbot_server.modules.findings_models import FindingQuery

        query = FindingQuery(search="apache")
        bbserver.query_findings(query)

    You can do:

        bbserver.query_findings(search="apache")

    """
    param_name, model_class = detect_translatable_function(fn)

    if param_name is not None:
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def wrapper(*args, **kwargs):
                args, kwargs = convert_human_args(fn, param_name, model_class, *args, **kwargs)
                return await fn(*args, **kwargs)
        elif inspect.isasyncgenfunction(fn):

            @wraps(fn)
            async def wrapper(*args, **kwargs):
                args, kwargs = convert_human_args(fn, param_name, model_class, *args, **kwargs)
                async for _ in fn(*args, **kwargs):
                    yield _
        else:

            @wraps(fn)
            def wrapper(*args, **kwargs):
                args, kwargs = convert_human_args(fn, param_name, model_class, *args, **kwargs)
                return fn(*args, **kwargs)

        return wrapper

    return fn


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


def timestamp_to_human(timestamp: float, include_hours: bool = True) -> str:
    if include_hours:
        format_str = "%Y-%m-%d %H:%M:%S"
    else:
        format_str = "%Y-%m-%d"
    return datetime.fromtimestamp(timestamp).strftime(format_str)


def orjson_serializer(obj: Any) -> Any:
    """
    Enable orjson to serialize Mongo's ObjectIds
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    return obj


def smart_encode(obj: Any) -> bytes:
    # handle both python and pydantic objects, as well as strings
    if isinstance(obj, BaseModel):
        return obj.model_dump_json().encode()
    elif isinstance(obj, str):
        return obj.encode()
    elif isinstance(obj, bytes):
        return obj
    else:
        return orjson.dumps(obj, default=orjson_serializer)


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
            raise ValueError(f'Model {model.__name__} has no attribute "model_fields"') from e

        for field_name, field in model_fields.items():
            if field_name in combined_fields:
                current_annotation, _ = combined_fields[field_name]
                if field.annotation != current_annotation:
                    raise ValueError(
                        f'Field "{field_name}" on {model.__name__} already exists, but with a different annotation: ({current_annotation} vs {field.annotation})'
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


# fmt: off
ALLOWED_QUERY_OPERATORS = {
    # Query Operators (excluding $where, $expr)
    "$eq", "$gt", "$gte", "$in", "$lt", "$lte", "$ne", "$nin",
    "$and", "$not", "$nor", "$or",
    "$exists", "$type",
    "$jsonSchema", "$mod", "$search", "$text", "$regex",
    "$geoIntersects", "$geoWithin", "$near", "$nearSphere",
    "$all", "$elemMatch", "$size",
    "$bitsAllClear", "$bitsAllSet", "$bitsAnyClear", "$bitsAnySet",
    "$comment"
}
# fmt: on


def _sanitize_mongo_query(data: Any) -> Any:
    """
    Sanitizes a MongoDB query dictionary using a whitelist approach.
    Throws a ValueError if any unauthorized operator (key starting with $) is found.
    Focused on query operators for find() or $match.
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            key = key.strip()
            if key.startswith("$") and key not in ALLOWED_QUERY_OPERATORS:
                raise BBOTServerValueError(f"Unauthorized MongoDB query operator: {key}")
            sanitized[key] = _sanitize_mongo_query(value)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_mongo_query(item) for item in data]
    return data


# fmt: off
ALLOWED_AGG_OPERATORS = {
    # We intentionally exclude $match because it"s automatically added and sanitized separately

    # Aggregation Pipeline Stages (excluding $out, $merge, $lookup, $graphLookup)
    "$addFields", "$bucket", "$bucketAuto", "$collStats", "$count",
    "$densify", "$documents", "$facet", "$fill", "$geoNear",
    "$group", "$indexStats", "$limit", "$listSessions",
    "$planCacheStats", "$project", "$redact",
    "$replaceRoot", "$replaceWith", "$sample", "$search", "$searchMeta",
    "$set", "$setWindowFields", "$skip", "$sort", "$sortByCount",
    "$unionWith", "$unset", "$unwind",

    # Aggregation Expression Operators (excluding $function, $accumulator)
    # Arithmetic
    "$abs", "$add", "$ceil", "$divide", "$exp", "$floor", "$ln",
    "$log", "$log10", "$mod", "$multiply", "$pow", "$round",
    "$sqrt", "$subtract", "$trunc",

    # Array
    "$arrayElemAt", "$arrayToObject", "$concatArrays", "$filter",
    "$first", "$in", "$indexOfArray", "$isArray", "$last", "$map",
    "$objectToArray", "$range", "$reduce", "$reverseArray", "$size",
    "$slice", "$sortArray", "$zip",

    # Boolean
    "$and", "$not", "$or",

    # Comparison
    "$cmp", "$eq", "$gt", "$gte", "$lt", "$lte", "$ne",

    # Conditional
    "$cond", "$ifNull", "$switch",

    # Data Size
    "$binarySize", "$bsonSize",

    # Date
    "$dateAdd", "$dateDiff", "$dateFromParts", "$dateFromString",
    "$dateSubtract", "$dateToParts", "$dateToString", "$dateTrunc",
    "$dayOfMonth", "$dayOfWeek", "$dayOfYear", "$hour",
    "$isoDayOfWeek", "$isoWeek", "$isoWeekYear", "$millisecond",
    "$minute", "$month", "$second", "$toDate", "$week", "$year",

    # Diagnostic
    "$getField", "$rand", "$sampleRate", "$tsIncrement", "$tsSecond",

    # Literal
    "$literal",

    # Miscellaneous
    "$mergeObjects",

    # Object
    "$getField", "$mergeObjects", "$objectToArray", "$setField",

    # Set
    "$allElementsTrue", "$anyElementTrue", "$setDifference",
    "$setEquals", "$setIntersection", "$setIsSubset", "$setUnion",

    # String
    "$concat", "$dateFromString", "$dateToString", "$indexOfBytes",
    "$indexOfCP", "$ltrim", "$regexFind", "$regexFindAll",
    "$regexMatch", "$replaceAll", "$replaceOne", "$rtrim", "$split",
    "$strLenBytes", "$strLenCP", "$strcasecmp", "$substr",
    "$substrBytes", "$substrCP", "$toLower", "$toString", "$trim",
    "$toUpper",

    # Text Search
    "$meta",

    # Trigonometry
    "$sin", "$cos", "$tan", "$asin", "$acos", "$atan", "$atan2",
    "$asinh", "$acosh", "$atanh", "$degreesToRadians", "$radiansToDegrees",

    # Type
    "$convert", "$isNumber", "$toBool", "$toDate", "$toDecimal",
    "$toDouble", "$toInt", "$toLong", "$toObjectId", "$toString", "$type",

    # Accumulators (for $group)
    "$addToSet", "$avg", "$bottom", "$bottomN", "$count", "$first",
    "$firstN", "$last", "$lastN", "$max", "$maxN", "$mergeObjects",
    "$min", "$minN", "$push", "$stdDevPop", "$stdDevSamp", "$sum",
    "$top", "$topN",

    # Window Operators (for $setWindowFields)
    "$addToSet", "$avg", "$count", "$covariancePop", "$covarianceSamp",
    "$denseRank", "$derivative", "$documentNumber", "$expMovingAvg",
    "$first", "$integral", "$last", "$linearFill", "$locf", "$max",
    "$min", "$push", "$rank", "$shift", "$stdDevPop", "$stdDevSamp", "$sum",

    # Variable
    "$let"
}
# fmt: on


def _sanitize_mongo_aggregation(data: Any) -> Any:
    """
    Sanitizes a MongoDB aggregation pipeline or expression dictionary using a whitelist approach.
    Throws a ValueError if any unauthorized operator or stage (key starting with $) is found.
    Focused on aggregation stages and expressions.
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            key = key.strip()
            if key.startswith("$") and key not in ALLOWED_AGG_OPERATORS:
                raise BBOTServerValueError(f"Unauthorized MongoDB aggregation operator: {key}")
            sanitized[key] = _sanitize_mongo_aggregation(value)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_mongo_aggregation(item) for item in data]
    return data
