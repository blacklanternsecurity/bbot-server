from .lib import *


# class TestMongo(IOTestBase):
#     async def setup(self):
#         from bbot_io.backends.mongo import mongo

#         return mongo(db_name="bbot_pytest", collection_prefix="pytest_")

# def test_mongodb():
#     from bbot_io.backends.mongo import sqlalchemy_to_mongodb
#     from bbot_io.models import Event
#     from sqlmodel import distinct, select

#     statement = select(distinct(Event.host)).where(Event.type == "DNS_NAME")
#     mongo_query = sqlalchemy_to_mongodb(statement)
#     print(mongo_query)
