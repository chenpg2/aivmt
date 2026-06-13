"""Run the case-entry portal:  ``uv run --extra portal python -m aivmt.portal``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
    parser = argparse.ArgumentParser(description="AIVMT 病历录入门户 (teacher case-entry portal)")
    parser.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="bind port (default 8765)")
    parser.add_argument(
        "--case-dir", default=None,
        help="case directory (default: $AIVMT_CASE_DIR or conf/case)",
    )
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        logger.error(
            "缺少 portal 依赖,请用: uv run --extra portal python -m aivmt.portal"
        )
        return 1

    from .app import create_app

    try:
        app = create_app(Path(args.case_dir) if args.case_dir else None)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    logger.info("病历录入门户已启动: http://%s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
