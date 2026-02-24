import pytest

pytestmark = pytest.mark.skip(reason="MongoDB tests removed in Postgres migration")

from bbot_server.errors import BBOTServerValueError
from bbot_server.utils.misc import _sanitize_mongo_query, _sanitize_mongo_aggregation


# Enhanced Tests for Query Sanitizer
def test_query_allowed_simple():
    input_data = {"field": 1, "another": "value"}
    result = _sanitize_mongo_query(input_data)
    assert result == input_data, "Simple dict without operators should remain unchanged."


def test_query_allowed_operators():
    input_data = {"age": {"$gt": 18, "$lte": 100}, "status": {"$in": ["active", "pending"]}}
    result = _sanitize_mongo_query(input_data)
    assert result == input_data, "Allowed query operators should pass through."


def test_query_allowed_logical():
    input_data = {"$and": [{"age": {"$gte": 18}}, {"score": {"$lt": 100}}]}
    result = _sanitize_mongo_query(input_data)
    assert result == input_data, "Logical operators like $and should be allowed."


def test_query_naughty_where():
    input_data = {"$where": "this.age > 18"}
    with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB query operator: \$where"):
        _sanitize_mongo_query(input_data)


def test_query_naughty_expr():
    input_data = {"$expr": {"$gt": ["$age", 18]}}
    with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB query operator: \$expr"):
        _sanitize_mongo_query(input_data)


def test_query_deep_nested_allowed():
    input_data = {"level1": {"level2": {"level3": {"$exists": True}}}}
    result = _sanitize_mongo_query(input_data)
    assert result == input_data, "Deeply nested allowed operators should pass."


def test_query_deep_nested_naughty():
    input_data = {"level1": {"level2": {"level3": {"$where": "js"}}}}
    with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB query operator: \$where"):
        _sanitize_mongo_query(input_data)


def test_query_list_allowed():
    input_data = {"$or": [{"age": {"$gt": 18}}, {"status": {"$eq": "active"}}]}
    result = _sanitize_mongo_query(input_data)
    assert result == input_data, "Lists with allowed operators should pass."


def test_query_list_naughty():
    input_data = {"$or": [{"age": {"$expr": {"$gt": [18]}}}, {"status": "active"}]}
    with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB query operator: \$expr"):
        _sanitize_mongo_query(input_data)


def test_query_non_dict_values():
    input_data = {"array": [1, 2, {"$in": [3, 4]}]}
    result = _sanitize_mongo_query(input_data)
    assert result == input_data, "Non-dict list items should remain, dicts sanitized."


def test_query_empty_dict():
    input_data = {}
    result = _sanitize_mongo_query(input_data)
    assert result == {}, "Empty dict should remain empty."


def test_agg_allowed_pipeline_list():
    input_data = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    result = _sanitize_mongo_aggregation(input_data)
    assert result == input_data, "Full pipeline with allowed stages should pass."


def test_agg_allowed_set_stage():
    input_data = {"$set": {"total": {"$add": ["$price", "$tax"]}}}
    result = _sanitize_mongo_aggregation(input_data)
    assert result == input_data, "$set as aggregation stage should be allowed."


def test_agg_allowed_expressions():
    input_data = {
        "$project": {
            "total": {"$add": ["$price", {"$multiply": ["$quantity", 0.1]}]},
            "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdAt"}},
        }
    }
    result = _sanitize_mongo_aggregation(input_data)
    assert result == input_data, "Expressions within stages should pass if allowed."


def test_agg_naughty_out():
    input_data = {"$out": "newCollection"}
    with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB aggregation operator: \$out"):
        _sanitize_mongo_aggregation(input_data)


def test_agg_naughty_merge():
    input_data = {"$merge": {"into": "collection"}}
    with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB aggregation operator: \$merge"):
        _sanitize_mongo_aggregation(input_data)


def test_agg_naughty_lookup():
    input_data = {"$lookup": {"from": "other", "localField": "id", "foreignField": "id", "as": "joined"}}
    with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB aggregation operator: \$lookup"):
        _sanitize_mongo_aggregation(input_data)


def test_agg_naughty_function():
    input_data = {"$project": {"custom": {"$function": {"body": "function() {}", "args": [], "lang": "js"}}}}
    with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB aggregation operator: \$function"):
        _sanitize_mongo_aggregation(input_data)


def test_agg_naughty_accumulator():
    input_data = {"$group": {"_id": None, "custom": {"$accumulator": {"init": "function() {}"}}}}
    with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB aggregation operator: \$accumulator"):
        _sanitize_mongo_aggregation(input_data)


def test_agg_deep_nested_allowed():
    input_data = {"$facet": {"category": [{"$match": {"$exists": True}}, {"$group": {"_id": "$cat"}}]}}
    with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB aggregation operator: \$match"):
        _sanitize_mongo_aggregation(input_data)


def test_agg_deep_nested_naughty():
    input_data = {"$facet": {"category": [{"$graphLookup": {}}]}}
    with pytest.raises(BBOTServerValueError, match=r"Unauthorized MongoDB aggregation operator: \$graphLookup"):
        _sanitize_mongo_aggregation(input_data)


def test_agg_list_non_dict():
    input_data = {"$sortByCount": "$field"}
    result = _sanitize_mongo_aggregation(input_data)
    assert result == input_data, "Stages with non-dict values should pass."


def test_agg_empty_pipeline():
    input_data = []
    result = _sanitize_mongo_aggregation(input_data)
    assert result == input_data, "Empty list (pipeline) should remain unchanged."
