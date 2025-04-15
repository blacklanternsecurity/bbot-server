import pytest
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from bbot_server.utils.misc import combine_pydantic_models


class ModelA(BaseModel):
    field1: int = Field(default=10)
    field2: str = Field(default="default")
    field3: float = Field(default=1.0)


class ModelB(BaseModel):
    field3: float = Field(default=1.0)
    field4: bool = Field(default=True)


class ModelC(BaseModel):
    field1: int = Field(default=20)  # Same type as in ModelA
    field5: str = Field(default="another default")


class ModelD(BaseModel):
    field1: str = Field(default="conflict")  # Conflicting type with ModelA and ModelC


def test_combine_pydantic_models():
    # Test combining models with non-conflicting fields
    CombinedModel = combine_pydantic_models([ModelA, ModelB], "CombinedModel")

    # test creating a model from the combined model
    combined_model = CombinedModel(field1=10, field2="default", field3=1.0, field4=True)
    assert combined_model.field1 == 10
    assert combined_model.field2 == "default"
    assert combined_model.field3 == 1.0
    assert combined_model.field4 is True

    # now try creating it with a nonexistent field
    combined_model = CombinedModel(field1=10, field2="default", field3=1.0, field4=True, field5="test")
    assert combined_model.field1 == 10
    assert combined_model.field2 == "default"
    assert combined_model.field3 == 1.0
    assert combined_model.field4 is True
    with pytest.raises(AttributeError):
        assert combined_model.field5 == "test"

    # Test combining models with conflicting field types
    with pytest.raises(ValueError, match="Field 'field1' on ModelD already exists, but with a different annotation:"):
        combine_pydantic_models([ModelA, ModelD], "ConflictingModel")

    # Test combining models with no fields
    class EmptyModel(BaseModel):
        pass

    CombinedEmptyModel = combine_pydantic_models([EmptyModel], "CombinedEmptyModel")
    assert len(CombinedEmptyModel.model_fields) == 0

    # Test combining a single model
    SingleModel = combine_pydantic_models([ModelA], "SingleModel")

    # Create an instance of SingleModel
    single_model_instance = SingleModel()

    # Access fields from the instance
    assert hasattr(single_model_instance, "field1")
    assert single_model_instance.field1 == 10
    assert hasattr(single_model_instance, "field2")
    assert single_model_instance.field2 == "default"


from bbot_server.cli.common import json_to_csv


def test_json_to_csv():
    json_data = [
        {"name": "test", "value": 1, "value2": [{"a": 2}]},
        {"name": "test2", "value": 2, "value2": {"a": [1, 2]}, "value3": "test"},
    ]
    csv_data = list(json_to_csv(json_data, fieldnames=["name", "value", "value2"]))
    assert csv_data == [
        b"name,value,value2\r\n",
        b'test,1,"[{""a"":2}]"\r\n',
        b'test2,2,"{""a"":[1,2]}"\r\n',
    ]

    # same exact thing but with pydantic model
    class TestModel(BaseModel):
        name: str = None
        value: int = None
        value2: List[Dict[str, Any]] = None
        value3: str = None

    pydantic_data = [
        TestModel(name="test", value=1, value2=[{"a": 2}]),
        TestModel(name="test2", value=2, value2=[{"a": [1, 2]}], value3="test"),
    ]

    csv_data_pydantic = list(json_to_csv(pydantic_data, fieldnames=["name", "value", "value2"]))
    assert csv_data_pydantic == [
        b"name,value,value2\r\n",
        b'test,1,"[{""a"":2}]"\r\n',
        b'test2,2,"[{""a"":[1,2]}]"\r\n',
    ]
