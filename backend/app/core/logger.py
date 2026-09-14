import logging
import sys


LOGGER_NAME = "phishsense"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_HANDLER_MARKER = "_phishsense_console_handler"


def setup_logging() -> logging.Logger:
    """Configure and return the application's shared logger.

    The handler marker makes this function safe to call during application
    startup, tests, or worker initialization without duplicating log output.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)

    # Keep application logs from being emitted again by the root logger.
    logger.propagate = False

    # Reuse the existing application console handler when setup runs again.
    console_handler = next(
        (
            handler
            for handler in logger.handlers
            if getattr(handler, _HANDLER_MARKER, False)
        ),
        None,
    )

    if console_handler is None:
        console_handler = logging.StreamHandler(sys.stdout)
        setattr(console_handler, _HANDLER_MARKER, True)
        logger.addHandler(console_handler)

    # Set these on every call so the logger remains correctly configured even
    # if another part of the application changed the handler configuration.
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    return logger