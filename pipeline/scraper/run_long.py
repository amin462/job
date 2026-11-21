"""Run polite JobThai harvest batches for a bounded period.

This runner never tries to evade blocking. It stops on 403, 429, or CAPTCHA,
and requires an explicit confirmation that the project's collection approval
and prerequisite tasks are complete before making any network request.

Example (after approval and T1.2-T1.7 are complete):
  .\\.venv\\Scripts\\python.exe -B -X utf8 -m pipeline.scraper.run_long --authorization-confirmed --hours 8 --max-total 5000

Stop manually with Ctrl+C. Output is written to data/raw/jobthai/.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import time

from pipeline.scraper.harvest_batch import DEFAULT_OUT_DIR, run_batch


STOP_STATUSES = {"stopped_403", "stopped_429", "stopped_captcha"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run polite sequential JobThai batches for a limited time.")
    parser.add_argument(
        "--authorization-confirmed",
        action="store_true",
        help="Confirm JobThai permission (T0.3) and T1.2-T1.7 prerequisites are complete.",
    )
    parser.add_argument("--hours", type=float, default=8, help="Maximum wall time, from 0.1 to 24 hours.")
    parser.add_argument("--max-total", type=int, default=5000, help="Stop after this many new detail pages.")
    parser.add_argument("--batch-size", type=int, default=70, help="Maximum new detail pages per batch.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--min-delay", type=float, default=5.2, help="Per-request delay; must be >= 5 seconds.")
    parser.add_argument("--max-delay", type=float, default=6.3, help="Per-request jitter ceiling.")
    parser.add_argument("--min-pause", type=int, default=60, help="Minimum idle seconds between batches.")
    parser.add_argument("--max-pause", type=int, default=120, help="Maximum idle seconds between batches.")
    args = parser.parse_args(argv)

    if not args.authorization_confirmed:
        parser.error("T0.3 permission and T1.2-T1.7 must be complete; pass --authorization-confirmed only then.")
    if not 0.1 <= args.hours <= 24:
        parser.error("--hours must be between 0.1 and 24.")
    if args.max_total < 1 or args.batch_size < 1:
        parser.error("--max-total and --batch-size must be positive.")
    if args.min_pause < 60 or args.max_pause < args.min_pause:
        parser.error("batch pauses must be at least 60 seconds and max-pause >= min-pause.")

    deadline = datetime.now(timezone.utc) + timedelta(hours=args.hours)
    rng = random.SystemRandom()
    total_fetched = 0
    batch_number = 0
    print(
        f"[START] max_hours={args.hours} max_new={args.max_total} "
        f"per_request_delay={args.min_delay}-{args.max_delay}s output={args.out_dir}",
        flush=True,
    )

    try:
        while total_fetched < args.max_total and datetime.now(timezone.utc) < deadline:
            batch_number += 1
            remaining = args.max_total - total_fetched
            result = run_batch(
                batch_size=min(args.batch_size, remaining),
                out_dir=args.out_dir,
                min_delay=args.min_delay,
                max_delay=args.max_delay,
                batch_label=f"long{batch_number}",
            )
            total_fetched += int(result.get("n_fetched", 0))
            print(
                f"[BATCH {batch_number}] status={result.get('status')} "
                f"fetched={result.get('n_fetched', 0)} total={total_fetched}/{args.max_total}",
                flush=True,
            )

            if result.get("status") in STOP_STATUSES:
                print("[HALT] Block or CAPTCHA detected; do not retry or switch IP.", flush=True)
                return 2
            if int(result.get("n_fetched", 0)) == 0:
                print("[STOP] No new detail pages fetched; stopping to avoid repeated requests.", flush=True)
                return 0

            if total_fetched < args.max_total and datetime.now(timezone.utc) < deadline:
                pause = rng.randint(args.min_pause, args.max_pause)
                print(f"[PAUSE] idle {pause}s before next batch", flush=True)
                time.sleep(pause)
    except KeyboardInterrupt:
        print("[STOP] Interrupted by user; completed batches remain logged.", flush=True)
        return 130

    print(f"[DONE] total_fetched={total_fetched} batches={batch_number}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
