"""Centralized logging configuration for the backend.

This keeps log output uniform so the team can trace requests and DB behavior.
The handlers are intentionally simple (stdout only) to run well in local/dev and
container environments without needing external services.
"""

import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging with a consistent, structured-ish format."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Align uvicorn/fastapi logs with our level so request errors surface.
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)
    logging.getLogger("fastapi").setLevel(level)

    # Note: For richer structured logs (json), swap the formatter here; keeping
    # it light for now so teammates can tail logs easily.

