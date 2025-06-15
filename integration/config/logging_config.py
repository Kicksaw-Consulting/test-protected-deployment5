import logging
import os
import sys

try:
    from rich.logging import RichHandler
except ImportError:
    RichHandler = None


def configure_loggers(loggers: list[str]) -> None:
    """
    Configure project loggers.

    Parameters
    ----------
    loggers : list[str]
        List of loggers to configure.

    """
    # Prepare handlers
    handlers: list[logging.Handler]
    # User RichHandler if available and running locally (not in AWS)
    if os.getenv("AWS_EXECUTION_ENV") is None and RichHandler is not None:
        handlers = [RichHandler(level=logging.DEBUG)]
    else:
        stream_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            " - ".join(
                [
                    "[%(levelname)s] %(asctime)s",
                    "%(name)s",
                    "%(funcName)s",
                    "%(lineno)d",
                    "%(message)s",
                ]
            )
        )
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(logging.DEBUG)
        handlers = [stream_handler]

    # Configure loggers
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.handlers = [*handlers]
        logger.setLevel(logging.DEBUG)

    # Don't propagate messages to root logger (avoid double-printing in AWS)
    root_logger = logging.getLogger()
    root_logger.propagate = False
    root_logger.handlers = []
