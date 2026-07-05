from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "training_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

TARGET_LIKE_KEYS = {
    "answer",
    "answer_key",
    "clean_state",
    "expected",
    "expected_answer",
    "expected_output",
    "gold",
    "gold_label",
    "label",
    "oracle",
    "reference",
    "solution",
    "target",
    "target_body",
    "target_node_id",
    "target_text",
}

VISIBLE_ROOT_KEYS = {
    "context",
    "corrupted_state",
    "encoder_text",
    "features",
    "graph_input",
    "input",
    "input_state",
    "model_input",
    "nodes",
    "prompt",
    "query",
    "source_packet",
    "visible_context",
    "visible_state",
}

TARGET_ROOT_KEYS = {
    "clean_state",
    "decoder_text",
    "expected_output",
    "label",
    "target",
    "target_text",
}

ID_KEYS = {
    "candidate_id",
    "edge_id",
    "example_id",
    "graph_id",
    "node_id",
    "query_node_id",
    "row_id",
    "semantic_key",
    "source_id",
    "target_node_id",
}

LABEL_TOKENS = {
    "ABSTAIN",
    "ABSTAIN_UNBOUND",
    "BIND_CALL_TO_SYMBOL",
    "BIND_FAILURE_TO_SYMBOL",
    "BIND_IMPORT_TO_MODULE",
    "BIND_TEST_TO_SYMBOL",
    "BUILD_FROM_SCRATCH",
    "BUILD_ON_TOP",
    "CODE_GENERATION",
    "DIRECT_PRESENT",
    "EVIDENCE_REMOVED",
    "HOLD_LONG_OUTPUT",
    "REPAIR_INTERNAL_LEAK",
    "REPAIR_SHORT_OUTPUT",
    "REPO_QA_OR_MAINTAINER",
    "REPO_REPAIR",
    "RETRIEVE",
    "RETRIEVE_MORE",
    "SAFE",
    "UNSAFE",
    "USE_WHITELIST_IMPORT",
}

BODY_LEAK_KEYS = {
    "body_leak",
    "patch_body_leak",
    "raw_body_in_model_input",
    "raw_source_in_model_input",
    "source_body_leak",
}

RAW_SOURCE_VISIBLE_KEYS = {
    "body",
    "decoder_text",
    "full_source",
    "patch_body",
    "raw_body",
    "raw_decoder_text",
    "raw_encoder_text",
    "raw_source",
    "source_body",
    "source_excerpt",
}

ROUTES = {
    "PASS_NO_CONTAMINATION",
    "BLOCK_TARGET_LEAK",
    "BLOCK_LABEL_CODED_ID",
    "BLOCK_HELDOUT_OVERLAP",
    "BLOCK_BODY_OR_SOURCE_LEAK",
    "REVIEW_SPLIT_OVERLAP",
    "REVIEW_SUSPICIOUS_PROXY",
}


def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _normalize_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            yield from _walk(child, (*path, str(idx)))


def _get(row: Mapping[str, Any], key: str) -> Any:
    return row.get(key)


def _visible_roots(row: Mapping[str, Any]) -> list[tuple[str, Any]]:
    roots: list[tuple[str, Any]] = []
    for key, value in row.items():
        if key in VISIBLE_ROOT_KEYS:
            roots.append((key, value))
    if not roots:
        roots = [(key, value) for key, value in row.items() if key not in TARGET_ROOT_KEYS and key != "authority"]
    return roots


def _target_values(row: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in TARGET_ROOT_KEYS:
        value = row.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, (dict, list)):
            for _, child in _walk(value):
                if isinstance(child, str):
                    values.append(child)
    return [value for value in values if len(value) >= 12]


def _visible_text(row: Mapping[str, Any]) -> str:
    chunks: list[str] = []
    for _, root in _visible_roots(row):
        for _, child in _walk(root):
            if isinstance(child, str):
                chunks.append(child)
    return "\n".join(chunks)


