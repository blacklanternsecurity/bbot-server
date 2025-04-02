from .base_store import BaseMongoStore


class UserStore(BaseMongoStore):
    config_key = "user_store"
