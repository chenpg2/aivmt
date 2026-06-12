"""Shared utilities: reproducibility seeding and logging."""

from __future__ import annotations

import logging
import os
import random

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger with a single stream handler."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def set_seed(seed: int = 42) -> None:
    """Set random seeds for reproducibility (numpy seeded if available)."""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np  # noqa: PLC0415

        np.random.seed(seed)
    except ImportError:
        pass
