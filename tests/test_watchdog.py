import os
import subprocess
from datetime import datetime, timedelta, timezone

from stage_results import MachineCfg
from watchdog import evaluate, git_last_seen

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
CFG = {"m": MachineCfg(active=True, max_age_hours=48.0, max_unhealthy_hours=24.0)}


def h(n):
    return NOW - timedelta(hours=n)


def test_fresh_ok():
    assert evaluate(CFG, {"m": h(2)}, {"m": None}, NOW) == []


def test_stale_flagged():
    assert evaluate(CFG, {"m": h(50)}, {}, NOW) == [
        "m: no results or heartbeat for 50h (max 48h)"
    ]


def test_never_seen():
    assert evaluate(CFG, {"m": None}, {}, NOW) == [
        "m: no results or heartbeat ever (max 48h)"
    ]


def test_unhealthy_flagged_with_text():
    st = {"m": {"problem": "foreign GPU process pid 1234 (Xorg)",
                "problem_since": "2026-10-09T06:00:00Z"}}
    assert evaluate(CFG, {"m": h(1)}, st, NOW) == [
        "m: unhealthy for 30h: foreign GPU process pid 1234 (Xorg)"
    ]


def test_recent_problem_not_flagged():
    st = {"m": {"problem": "x", "problem_since": h(3).strftime("%Y-%m-%dT%H:%M:%SZ")}}
    assert evaluate(CFG, {"m": h(1)}, st, NOW) == []


def test_inactive_ignored():
    cfg = {"m": MachineCfg(active=False, max_age_hours=48, max_unhealthy_hours=24)}
    assert evaluate(cfg, {"m": None}, {}, NOW) == []


def test_heartbeat_counts_as_fresh(tmp_path):
    def git(*a, date=None):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        if date:
            env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = date
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, env=env,
                       capture_output=True)

    git("init", "-q")
    (tmp_path / "results/m").mkdir(parents=True)
    (tmp_path / "machines/m").mkdir(parents=True)
    (tmp_path / "results/m/a.json").write_text("{}")
    git("add", "-A")
    git("commit", "-qm", "result", date=h(100).isoformat())
    (tmp_path / "machines/m/status.json").write_text('{"problem": null}')
    git("add", "-A")
    git("commit", "-qm", "heartbeat", date=h(2).isoformat())
    seen = git_last_seen(tmp_path, "m")
    assert seen is not None and abs(seen - h(2)) < timedelta(seconds=1)
    assert evaluate(CFG, {"m": seen}, {"m": {"problem": None}}, NOW) == []
    assert git_last_seen(tmp_path, "other") is None
