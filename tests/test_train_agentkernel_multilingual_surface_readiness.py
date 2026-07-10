from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"


def _load():
    spec = importlib.util.spec_from_file_location("train_agentkernel_lite_encdec", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _row(language: str, split: str, label: str, task: str, evidence: str, file_ext: str, *, config: bool = False, entry: bool = False, symbols: bool = False, tests: bool = False):
    return {
        "row_id": f"{language}:{split}:{label}:{task}:{evidence}",
        "language_family": language,
        "split": split,
        "clean_state": {"edit_localization_target": label},
        "input_state": {
            "task_observation": task,
            "visible_locality_evidence": evidence,
            "file_extension": file_ext,
            "context_config_visible": config,
            "context_entrypoint_visible": entry,
            "context_symbol_names_visible": symbols,
            "context_tests_visible": tests,
        },
    }


def _base_rows() -> list[dict[str, object]]:
    rows = []
    rows.extend(
        [
            _row("python", "train", "A", "t1", "e1", "py", tests=True),
            _row("python", "train", "B", "t2", "e2", "py", config=True),
            _row("python", "eval", "A", "t1", "e1", "py", tests=True),
            _row("python", "eval", "B", "t2", "e2", "py", config=True),
            _row("python", "strict_eval", "A", "t1", "e1", "py", tests=True),
            _row("python", "strict_eval", "B", "t2", "e2", "py", config=True),
            _row("rust", "train", "A", "t1", "e1", "rs", tests=True),
            _row("rust", "train", "B", "t2", "e2", "rs", config=True),
            _row("rust", "eval", "A", "t1", "e1", "rs", tests=True),
            _row("rust", "eval", "B", "t2", "e2", "rs", config=True),
            _row("rust", "strict_eval", "A", "t1", "e1", "rs", tests=True),
            _row("rust", "strict_eval", "B", "t2", "e2", "rs", config=True),
            _row("c_cpp", "train", "A", "t1", "e1", "cpp", tests=True),
            _row("c_cpp", "train", "B", "t2", "e2", "cpp", config=True),
            _row("c_cpp", "eval", "A", "t1", "e1", "cpp", tests=True),
            _row("c_cpp", "eval", "B", "t2", "e2", "cpp", config=True),
            _row("c_cpp", "strict_eval", "A", "t1", "e1", "cpp", tests=True),
            _row("c_cpp", "strict_eval", "B", "t2", "e2", "cpp", config=True),
            _row("web_js_ts_html", "train", "A", "t1", "e1", "ts", tests=True),
            _row("web_js_ts_html", "train", "B", "t2", "e2", "ts", config=True),
            _row("web_js_ts_html", "eval", "A", "t1", "e1", "ts", tests=True),
            _row("web_js_ts_html", "eval", "B", "t2", "e2", "ts", config=True),
            _row("web_js_ts_html", "strict_eval", "A", "t1", "e1", "ts", tests=True),
            _row("web_js_ts_html", "strict_eval", "B", "t2", "e2", "ts", config=True),
        ]
    )
    return rows


def test_surface_readiness_allows_multiple_signatures_per_label_when_non_colliding():
    mod = _load()
    rows = _base_rows()
    rows.append(_row("python", "eval", "A", "t3", "e3", "py", entry=True))
    rows.append(_row("c_cpp", "eval", "B", "t4", "e4", "cpp", symbols=True))
    readiness = mod.assess_multilingual_surface_readiness("edit_localization_probe", rows)
    assert readiness is not None
    assert readiness["passed"] is True
    assert readiness["buckets"]["python:eval"]["safe_signature_unique_count"] == 3
    assert readiness["buckets"]["python:eval"]["label_count"] == 2
    assert readiness["buckets"]["python:eval"]["surface_separates_labels"] is True
    assert readiness["buckets"]["python:eval"]["signature_collision_count"] == 0


def test_surface_readiness_rejects_signature_collision_across_labels():
    mod = _load()
    rows = _base_rows()
    rows.append(_row("python", "eval", "B", "t1", "e1", "py", tests=True))
    readiness = mod.assess_multilingual_surface_readiness("edit_localization_probe", rows)
    assert readiness is not None
    assert readiness["passed"] is False
    assert "python:eval" in readiness["failed_buckets"]
    assert readiness["buckets"]["python:eval"]["signature_collision_count"] == 1
