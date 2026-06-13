"""Run the faculty-scoring portal: ``uv run --extra portal python -m aivmt.faculty_portal``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
    parser = argparse.ArgumentParser(
        description="AIVMT 教师评分门户 (blinded faculty-scoring portal)"
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8770, help="bind port (default 8770)")
    parser.add_argument(
        "--transcript-dir", default=None,
        help="eval transcript directory (default: $AIVMT_EVAL_TRANSCRIPT_DIR or data/eval_transcripts)",
    )
    parser.add_argument(
        "--ratings-csv", default=None,
        help="faculty ratings CSV (default: $AIVMT_FACULTY_RATINGS_CSV or data/faculty_ratings.csv)",
    )
    parser.add_argument("--seed", type=int, default=42, help="per-rater order seed (mirror configs/seed.yaml)")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        logger.error("缺少 portal 依赖,请用: uv run --extra portal python -m aivmt.faculty_portal")
        return 1

    from .app import create_app

    try:
        app = create_app(
            Path(args.transcript_dir) if args.transcript_dir else None,
            Path(args.ratings_csv) if args.ratings_csv else None,
            seed=args.seed,
        )
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        logger.error("提示:评分转写集尚未生成时,请先让数据同事放入转写文件,或用 --transcript-dir 指定目录。")
        return 1

    logger.info("教师评分门户已启动: http://%s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
