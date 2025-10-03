import os
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Define the format for console logs
# If we're inside tests, we include the date in the format
if os.environ.get("BBOT_TESTING", "False") == "True":
    FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
else:
    FORMAT = "[%(levelname)s] %(message)s"

# Define the format for file logs (including line numbers)
FILE_FORMAT = "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"

# Create logger
logger = logging.getLogger("bbot_server")
logger.setLevel(logging.INFO)

# Create console handler with the current format
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(FORMAT, datefmt="[%X]"))
logger.addHandler(console_handler)

# Create file handler for debug logs in ~/.bbot_server/debug.log (plain text)
# We only compress the rotated log files, not the active one, so keep the
# base file extension as .log rather than .log.gz.
log_dir = Path.home() / ".bbot_server"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "debug.log"


class GzipRotatingFileHandler(RotatingFileHandler):
    """
    A rotating file handler that compresses rotated files with gzip.
    Checks file size only periodically to improve performance.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._msg_count = 0
        self._check_interval = 1000  # Check size every 1000 messages

    def rotation_filename(self, default_name):
        """
        Ensure the rotated filename ends with `.gz` so that the compressed
        file is easy to identify. If the default_name already includes the
        suffix (it should not, but guard just in case) we leave it untouched.
        """
        return default_name if default_name.endswith(".gz") else default_name + ".gz"

    def rotate(self, source, dest):
        """
        Compress the source file and move it to the destination.
        """
        import gzip

        with open(source, "rb") as f_in:
            with gzip.open(dest, "wb") as f_out:
                f_out.writelines(f_in)
        os.remove(source)

    def emit(self, record):
        """
        Emit a record, checking for rollover only periodically using modulo.
        """
        self._msg_count += 1

        # Only check for rollover periodically to save compute
        if self._msg_count % self._check_interval == 0:
            if self.shouldRollover(record):
                self.doRollover()

        # Continue with normal emit process
        super().emit(record)


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
