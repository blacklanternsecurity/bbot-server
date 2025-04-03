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
logger.setLevel(logging.INFO)

# Create console handler with the current format
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(FORMAT, datefmt="[%X]"))
logger.addHandler(console_handler)

# Create file handler for debug logs in ~/.bbot_server/debug.log
log_dir = Path.home() / ".bbot_server"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "debug.log.gz"


class GzipRotatingFileHandler(RotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._check_count = 0
        self._check_interval = 1000  # Check file size every 1000 log messages

    def _open(self):
        # Just override the file opening mechanism to use gzip
        return gzip.open(f"{self.baseFilename}.gz", mode="at", encoding=self.encoding)

    def shouldRollover(self, record):
        """
        Override shouldRollover to handle gzip files which don't support seek from end
        Only check file size every 1000 log messages to improve performance
        """
        if self.maxBytes <= 0:
            return False

        # Increment counter and check if we should evaluate file size
        self._check_count = (self._check_count + 1) % self._check_interval

        # Only check file size when counter is 0 (every _check_interval messages)
        if self._check_count == 0:
            if self.stream:
                self.stream.flush()
                # Get current file size without seeking
                current_size = os.path.getsize(self.baseFilename)

                # Check if this record would push us over the limit
                msg = self.format(record)
                # Conservatively estimate the size increase
                estimated_msg_size = len(msg) + 1  # +1 for the newline
                return current_size + estimated_msg_size >= self.maxBytes

        return False


# Create gzip file handler with line numbers in the format
file_handler = GzipRotatingFileHandler(
    filename=str(log_file),
    maxBytes=50 * 1000 * 1000,  # 50MB
    backupCount=5,
    mode="at",
)
file_handler.setFormatter(logging.Formatter(FILE_FORMAT, datefmt="[%X]"))
logger.addHandler(file_handler)

# Replace the root logger's configuration with our custom logger
logging.root = logger
