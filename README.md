# warp-bench

Benchmark results for [NVIDIA/warp](https://github.com/NVIDIA/warp), published with asv to GitHub Pages.

## Branches
- `main`: workflows, `tools/`, `machines.toml`, this README.
- `results`: data, append-only, never force-pushed. `asv.conf.json`, `results/<machine>/*.json` (samples stripped), and `machines/<machine>/` metadata (`benchmarks.json`, `status.json`, ...).
- `gh-pages`: frozen pre-cutover site, kept for rollback.

## Publish and watchdog
An hourly workflow runs `tools/stage_results.py` to assemble an asv results tree from `results` (only machines listed in `machines.toml`; `benchmarks.json` files merged, the machine with the newest result wins collisions), then `asv publish` and deploys to Pages. A watchdog job fails the run (GitHub emails the owner) if an active machine has had no `results`-branch commit for `max_age_hours`, or reports a problem in `status.json` for `max_unhealthy_hours`.

## Adding or retiring a machine
Edit `machines.toml`. Add a `[machines.<name>]` table to add one. Set `active = false` to retire it: its data stays published but the watchdog ignores it. Remove the table to hide it entirely (data stays on `results`).

## Tests
`python -m pytest -q` (Python 3.12, stdlib only plus pytest).
