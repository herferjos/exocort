#!/usr/bin/env python3
"""
CLI entry point for the Exocort processor.
Ingests data/events/*.jsonl and generates an Obsidian-style vault.
"""
import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import settings
from .pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("processor")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Process events into Obsidian vault")
    p.add_argument("--day", help="Process single day (YYYY-MM-DD)")
    p.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    p.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD)")
    p.add_argument(
        "--provider",
        choices=["llama_cpp", "openai", "gemini"],
        help="Override LLM provider",
    )
    p.add_argument("--rebuild", action="store_true", help="Rebuild vault without re-ingesting")
    p.add_argument("--dry-run", action="store_true", help="Do not write files")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = settings.data_dir()
    events_dir = data_dir / "events"
    if not events_dir.exists():
        log.warning("Events dir does not exist: %s", events_dir)
        return 0

    # Resolve date range
    if args.day:
        days = [args.day]
    elif args.from_date and args.to_date:
        start = datetime.strptime(args.from_date, "%Y-%m-%d")
        end = datetime.strptime(args.to_date, "%Y-%m-%d")
        if start > end:
            log.error("--from must be <= --to")
            return 1
        days = []
        d = start
        while d <= end:
            days.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
    else:
        # All available days
        days = []
        for f in sorted(events_dir.glob("*.jsonl")):
            stem = f.stem
            if stem and len(stem) == 10 and stem[4] == "-" and stem[7] == "-":
                days.append(stem)

    if not days:
        log.info("No days to process")
        return 0

    log.info("Processing days: %s", days[:5] if len(days) > 5 else days)

    run_pipeline(
        days=days,
        provider_override=args.provider,
        rebuild_only=args.rebuild,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
