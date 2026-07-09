from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9701_symbol_binding_rebalanced_contract_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9701", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9701_rebalanced_manifest_data_contract_is_clean():
    mod = _load()
    rows = mod.load_jsonl(mod.MANIFEST)
    split_counts = mod.split_label_counts(rows)
    labels = {mod.label(row) for row in rows}
    assert len(rows) == 64
    assert Counter(row["split"] for row in rows) == {"train": 32, "eval": 16, "strict_eval": 16}
    for split in ["train", "eval", "strict_eval"]:
        assert set(split_counts[split]) == labels
    assert mod.loss_counts(rows) == Counter({"symbol_binding_ce": 64})
    assert mod.authority_violations(rows) == []


def test_stage9701_shortcut_baselines_below_ceiling_but_query_kind_warns():
    mod = _load()
    rows = mod.load_jsonl(mod.MANIFEST)
    baselines = [
        mod.baseline(rows, "majority", lambda row: "all"),
        mod.baseline(rows, "split", lambda row: str(row.get("split"))),
        mod.baseline(rows, "query_kind", mod.query_kind),
        mod.baseline(rows, "target_node_presence", mod.target_node_presence),
        mod.baseline(rows, "target_node_kind", mod.target_node_kind),
    ]
    strongest = max(baselines, key=lambda item: item["exact"])
    assert strongest["feature"] == "query_kind"
    assert strongest["exact"] == 0.640625
    assert strongest["exact"] < mod.SHORTCUT_CEILING


def test_stage9701_execution_blocked_until_native_ablation_exists():
    mod = _load()
    support = mod.native_ablation_support()
    assert support["proxy_ablation_present"] is True
    assert support["native_grouped_ablation_function_present"] is False
    assert support["native_grouped_ablation_cli_present"] is False
