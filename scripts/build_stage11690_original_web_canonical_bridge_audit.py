#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11690_original_web_canonical_bridge_audit"
OUT = ART / NAME
SUMMARY = OUT / "original_web_canonical_bridge_audit.json"
BRIDGED_ROWS = OUT / "original_web_canonical_bridged_rows.jsonl"

ORIGINAL_WEB = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
CANONICAL_HELDOUT = ART / "stage11663_web_canonical_renderer_package/web_canonical_heldout.jsonl"
ROUTED_AUDIT = ART / "stage11688_routed_web_identity_scorer_audit/routed_web_identity_scorer_audit.json"

STAGE11663 = ROOT / "scripts/build_stage11663_web_canonical_renderer_package.py"
STAGE11688 = ROOT / "scripts/build_stage11688_routed_web_identity_scorer_audit.py"


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


canon = load_module(STAGE11663, "stage11663_canonical")
route_audit = load_module(STAGE11688, "stage11688_route_audit")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def root_key(row: dict[str, Any]) -> str:
    return str(row.get("root_lineage_key") or row.get("root_id") or row.get("row_id"))


def target_label(row: dict[str, Any]) -> str:
    return str(row.get("bounded_choice_target_label") or row.get("target_text") or (row.get("target") or {}).get("bounded_choice_target_label") or "").strip()


def canonical_base_row_id(row_id: str) -> str:
    for suffix in ("::stage11663_canonical", "::stage11690_original_web_canonical_bridge"):
        if row_id.endswith(suffix):
            return row_id[: -len(suffix)]
    return row_id


def role_counts(row: dict[str, Any]) -> Counter[str]:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or row.get("opaque_options") or [])
    return Counter(route_audit.option_role(option) for option in options if isinstance(option, dict) and route_audit.option_role(option))


