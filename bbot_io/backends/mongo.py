from pymongo import ASCENDING
from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList, UnaryExpression
from sqlalchemy.sql import Select  # , ColumnElement, Alias
from sqlalchemy.sql.sqltypes import NullType

# from sqlalchemy.sql.functions import Function


# from bbot_io.models import *
from bbot_io.backends._base import BaseBackend, BaseTable


# def sqlalchemy_to_mongodb(clause):
#     """
#     Translate a sqlalchemy query to mongodb
#     """
#     if isinstance(clause, Select):
#         print(f'DIR: {clause._where_criteria}')
#         return sqlalchemy_to_mongodb(clause._where_criteria[0])

#     elif isinstance(clause, BinaryExpression):
#         key = clause.left.key
#         if isinstance(clause.right.type, NullType):
#             value = None
#         else:
#             value = clause.right.value
#         op = clause.operator.__name__

#         mongo_op = {
#             "eq": "$eq",
#             "ne": "$ne",
#             "gt": "$gt",
#             "lt": "$lt",
#             "ge": "$gte",
#             "le": "$lte",
#             "is_not": "$ne",
#         }.get(op, op)

#         return {key: {mongo_op: value}}

#     elif isinstance(clause, BooleanClauseList):
#         mongo_op = "$and" if clause.operator.__name__ == "and_" else "$or"
#         return {mongo_op: [sqlalchemy_to_mongodb(child) for child in clause.clauses]}

#     else:
#         print(f'UNKNOWN CLAUSE "{clause}" (type: {clause.__class__.__mro__})')


def sqlalchemy_to_mongodb(clause):
    """
    Translate a sqlalchemy query to mongodb
    """
    if isinstance(clause, Select):
        mongo_query = {}
        distinct_field = None
        if clause._where_criteria:
            mongo_query["$match"] = sqlalchemy_to_mongodb(clause._where_criteria[0])
        for column in clause.columns:
            if isinstance(column, UnaryExpression) and column.operator.__name__ == "distinct":
                distinct_field = column.element.key

        if distinct_field:
            mongo_query["distinct"] = distinct_field
        return mongo_query

    elif isinstance(clause, BinaryExpression):
        key = clause.left.key
        if isinstance(clause.right.type, NullType):
            value = None
        else:
            value = clause.right.value
        op = clause.operator.__name__

        mongo_op = {
            "eq": "$eq",
            "ne": "$ne",
            "gt": "$gt",
            "lt": "$lt",
            "ge": "$gte",
            "le": "$lte",
        }.get(op, op)

        return {key: {mongo_op: value}}

    elif isinstance(clause, BooleanClauseList):
        mongo_op = "$and" if clause.operator.__name__ == "and_" else "$or"
        return {mongo_op: [sqlalchemy_to_mongodb(child) for child in clause.clauses]}

    elif isinstance(clause, UnaryExpression):
        op = clause.operator.__name__
        if op == "distinct":
            return {"$group": {"_id": f"${clause.element.key}"}}
        elif op == "is_":
            return {clause.element.key: {"$exists": True, "$ne": None}}
        elif op == "is_not":
            return {"$or": [{clause.element.key: {"$exists": False}}, {clause.element.key: None}]}

    return {}


class MongoCollection(BaseTable):
    async def setup(self):
        if self.data_model:
            self.collection = getattr(self.backend.database, self.table_name)
            for field in self.data_model.model_config["index_fields"]:
                await self.collection.create_index([(field, ASCENDING)])

    async def insert(self, obj):
        return await self.collection.insert_one(obj.model_dump())


class mongo(BaseBackend):

    table_class = MongoCollection

    async def setup(self, uri: str = "mongodb://localhost:27017", db_name: str = "bbot", collection_prefix: str = ""):
        self.uri = uri
        self.db_name = db_name
        self.collection_prefix = collection_prefix

        self.client = AsyncIOMotorClient(self.uri)
        self.database = getattr(self.client, db_name)

    #     # collections (tables in mongodb)
    #     self.events = getattr(self.database, f"{self.collection_prefix}events")
    #     self.scans = getattr(self.database, f"{self.collection_prefix}scans")
    #     self.targets = getattr(self.database, f"{self.collection_prefix}targets")
    #     self.campaigns = getattr(self.database, f"{self.collection_prefix}campaigns")

    # async def async_setup(self):
    #     # create event indexes
    #     for field in ("id", "type", "host", "timestamp", "module", "scan"):
    #         await self.events.create_index([(field, ASCENDING)])

    #     # create scan indexes
    #     for field in ("id",):
    #         await self.scans.create_index([(field, ASCENDING)])

    # ### EVENTS ###

    # async def insert_event(self, event: Event):
    #     if event.type == "SCAN":
    #         await self.insert_scan(event)
    #     event_dict = event.model_dump(exclude_none=True)
    #     await self.events.insert_one(event_dict)

    # async def get_events(self, limit: int = None):
    #     return [Event(**e) for e in await self.events.find().to_list(None)]

    # async def get_subdomains(
    #     self,
    # ):
    #     return await self.events.distinct("host", {"type": {"$eq": "DNS_NAME"}})

    # ### SCANS ###

    # async def insert_scan(self, event: Event):
    #     scan_dict = event.model_dump(exclude_none=True)
    #     await self.scans.insert_one(scan_dict)
    #     await self.insert_target(scan_dict["data"])

    # async def get_scans(self, limit: int = None):
    #     return await self.scans.find().to_list(limit)

    # ### TARGETS ###

    # async def _insert_target(self, target: Target):
    #     query = {"hash": {"$eq": target.hash}}
    #     return await self.targets.update_one(query, target.model_dump(), upsert=True)

    # async def get_target(self, id: str = None):
    #     if id is None:
    #         query = {"default": {"$eq": True}}
    #     else:
    #         query = {"id": {"$eq": "id"}}
    #     return await self.targets.find_one(query)

    # ### DB UTILITIES ###

    # async def drop_database(self):
    #     response = []
    #     for collection in (self.events, self.scans):
    #         response.append(await collection.drop())
    #     return response
