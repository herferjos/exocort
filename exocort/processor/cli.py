"""CLI for running the vault processor."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from exocort import settings

from .engine import ProcessorConfig, run_once, run_watch


def main() -> None:
    parser = argparse.ArgumentParser(description="Process vault records into derived events.")
    parser.add_argument("--vault", type=str, default=None, help="Vault directory (default: settings).")
    parser.add_argument("--out", type=str, default=None, help="Output directory (default: settings).")
    parser.add_argument("--state", type=str, default=None, help="State file path (default: settings).")
    parser.add_argument("--batch-size", type=int, default=None, help="Max records per cycle.")
    parser.add_argument("--poll", type=float, default=None, help="Poll interval in seconds.")
    parser.add_argument("--min-text-chars", type=int, default=None, help="Skip records with less text.")
    parser.add_argument("--max-text-chars", type=int, default=None, help="Trim extracted text length.")
    parser.add_argument("--dry-run", action="store_true", help="Parse but do not write outputs.")
    parser.add_argument("--no-notes", action="store_true", help="Skip markdown note output.")
    parser.add_argument("--watch", action="store_true", help="Run continuously.")

    args = parser.parse_args()

    config = ProcessorConfig(
        vault_dir=(settings.processor_vault_dir() if args.vault is None else Path(args.vault).expanduser().resolve()),
        out_dir=(settings.processor_out_dir() if args.out is None else Path(args.out).expanduser().resolve()),
        state_path=(settings.processor_state_path() if args.state is None else Path(args.state).expanduser().resolve()),
        batch_size=(settings.processor_batch_size() if args.batch_size is None else args.batch_size),
        poll_interval_s=(settings.processor_poll_interval_s() if args.poll is None else args.poll),
        min_text_chars=(settings.processor_min_text_chars() if args.min_text_chars is None else args.min_text_chars),
        max_text_chars=(settings.processor_max_text_chars() if args.max_text_chars is None else args.max_text_chars),
        write_notes=not args.no_notes,
        dry_run=args.dry_run,
    )

    logging.basicConfig(
        level=settings.log_level(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    if args.watch:
        run_watch(config)
        return

    run_once(config)


if __name__ == "__main__":
    main()
