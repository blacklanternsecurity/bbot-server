from omegaconf import OmegaConf
from urllib.parse import urlparse

from bbot_server.config import BBOT_SERVER_CONFIG


def MessageQueue(config=None):
    # make sure the necessary variables are in the config
    global_config = BBOT_SERVER_CONFIG
    try:
        mq_config = global_config["message_queue"] or OmegaConf.create()
        if config is not None:
            mq_config = OmegaConf.merge(mq_config, config)
    except Exception as e:
        raise ValueError("Message queue configuration is missing") from e
    try:
        uri = mq_config.uri
    except Exception as e:
        raise ValueError("Message queue URI is missing") from e

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
