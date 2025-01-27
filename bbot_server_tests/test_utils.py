import pytest
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
    with pytest.raises(ValueError, match="Conflicting types for field 'field1'"):
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
