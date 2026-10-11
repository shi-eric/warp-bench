#!/usr/bin/env python3
"""Assemble an asv results tree from a checkout of the `results` branch.

Only machines listed in machines.toml are staged (active or not). Per-machine
metadata (status.json etc.) is never copied; benchmarks.json files are merged.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MachineCfg:
    active: bool
    max_age_hours: float
    max_unhealthy_hours: float


def load_machines(path: Path) -> dict[str, MachineCfg]:
    data = tomllib.loads(Path(path).read_text())
    return {
        name: MachineCfg(
            active=bool(cfg["active"]),
            max_age_hours=float(cfg["max_age_hours"]),
            max_unhealthy_hours=float(cfg["max_unhealthy_hours"]),
        )
        for name, cfg in data.get("machines", {}).items()
    }


def newest_result_ms(machine_dir: Path) -> int:
    newest = 0
    for f in Path(machine_dir).glob("*.json"):
        if f.name == "machine.json":
            continue
        date = json.loads(f.read_text()).get("date")
        if isinstance(date, int) and not isinstance(date, bool):
            newest = max(newest, date)
    return newest


def merge_benchmarks(sources: list[tuple[int, dict]]) -> dict:
    """Union of benchmark entries; on a name collision the larger int wins."""
    merged: dict = {}
    version = None
    owner: dict[str, int] = {}
    for stamp, data in sources:
        for key, value in data.items():
            if key == "version":
                if version is None:
                    version = value
                continue
            if key not in merged or stamp > owner[key]:
                merged[key] = value
                owner[key] = stamp
    out: dict = {}
    if version is not None:
        out["version"] = version
    out.update(merged)
    return out


def stage(results_checkout: Path, machines_toml: Path, warp_clone: Path, out: Path) -> None:
    results_checkout, out = Path(results_checkout), Path(out)
    machines = load_machines(machines_toml)
    out.mkdir(parents=True, exist_ok=True)

    conf = json.loads((results_checkout / "asv.conf.json").read_text())
    conf["repo"] = str(warp_clone)
    conf["results_dir"] = "results"
    conf["html_dir"] = "html"
    (out / "asv.conf.json").write_text(json.dumps(conf, indent=2) + "\n")

    sources: list[tuple[int, dict]] = []
    (out / "results").mkdir(exist_ok=True)
    for name in machines:
        src = results_checkout / "results" / name
        stamp = 0
        if src.is_dir():
            dst = out / "results" / name
            dst.mkdir(parents=True, exist_ok=True)
            for f in src.glob("*.json"):  # result files + machine.json only
                shutil.copy2(f, dst / f.name)
            stamp = newest_result_ms(src)
        bench = results_checkout / "machines" / name / "benchmarks.json"
        if bench.is_file():
            sources.append((stamp, json.loads(bench.read_text())))
    (out / "results" / "benchmarks.json").write_text(
        json.dumps(merge_benchmarks(sources)) + "\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--machines", required=True, type=Path)
    ap.add_argument("--warp", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    stage(a.results, a.machines, a.warp, a.out)


if __name__ == "__main__":
    main()