def _target_leak(row: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for root_name, root in _visible_roots(row):
        for path, value in _walk(root):
            if not path:
                continue
            key = path[-1]
            if key in TARGET_LIKE_KEYS:
                reasons.append(f"visible_target_like_key:{root_name}.{'.'.join(path)}")
            if isinstance(value, str) and _normalize_token(value) in LABEL_TOKENS:
                if key in {"field_name", "source_field", "visible_feature", "feature_name"}:
                    reasons.append(f"visible_label_proxy_value:{root_name}.{'.'.join(path)}")
    visible = _visible_text(row)
    for target in _target_values(row):
        if target and target in visible:
            reasons.append("target_text_copied_in_visible_input")
            break
    return bool(reasons), sorted(set(reasons))


def _label_coded_id(row: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for path, value in _walk(row):
        if not path or path[-1] not in ID_KEYS or not isinstance(value, str):
            continue
        normalized = _normalize_token(value)
        for token in LABEL_TOKENS:
            if re.search(rf"(^|_){re.escape(token)}(_|$)", normalized):
                reasons.append(f"label_coded_id:{'.'.join(path)}:{token}")
                break
    return bool(reasons), sorted(set(reasons))


def _body_or_source_leak(row: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for key in BODY_LEAK_KEYS:
        if bool(row.get(key)):
            reasons.append(key)
    for root_name, root in _visible_roots(row):
        for path, value in _walk(root):
            if not path:
                continue
            key = path[-1]
            if key in RAW_SOURCE_VISIBLE_KEYS and value:
                reasons.append(f"raw_source_visible:{root_name}.{'.'.join(path)}")
    return bool(reasons), sorted(set(reasons))


def _heldout_overlap(row: Mapping[str, Any], locked_ids: set[str]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for key in ("source_id", "semantic_key", "row_id", "content_hash", "lineage_hash"):
        value = row.get(key)
        if isinstance(value, str) and value in locked_ids:
            reasons.append(f"locked_eval_overlap:{key}")
    if row.get("heldout_overlap") or row.get("locked_eval_overlap") or row.get("hidden_eval_contamination"):
        reasons.append("explicit_heldout_overlap_flag")
    return bool(reasons), sorted(set(reasons))


def detect_row(row: Mapping[str, Any], *, locked_eval_ids: set[str] | None = None) -> dict[str, Any]:
    locked_ids = locked_eval_ids or set()
    target_leak, target_reasons = _target_leak(row)
    label_coded_id, label_reasons = _label_coded_id(row)
    body_leak, body_reasons = _body_or_source_leak(row)
    heldout_overlap, heldout_reasons = _heldout_overlap(row, locked_ids)
    suspicious_proxy = bool(row.get("shortcut_dominated_feature") or row.get("suspicious_proxy_feature"))

    reasons = target_reasons + label_reasons + body_reasons + heldout_reasons
    if suspicious_proxy:
        reasons.append("suspicious_proxy_feature")

    if body_leak:
        route = "BLOCK_BODY_OR_SOURCE_LEAK"
    elif target_leak:
        route = "BLOCK_TARGET_LEAK"
    elif label_coded_id:
        route = "BLOCK_LABEL_CODED_ID"
    elif heldout_overlap:
        route = "BLOCK_HELDOUT_OVERLAP"
    elif suspicious_proxy:
        route = "REVIEW_SUSPICIOUS_PROXY"
    else:
        route = "PASS_NO_CONTAMINATION"

    return {
        "row_id": str(row.get("row_id") or row.get("id") or ""),
        "route": route,
        "contamination_route": route,
        "target_leak_flag": target_leak,
        "heldout_overlap": heldout_overlap,
        "label_coded_id": label_coded_id,
        "body_leak_flag": body_leak,
        "suspicious_proxy_flag": suspicious_proxy,
        "reasons": sorted(set(reasons)),
        "row_fingerprint": _json_hash({k: row.get(k) for k in ("row_id", "semantic_key", "source_id", "input_state", "graph_input", "query")}),
        "authority": AUTHORITY_CLOSED,
    }


def detect_card(rows: list[Mapping[str, Any]], *, locked_eval_ids: set[str] | None = None) -> dict[str, Any]:
    decisions = [detect_row(row, locked_eval_ids=locked_eval_ids) for row in rows]
    route_counts: dict[str, int] = {}
    for decision in decisions:
        route_counts[decision["route"]] = route_counts.get(decision["route"], 0) + 1

    semantic_splits: dict[str, set[str]] = {}
    for row in rows:
        semantic_key = row.get("semantic_key")
        split = row.get("split") or row.get("package_split")
        if isinstance(semantic_key, str) and isinstance(split, str):
            semantic_splits.setdefault(semantic_key, set()).add(split)
    split_overlap_keys = sorted(key for key, splits in semantic_splits.items() if len(splits) > 1 and "train" in splits)
    split_overlap_rows = len(split_overlap_keys)
    if split_overlap_rows:
        route_counts["REVIEW_SPLIT_OVERLAP"] = route_counts.get("REVIEW_SPLIT_OVERLAP", 0) + split_overlap_rows

    blocked_rows = sum(1 for decision in decisions if decision["route"].startswith("BLOCK_"))
    review_rows = sum(1 for decision in decisions if decision["route"].startswith("REVIEW_")) + split_overlap_rows
    return {
        "rows": len(rows),
        "decisions": decisions,
        "route_counts": dict(sorted(route_counts.items())),
        "blocked_rows": blocked_rows,
        "review_rows": review_rows,
        "pass_rows": sum(1 for decision in decisions if decision["route"] == "PASS_NO_CONTAMINATION"),
        "target_leak_rows": sum(1 for decision in decisions if decision["target_leak_flag"]),
        "heldout_overlap_rows": sum(1 for decision in decisions if decision["heldout_overlap"]),
        "label_coded_id_rows": sum(1 for decision in decisions if decision["label_coded_id"]),
        "body_leak_rows": sum(1 for decision in decisions if decision["body_leak_flag"]),
        "split_overlap_rows": split_overlap_rows,
        "split_overlap_keys": split_overlap_keys,
        "valid_routes": sorted(ROUTES),
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Objective-aware contamination and leakage detector.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--locked-eval-id", action="append", default=[])
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {
            "row_id": "row_clean_001",
            "split": "train",
            "semantic_key": "sem_001",
            "input_state": {"intent": "repair parser", "evidence_state": "direct_present"},
            "target": {"action": "PATCH_OPERATOR"},
        }
    ]
    card = detect_card(rows, locked_eval_ids=set(args.locked_eval_id))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
