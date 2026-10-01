"""Explicit retention command; defaults to preview without deleting data."""
import argparse
import time
from sqlalchemy import delete, func, select
from backend.storage import engine, events, init_db, scans, tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.days < 1:
        parser.error("days must be positive")
    init_db()
    cutoff = int(time.time()) - args.days*86400
    # Keep evidence used by all retained tasks.
    condition = (scans.c.created_at < cutoff) & ~scans.c.id.in_(select(tasks.c.scan_id))
    with engine.begin() as conn:
        count = conn.scalar(select(func.count()).select_from(scans).where(condition))
        print(f"{count} scans older than {args.days} days without task references.")
        if args.apply:
            conn.execute(delete(scans).where(condition))
            print("Deleted. Back up before retention runs. SQLite can reuse freed pages.")
        else:
            print("Preview only. Add --apply to delete.")


if __name__ == "__main__":
    main()
