import logging

from bbot_server.errors import BBOTServerError

log = logging.getLogger(__name__)


def MessageQueue(config):
    # make sure the necessary variables are in the config
    try:
        mq_config = config["message_queue"]
    except Exception as e:
        raise BBOTServerError(f"Message queue configuration is missing from config: {config}") from e
    try:
        uri = mq_config.uri
    except Exception as e:
        raise BBOTServerError(f"Message queue URI is missing from config: {config}") from e

    from .redis import RedisMessageQueue

    return RedisMessageQueue(uri, mq_config)
