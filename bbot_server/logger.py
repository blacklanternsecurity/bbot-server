import logging
import os
import gzip
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Define the format for console logs
FORMAT = "[%(levelname)s] %(message)s"

# Define the format for file logs (including line numbers)
FILE_FORMAT = "[%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"

# Create logger
logger = logging.getLogger("bbot_server")
logger.setLevel(logging.NOTSET)

# Create console handler with the current format
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(FORMAT, datefmt="[%X]"))
logger.addHandler(console_handler)

# Create file handler for debug logs in ~/.bbot_server/debug.log
log_dir = Path.home() / ".bbot_server"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "debug.log.gz"


class GzipRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        # Just override the file opening mechanism to use gzip
        return gzip.open(self.baseFilename, "at")


# Create gzip file handler with line numbers in the format
file_handler = GzipRotatingFileHandler(
    filename=str(log_file),
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    mode="at",
)
file_handler.setFormatter(logging.Formatter(FILE_FORMAT, datefmt="[%X]"))
logger.addHandler(file_handler)

# Replace the root logger's configuration with our custom logger
logging.root = logger
