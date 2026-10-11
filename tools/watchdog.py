"""Freshness/health watchdog for the results branch. Exit 1 on any problem."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from stage_results import MachineCfg, load_machines


def _parse(ts) -> datetime | None:
    if not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def evaluate(machines: dict[str, MachineCfg],
             last_seen: dict[str, datetime | None],
             statuses: dict[str, dict | None],
             now: datetime) -> list[str]:
    problems: list[str] = []
    for m, cfg in machines.items():
        if not cfg.active:
            continue
        seen = last_seen.get(m)
        if seen is None:
            problems.append(f"{m}: no results or heartbeat ever (max {cfg.max_age_hours:g}h)")
        else:
            age = (now - seen).total_seconds() / 3600
            if age > cfg.max_age_hours:
                problems.append(
                    f"{m}: no results or heartbeat for {age:.0f}h (max {cfg.max_age_hours:g}h)")
        st = statuses.get(m)
        if isinstance(st, dict) and st.get("problem"):
            since = _parse(st.get("problem_since"))
            if since is not None:
                age = (now - since).total_seconds() / 3600
                if age > cfg.max_unhealthy_hours:
                    problems.append(f"{m}: unhealthy for {age:.0f}h: {st['problem']}")
    return problems


def git_last_seen(repo: Path, machine: str) -> datetime | None:
    out = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%cI", "--",
         f"results/{machine}", f"machines/{machine}"],
        capture_output=True, text=True, check=True).stdout.strip()
    return _parse(out) if out else None


def _load_status(repo: Path, machine: str) -> dict | None:
    try:
        data = json.loads((repo / "machines" / machine / "status.json").read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--machines", type=Path, required=True)
    ap.add_argument("--now")
    args = ap.parse_args(argv)
    now = _parse(args.now) if args.now else datetime.now(timezone.utc)
    machines = load_machines(args.machines)
    seen = {m: git_last_seen(args.results, m) for m in machines}
    statuses = {m: _load_status(args.results, m) for m in machines}
    problems = evaluate(machines, seen, statuses, now)
    text = "\n".join(problems) if problems else "all machines healthy"
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(text + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
