from pydantic import BaseModel

from bbot_server.applets.base import api_endpoint


class TestModel(BaseModel):
    """Simple test model for testing api_endpoint decorator."""

    name: str
    age: int
    active: bool = True


def test_api_endpoint_decorator():
    """Test all three ways to call a function decorated with api_endpoint."""

    @api_endpoint("/test")
    def process_data(data: TestModel) -> str:
        return f"{data.name} is {data.age} years old and active={data.active}"

    # Test case 1: calling with param_name=<pydantic_object>
    test_data = TestModel(name="Alice", age=30, active=False)
    result = process_data(data=test_data)
    assert result == "Alice is 30 years old and active=False"

    # Test case 2: calling with positional <pydantic_object>
    test_data = TestModel(name="Bob", age=25)
    result = process_data(test_data)
    assert result == "Bob is 25 years old and active=True"

    # Test case 3: calling with individual pydantic attributes
    result = process_data(name="Charlie", age=35, active=False)
    assert result == "Charlie is 35 years old and active=False"
