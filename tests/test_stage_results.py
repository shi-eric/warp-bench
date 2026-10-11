import json
from pathlib import Path

import stage_results as sr

CONF = {
    "version": 1,
    "project": "warp-lang",
    "repo": "https://github.com/NVIDIA/warp.git",
    "results_dir": "x",
    "regressions_thresholds": {".*": 0.05, "tile\\.compile_.*": 0.10},
}


def _w(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj))


def _toml(tmp_path, names):
    t = tmp_path / "machines.toml"
    t.write_text(
        "".join(
            f"[machines.{n}]\nactive = true\nmax_age_hours = 48\nmax_unhealthy_hours = 24\n"
            for n in names
        )
    )
    return t


def _checkout(tmp_path, machines):
    """machines: {name: (date_ms, benchmarks_dict or None)}"""
    co = tmp_path / "co"
    _w(co / "asv.conf.json", CONF)
    for m, (date, bm) in machines.items():
        _w(co / "results" / m / "machine.json", {"machine": m, "version": 1})
        _w(co / "results" / m / "abcd1234-env.json", {"date": date, "results": {}})
        if bm is not None:
            _w(co / "machines" / m / "benchmarks.json", bm)
        _w(co / "machines" / m / "status.json", {"ok": True})
    return co


def test_unlisted_machine_not_staged(tmp_path):
    co = _checkout(tmp_path, {"a": (1, {"version": 2}), "tegra-ubuntu": (2, {"version": 2})})
    out = tmp_path / "out"
    sr.stage(co, _toml(tmp_path, ["a"]), tmp_path / "warp", out)
    assert (out / "results" / "a" / "machine.json").exists()
    assert not (out / "results" / "tegra-ubuntu").exists()
    assert not (out / "results" / "a" / "status.json").exists()


def test_merge_newest_wins(tmp_path):
    co = _checkout(
        tmp_path,
        {
            "old": (100, {"version": 2, "a.b": {"who": "old"}, "only.old": {"x": 1}}),
            "new": (200, {"version": 2, "a.b": {"who": "new"}, "only.new": {"x": 2}}),
        },
    )
    out = tmp_path / "out"
    sr.stage(co, _toml(tmp_path, ["old", "new"]), tmp_path / "warp", out)
    merged = json.loads((out / "results" / "benchmarks.json").read_text())
    assert merged["version"] == 2
    assert merged["a.b"] == {"who": "new"}
    assert "only.old" in merged and "only.new" in merged


def test_merge_function_and_missing_benchmarks(tmp_path):
    assert sr.merge_benchmarks([(5, {"version": 2, "k": 1}), (1, {"version": 2, "k": 0})])["k"] == 1
    co = _checkout(tmp_path, {"a": (1, None), "b": (2, {"version": 2, "z": {}})})
    out = tmp_path / "out"
    sr.stage(co, _toml(tmp_path, ["a", "b"]), tmp_path / "warp", out)
    assert (out / "results" / "a").is_dir()
    assert "z" in json.loads((out / "results" / "benchmarks.json").read_text())


def test_newest_result_ms(tmp_path):
    co = _checkout(tmp_path, {"a": (7, None)})
    assert sr.newest_result_ms(co / "results" / "a") == 7
    (tmp_path / "empty").mkdir()
    assert sr.newest_result_ms(tmp_path / "empty") == 0


def test_conf_repo_overridden(tmp_path):
    co = _checkout(tmp_path, {"a": (1, {"version": 2})})
    out = tmp_path / "out"
    warp = tmp_path / "warp"
    sr.stage(co, _toml(tmp_path, ["a"]), warp, out)
    conf = json.loads((out / "asv.conf.json").read_text())
    assert conf["repo"] == str(warp)
    assert conf["results_dir"] == "results"
    assert conf["html_dir"] == "html"


def test_regression_thresholds_preserved(tmp_path):
    co = _checkout(tmp_path, {"a": (1, {"version": 2})})
    out = tmp_path / "out"
    sr.stage(co, _toml(tmp_path, ["a"]), tmp_path / "warp", out)
    conf = json.loads((out / "asv.conf.json").read_text())
    assert conf["regressions_thresholds"] == CONF["regressions_thresholds"]


def test_load_machines(tmp_path):
    cfg = sr.load_machines(_toml(tmp_path, ["a"]))
    assert cfg == {"a": sr.MachineCfg(True, 48.0, 24.0)}
