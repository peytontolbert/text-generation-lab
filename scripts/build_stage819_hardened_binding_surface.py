#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import re
from typing import Any


ENTITY_RE = re.compile(r"\b(?:gdom_\d+_e\d+|gdom_999_e\d+)\b")
KV_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]*?)=([^\s;]+)")
HAS_FIELD_RE = re.compile(r"\bhas\s+([A-Za-z][A-Za-z0-9_]*)\b")
RELATION_QUERY_RE = re.compile(r"\bquery=\S+\s+([A-Za-z][A-Za-z0-9_]*)\b")
COMPOSITION_FIELD_RELATION_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_]*)\s+of\s+([A-Za-z][A-Za-z0-9_]*)\s+target\s+for\b"
)
VALUE_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_]*_v\d+\b")
TARGET_OPS = {
    "atomic_fact",
    "relation",
    "composition",
    "counterfactual_false_claim",
    "exception",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _kv(text: str) -> dict[str, str]:
    return {str(key): str(value) for key, value in KV_RE.findall(str(text or ""))}


def _stable_code(value: str, *, prefix: str, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}|{value}".encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _field_hints(text: str) -> set[str]:
    values = _kv(text)
    fields: set[str] = set()
    gsel = str(values.get("gsel", "") or "")
    parts = [part for part in gsel.split("|") if part]
    for index in (2, 3):
        if len(parts) > index and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", parts[index]):
            fields.add(parts[index])
    for key in ("field", "relation"):
        value = str(values.get(key, "") or "")
        if value and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
            fields.add(value)
    for match in HAS_FIELD_RE.finditer(str(text or "")):
        fields.add(match.group(1))
    for match in RELATION_QUERY_RE.finditer(str(text or "")):
        fields.add(match.group(1))
    for match in COMPOSITION_FIELD_RELATION_RE.finditer(str(text or "")):
        fields.add(match.group(1))
        fields.add(match.group(2))
    return fields


def _replace_token(text: str, token: str, replacement: str) -> str:
    return re.sub(rf"\b{re.escape(token)}\b", replacement, text)


def _harden_text(
    text: str,
    *,
    side: str,
    salt: str,
    harden_values: bool = False,
) -> tuple[str, dict[str, str]]:
    hardened = str(text or "")
    mapping: dict[str, str] = {}
    entity_prefix = "qent" if side == "query" else "dent"
    field_prefix = "qslot" if side == "query" else "dslot"
    value_prefix = "qclaim" if side == "query" else "dclaim"

    for entity in sorted(set(ENTITY_RE.findall(hardened)), key=len, reverse=True):
        alias = _stable_code(entity, prefix=entity_prefix, salt=salt)
        hardened = _replace_token(hardened, entity, alias)
        mapping[entity] = alias

    for field in sorted(_field_hints(text), key=len, reverse=True):
        alias = _stable_code(field, prefix=field_prefix, salt=salt)
        hardened = _replace_token(hardened, field, alias)
        mapping[field] = alias

    if harden_values:
        answer_value = str(_kv(text).get("answer", "") or "")
        for value in sorted(set(VALUE_RE.findall(hardened)), key=len, reverse=True):
            if value == answer_value:
                continue
            alias = _stable_code(value, prefix=value_prefix, salt=salt)
            hardened = _replace_token(hardened, value, alias)
            mapping[value] = alias

    return hardened, mapping


def _pair_code_tokens(query_map: dict[str, str], doc_map: dict[str, str], *, salt: str) -> tuple[str, str]:
    query_codes: list[str] = []
    doc_codes: list[str] = []
    for original in sorted(set(query_map) & set(doc_map)):
        code = _stable_code(original, prefix="pair", salt=salt)
        suffix = code.removeprefix("pair_")
        query_codes.append(f"qpair_{suffix}")
        doc_codes.append(f"dpair_{suffix}")
    return " ".join(query_codes), " ".join(doc_codes)


def _harden_row(
    row: dict[str, Any],
    *,
    salt: str,
    harden_counterfactual_values: bool,
    add_pair_codes: bool,
    pair_code_salt: str,
) -> dict[str, Any]:
    operation = str(row.get("operation", "") or "")
    if operation not in TARGET_OPS:
        return dict(row)
    out = dict(row)
    query_text = str(out.get("retrieval_query_text", "") or out.get("encoder_text", "") or "")
    doc_text = str(out.get("retrieval_doc_text", "") or "")
    harden_values = bool(harden_counterfactual_values and operation == "counterfactual_false_claim")
    hardened_query, query_map = _harden_text(query_text, side="query", salt=salt, harden_values=harden_values)
    hardened_doc, doc_map = _harden_text(doc_text, side="doc", salt=salt, harden_values=harden_values)
    if add_pair_codes:
        query_codes, doc_codes = _pair_code_tokens(query_map, doc_map, salt=pair_code_salt)
        if query_codes:
            hardened_query = f"{hardened_query} latent_query_bridge={query_codes}"
        if doc_codes:
            hardened_doc = f"{hardened_doc} latent_doc_bridge={doc_codes}"
    out["retrieval_query_text"] = hardened_query
    out["encoder_text"] = hardened_query
    out["retrieval_doc_text"] = hardened_doc
    out["stage819_hardened_binding"] = {
        "mode": "query_doc_surface_disjoint_entity_field_alias",
        "harden_counterfactual_values": harden_values,
        "add_pair_codes": bool(add_pair_codes),
        "pair_code_salt": str(pair_code_salt),
        "query_aliases": query_map,
        "doc_aliases": doc_map,
    }
    return out


def _select_calibration_rows(
    rows: list[dict[str, Any]],
    *,
    fraction: float,
    stratified: bool,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if float(fraction) <= 0.0:
        return rows, []
    rng = random.Random(int(seed))
    if not stratified:
        shuffled = list(rows)
        rng.shuffle(shuffled)
        take = min(max(int(round(len(shuffled) * float(fraction))), 1), max(len(shuffled) - 1, 1))
        selected_ids = {id(row) for row in shuffled[:take]}
        return [row for row in rows if id(row) not in selected_ids], [row for row in rows if id(row) in selected_ids]
    selected_ids: set[int] = set()
    by_operation: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_operation.setdefault(str(row.get("operation", "") or "unknown"), []).append(row)
    for rows_for_operation in by_operation.values():
        take = min(
            max(int(round(len(rows_for_operation) * float(fraction))), 1),
            max(len(rows_for_operation) - 1, 1),
        )
        shuffled = list(rows_for_operation)
        rng.shuffle(shuffled)
        selected_ids.update(id(row) for row in shuffled[:take])
    return [row for row in rows if id(row) not in selected_ids], [row for row in rows if id(row) in selected_ids]


def build(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    source_manifest = json.loads(Path(args.source_manifest).read_text(encoding="utf-8"))
    source_train_rows = _iter_jsonl(Path(source_manifest["train_dataset_path"]))
    eval_rows = _iter_jsonl(Path(source_manifest["eval_dataset_path"]))
    train_rows, calibration_rows = _select_calibration_rows(
        source_train_rows,
        fraction=float(args.calibration_fraction),
        stratified=bool(args.calibration_stratified),
        seed=int(args.calibration_seed),
    )
    if bool(args.retain_calibration_in_train):
        train_rows = source_train_rows
    train_salt = str(args.train_salt or args.salt)
    eval_salt = str(args.eval_salt or args.salt)
    calibration_salt = str(args.calibration_salt or args.salt)
    pair_code_salt = str(args.pair_code_salt or "stage827_pair_code")
    hardened_train = [
        _harden_row(
            row,
            salt=train_salt,
            harden_counterfactual_values=bool(args.harden_counterfactual_values),
            add_pair_codes=bool(args.add_pair_codes),
            pair_code_salt=pair_code_salt,
        )
        for row in train_rows
    ]
    hardened_eval = [
        _harden_row(
            row,
            salt=eval_salt,
            harden_counterfactual_values=bool(args.harden_counterfactual_values),
            add_pair_codes=bool(args.add_pair_codes),
            pair_code_salt=pair_code_salt,
        )
        for row in eval_rows
    ]
    hardened_calibration = [
        _harden_row(
            row,
            salt=calibration_salt,
            harden_counterfactual_values=bool(args.harden_counterfactual_values),
            add_pair_codes=bool(args.add_pair_codes),
            pair_code_salt=pair_code_salt,
        )
        for row in calibration_rows
    ]

    output_dir = Path(args.output_dir).resolve()
    train_path = output_dir / "stage819_hardened_train.jsonl"
    eval_path = output_dir / "stage819_hardened_eval.jsonl"
    calibration_path = output_dir / "stage819_hardened_calibration.jsonl"
    manifest_path = output_dir / "agentkernel_lite_encdec_dataset_manifest.json"
    _write_jsonl(train_path, hardened_train)
    _write_jsonl(eval_path, hardened_eval)
    if hardened_calibration:
        _write_jsonl(calibration_path, hardened_calibration)

    manifest = dict(source_manifest)
    manifest["train_dataset_path"] = str(train_path)
    manifest["eval_dataset_path"] = str(eval_path)
    manifest["stage819_source_manifest"] = str(Path(args.source_manifest).resolve())
    manifest["stage819_hardening"] = {
        "target_operations": sorted(TARGET_OPS),
        "mode": "query_doc_surface_disjoint_entity_field_alias",
        "salt": str(args.salt),
        "train_salt": train_salt,
        "eval_salt": eval_salt,
        "calibration_salt": calibration_salt,
        "calibration_fraction": float(args.calibration_fraction),
        "retain_calibration_in_train": bool(args.retain_calibration_in_train),
        "calibration_stratified": bool(args.calibration_stratified),
        "calibration_seed": int(args.calibration_seed),
        "harden_counterfactual_values": bool(args.harden_counterfactual_values),
        "add_pair_codes": bool(args.add_pair_codes),
        "pair_code_salt": pair_code_salt,
    }
    if hardened_calibration:
        manifest["calibration_dataset_path"] = str(calibration_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    changed_train = sum(1 for row in hardened_train if "stage819_hardened_binding" in row)
    changed_eval = sum(1 for row in hardened_eval if "stage819_hardened_binding" in row)
    changed_calibration = sum(1 for row in hardened_calibration if "stage819_hardened_binding" in row)
    summary = {
        "artifact_kind": "stage819_hardened_binding_surface",
        "source_manifest": str(Path(args.source_manifest).resolve()),
        "dataset_manifest": str(manifest_path),
        "train_dataset_path": str(train_path),
        "eval_dataset_path": str(eval_path),
        "target_operations": sorted(TARGET_OPS),
        "train_rows": len(train_rows),
        "calibration_rows": len(calibration_rows),
        "eval_rows": len(eval_rows),
        "hardened_train_rows": changed_train,
        "hardened_calibration_rows": changed_calibration,
        "hardened_eval_rows": changed_eval,
        "decision": "Creates a hardened binding surface where target-operation query and document entity/field tokens are replaced with side-specific aliases. When counterfactual value hardening is enabled, wrong claimed values are also side-aliased while answer= values are preserved.",
    }
    output_json = Path(args.output_json).resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--output-dir", default=str(_repo_root() / "runs/local/tmp/stage819_hardened_binding_surface"))
    parser.add_argument("--output-json", default=str(_repo_root() / "runs/local/artifacts/stage819_hardened_binding_surface_summary.json"))
    parser.add_argument("--salt", default="stage819_v1")
    parser.add_argument("--train-salt", default="")
    parser.add_argument("--eval-salt", default="")
    parser.add_argument("--calibration-salt", default="")
    parser.add_argument("--calibration-fraction", type=float, default=0.0)
    parser.add_argument("--retain-calibration-in-train", action="store_true")
    parser.add_argument("--calibration-stratified", action="store_true")
    parser.add_argument("--calibration-seed", type=int, default=830)
    parser.add_argument("--harden-counterfactual-values", action="store_true")
    parser.add_argument("--add-pair-codes", action="store_true")
    parser.add_argument("--pair-code-salt", default="")
    args = parser.parse_args()
    print(json.dumps(build(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
