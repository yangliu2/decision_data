from loguru import logger
from pathlib import Path
import sys
from datetime import datetime


def setup_logger(log_dir: str = "logs"):
    """
    Sets up the Loguru logger to write logs to a specified folder with
    customized formatting.

    Args:
        log_dir (str): Directory where logs will be stored.
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Create a timestamped log file to avoid overwriting
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"app_{timestamp}.log"
    full_log_file = log_path / log_file

    # Remove the default logger to prevent duplicate logs
    logger.remove()

    # Define format strings
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss} | {level} | " "{file}:{function}:{line} - {message}"
    )
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level}</level> | "
        "<level>{file}:{function}:{line} - {message}</level>"
    )

    # Add a file sink without colorization
    logger.add(
        full_log_file,
        rotation="10 MB",
        retention="10 days",
        compression="zip",
        format=file_format,
        level="DEBUG",
        enqueue=True,  # Enables asynchronous logging
        catch=True,  # Catches exceptions in the logging process
        colorize=False,  # Disable color codes for file logs
    )

    # Add a console sink with colorization
    logger.add(
        sys.stdout,
        format=console_format,
        level="DEBUG",
        enqueue=True,  # Enables asynchronous logging
        catch=True,  # Catches exceptions in the logging process
        colorize=True,  # Enable color codes for console logs
    )
