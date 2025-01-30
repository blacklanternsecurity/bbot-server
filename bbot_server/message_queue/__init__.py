import logging
from omegaconf import OmegaConf
from urllib.parse import urlparse

from bbot_server.config import BBOT_SERVER_CONFIG


log = logging.getLogger(__name__)


def MessageQueue(config):
    # make sure the necessary variables are in the config
    try:
        mq_config = config["message_queue"]
    except Exception as e:
        raise ValueError(f"Message queue configuration is missing from config: {config}") from e
    try:
        uri = mq_config.uri
    except Exception as e:
        raise ValueError(f"Message queue URI is missing from config: {config}") from e

    # depending on the URI scheme, return either a RabbitMQ or NATS message queue
    parsed_uri = urlparse(uri)
    scheme = parsed_uri.scheme.lower()
    if scheme in ("rabbitmq", "amqp"):
        from .rabbitmq import RabbitMessageQueue

        return RabbitMessageQueue(uri, mq_config)
    elif scheme == "nats":
        from .nats import NATSMessageQueue

        return NATSMessageQueue(uri, config)
    else:
        raise ValueError(f"Unsupported message queue scheme: {scheme}")
