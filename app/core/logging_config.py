"""Lightweight logging configuration for the backend."""

import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging with a consistent format."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

