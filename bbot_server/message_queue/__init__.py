def MessageQueue():
    from .redis import RedisMessageQueue

    return RedisMessageQueue()