def evaluate_routed(rows: list[dict[str, Any]]) -> dict[str, Any]:
    web_model, web_tokenizer, _, _ = route_audit.load_runtime(route_audit.WEB_RUNTIME)
    identity_model, identity_tokenizer, _, _ = route_audit.load_runtime(route_audit.IDENTITY_RUNTIME)
    normalized = [route_audit.base.normalize_row(row) for row in rows]
    identity_rows = [row for row in normalized if route_audit.route(row) == "identity"]
    web_rows = [row for row in normalized if route_audit.route(row) == "web"]
    identity_result = route_audit.eval_group(
        name="stage11690_bridged_original_web__identity",
        rows=identity_rows,
        model=identity_model,
        tokenizer=identity_tokenizer,
        scorer=route_audit.IDENTITY_SCORER,
    )
    web_result = route_audit.eval_group(
        name="stage11690_bridged_original_web__web",
        rows=web_rows,
        model=web_model,
        tokenizer=web_tokenizer,
        scorer=route_audit.WEB_SCORER,
    )
    combined = route_audit.combine({"identity": identity_result, "web": web_result})
    return {
        **combined,
        "route": "identity_if_same_role_else_web",
        "parts": {"identity": identity_result, "web": web_result},
        "route_counts": {"identity": len(identity_rows), "web": len(web_rows)},
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    original_rows = load_jsonl(ORIGINAL_WEB)
    canonical_rows = load_jsonl(CANONICAL_HELDOUT)
    routed = load_json(ROUTED_AUDIT)
    bridged: list[dict[str, Any]] = []
    rejected: Counter[str] = Counter()
    for row in original_rows:
        transformed = canon.transform(row, source_name="stage11690_original_web_bridge", split="strict_eval")
        if transformed is None:
            rejected["canonical_transform_failed"] += 1
            continue
        transformed = copy.deepcopy(transformed)
        transformed["row_id"] = f"{row.get('row_id')}::stage11690_original_web_canonical_bridge"
        transformed["stage11690_original_web_canonical_bridge"] = True
        transformed["strict_eval_eligible_now"] = True
        transformed["trainable_now"] = False
        transformed["train_support_only"] = False
        source = dict(transformed.get("standalone_projection_source") or {})
        source["canonical_renderer_source"] = "stage11690_original_web_bridge"
        source["original_web_row_id"] = row.get("row_id")
        transformed["standalone_projection_source"] = source
        anti = dict(transformed.get("anti_cheat") or {})
        anti.update(
            {
                "bridge_from_original_web_heldout": True,
                "no_training_use": True,
                "candidate_objects_role_typed": True,
                "deterministic_option_shuffle": True,
            }
        )
        transformed["anti_cheat"] = anti
        bridged.append(transformed)
    write_jsonl(BRIDGED_ROWS, bridged)

    canonical_by_base = {canonical_base_row_id(str(row.get("row_id"))): row for row in canonical_rows}
    bridge_by_base = {canonical_base_row_id(str(row.get("row_id"))): row for row in bridged}
    shared = sorted(set(canonical_by_base) & set(bridge_by_base))
    diff_counts: Counter[str] = Counter()
    for key in shared:
        c = canonical_by_base[key]
        b = bridge_by_base[key]
        if target_label(c) != target_label(b):
            diff_counts["target_label_diff"] += 1
        if str(c.get("task_type")) != str(b.get("task_type")):
            diff_counts["task_type_diff"] += 1
        c_roles = [opt.get("role") for opt in c.get("opaque_options", []) if isinstance(opt, dict)]
        b_roles = [opt.get("role") for opt in b.get("opaque_options", []) if isinstance(opt, dict)]
        if c_roles != b_roles:
            diff_counts["option_role_order_diff"] += 1
    route_counts_before = Counter("identity" if route_audit.route(row) == "identity" else "web" for row in original_rows)
    route_counts_after = Counter("identity" if route_audit.route(row) == "identity" else "web" for row in bridged)
    bridged_eval = evaluate_routed(bridged)
    roots = {root_key(row) for row in bridged}
    prompt_leaks = sum(1 for row in bridged if (row.get("anti_cheat") or {}).get("gold_label_visible_before_options") is True)
    singleton_rows = sum(1 for row in bridged if len(row.get("opaque_options") or []) <= 1)
    option_role_hist = Counter()
    same_role_rows = 0
    for row in bridged:
        counts = role_counts(row)
        option_role_hist.update(counts)
        if counts and max(counts.values()) >= 2:
            same_role_rows += 1
    gates = {
        "bridged_all_66_original_rows": len(bridged) == 66 and len(original_rows) == 66,
        "bridge_matches_canonical_row_count": len(bridged) == len(canonical_rows) == 66,
        "no_transform_rejections": not rejected,
        "no_prompt_label_leaks": prompt_leaks == 0,
        "no_singleton_rows": singleton_rows == 0,
        "route_now_has_identity_rows": route_counts_after.get("identity", 0) > route_counts_before.get("identity", 0),
        "routed_score_matches_stage11688_canonical_53": bridged_eval["correct"] == 53 and bridged_eval["rows"] == 66,
        "beats_original_web_stage11688_28": bridged_eval["correct"] > routed["results"]["original_web_heldout"]["correct"],
        "same_roots_as_original": roots == {root_key(row) for row in original_rows},
    }
    if all(gates.values()):
        decision = "original_web_canonical_bridge_validated_interface_mismatch"
    elif gates["routed_score_matches_stage11688_canonical_53"] and gates["beats_original_web_stage11688_28"]:
        decision = "original_web_canonical_bridge_scoring_gain_with_audit_caveats"
    else:
        decision = "original_web_canonical_bridge_not_sufficient"
    summary = {
        "stage": 11690,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "counts": {
            "original_rows": len(original_rows),
            "bridged_rows": len(bridged),
            "canonical_reference_rows": len(canonical_rows),
            "roots": len(roots),
            "rejected": dict(rejected.most_common()),
            "prompt_label_leak_rows": prompt_leaks,
            "singleton_rows": singleton_rows,
            "same_role_candidate_rows": same_role_rows,
            "option_role_histogram": dict(option_role_hist.most_common()),
        },
        "route_counts": {
            "before_original": dict(route_counts_before),
            "after_bridged": dict(route_counts_after),
        },
        "scores": {
            "stage11688_original_web": {
                "correct": routed["results"]["original_web_heldout"]["correct"],
                "rows": routed["results"]["original_web_heldout"]["rows"],
                "accuracy": routed["results"]["original_web_heldout"]["accuracy"],
            },
            "stage11688_canonical_heldout": {
                "correct": routed["results"]["canonical_heldout"]["correct"],
                "rows": routed["results"]["canonical_heldout"]["rows"],
                "accuracy": routed["results"]["canonical_heldout"]["accuracy"],
            },
            "stage11690_bridged_original_web": {
                "correct": bridged_eval["correct"],
                "rows": bridged_eval["rows"],
                "accuracy": bridged_eval["accuracy"],
                "parts": bridged_eval["parts"],
            },
        },
        "canonical_diff_counts": dict(diff_counts.most_common()),
        "gates": gates,
        "interpretation": [
            "The exact original Web heldout rows can be re-rendered into the canonical role-typed candidate interface without changing roots or target labels.",
            "The route predicate does not fire on raw original Web rows because role metadata is absent; it fires after canonical bridging.",
            "If the bridged routed score matches canonical heldout, the Web gap is partly an interface/schema mismatch rather than only missing model capacity.",
            "This bridge is an eval/audit artifact, not a new training run and not proof of executable Web repair.",
        ],
        "recommended_next": {
            "stage": "stage11691_original_web_canonical_bridge_gemma_and_anticheat",
            "target": "run Gemma and anticheat comparison on the same canonical-bridged original Web rows, then decide whether canonical renderer becomes the product Web evaluation interface",
            "promotion_gate": [
                "100M bridged original Web > Gemma same-manifest",
                "no label leaks",
                "no singleton rows",
                "same original heldout roots",
                "protected gates still preserved by selected product route",
            ],
        },
        "source_artifacts": {
            "original_web": rel(ORIGINAL_WEB),
            "canonical_reference": rel(CANONICAL_HELDOUT),
            "routed_audit": rel(ROUTED_AUDIT),
        },
        "outputs": {"bridged_rows": rel(BRIDGED_ROWS), "summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "counts": summary["counts"], "route_counts": summary["route_counts"], "scores": summary["scores"], "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
