from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


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

VERIFIER_TYPES = {
    "semantic_equivalence",
    "property_contract",
    "metamorphic_relation",
    "api_compatibility",
    "determinism_contract",
}

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def stable_hash(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def normalize_code_shape(source: str) -> dict[str, Any]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {"syntax_ok": False, "error": str(exc), "functions": [], "classes": [], "imports": [], "returns": 0}
    functions = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    imports: list[str] = []
    returns = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Return):
            returns += 1
    return {
        "syntax_ok": True,
        "functions": sorted(functions),
        "classes": sorted(classes),
        "imports": sorted(imports),
        "returns": returns,
    }


def semantic_equivalence_check(candidate: str, reference: str, *, required_symbols: list[str] | None = None) -> dict[str, Any]:
    cand = normalize_code_shape(candidate)
    ref = normalize_code_shape(reference)
    failures: list[str] = []
    if not cand["syntax_ok"]:
        failures.append("candidate_syntax_invalid")
    if not ref["syntax_ok"]:
        failures.append("reference_syntax_invalid")
    if cand["syntax_ok"] and ref["syntax_ok"]:
        if cand["functions"] != ref["functions"]:
            failures.append("function_shape_mismatch")
        if cand["classes"] != ref["classes"]:
            failures.append("class_shape_mismatch")
        if cand["returns"] != ref["returns"]:
            failures.append("return_shape_mismatch")
    for symbol in required_symbols or []:
        if symbol not in candidate:
            failures.append(f"missing_required_symbol:{symbol}")
    return {
        "verifier_type": "semantic_equivalence",
        "passed": not failures,
        "failures": failures,
        "candidate_shape": cand,
        "reference_shape": ref,
        "authority": AUTHORITY_CLOSED,
    }


def property_contract_check(candidate: str, properties: list[Mapping[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    for prop in properties:
        prop_id = str(prop.get("property_id") or prop.get("name") or "property")
        kind = str(prop.get("kind") or "")
        value = str(prop.get("value") or "")
        if kind == "must_contain" and value not in candidate:
            failures.append(f"property_failed:{prop_id}:must_contain")
        elif kind == "must_not_contain" and value in candidate:
            failures.append(f"property_failed:{prop_id}:must_not_contain")
        elif kind == "must_define_symbol":
            shape = normalize_code_shape(candidate)
            if value not in shape.get("functions", []) and value not in shape.get("classes", []):
                failures.append(f"property_failed:{prop_id}:must_define_symbol")
        elif kind not in {"must_contain", "must_not_contain", "must_define_symbol"}:
            failures.append(f"unknown_property_kind:{prop_id}:{kind}")
    return {
        "verifier_type": "property_contract",
        "passed": not failures,
        "failures": failures,
        "property_count": len(properties),
        "authority": AUTHORITY_CLOSED,
    }


def metamorphic_relation_check(before: Mapping[str, Any], after: Mapping[str, Any], relation: Mapping[str, Any]) -> dict[str, Any]:
    relation_id = str(relation.get("relation_id") or relation.get("name") or "relation")
    kind = str(relation.get("kind") or "")
    failures: list[str] = []
    if kind == "preserve_key":
        key = str(relation.get("key") or "")
        if before.get(key) != after.get(key):
            failures.append(f"metamorphic_failed:{relation_id}:preserve_key:{key}")
    elif kind == "monotonic_non_decrease":
        key = str(relation.get("key") or "")
        try:
            if float(after.get(key, 0)) < float(before.get(key, 0)):
                failures.append(f"metamorphic_failed:{relation_id}:monotonic_non_decrease:{key}")
        except (TypeError, ValueError):
            failures.append(f"metamorphic_failed:{relation_id}:non_numeric:{key}")
    elif kind == "idempotent_hash":
        if stable_hash(before) != stable_hash(after):
            failures.append(f"metamorphic_failed:{relation_id}:idempotent_hash")
    else:
        failures.append(f"unknown_metamorphic_kind:{relation_id}:{kind}")
    return {
        "verifier_type": "metamorphic_relation",
        "passed": not failures,
        "failures": failures,
        "relation_id": relation_id,
        "kind": kind,
        "authority": AUTHORITY_CLOSED,
    }


def api_compatibility_check(candidate_api: Mapping[str, Any], expected_api: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    expected_symbols = set(map(str, expected_api.get("symbols", [])))
    candidate_symbols = set(map(str, candidate_api.get("symbols", [])))
    missing = sorted(expected_symbols - candidate_symbols)
    if missing:
        failures.extend(f"missing_api_symbol:{symbol}" for symbol in missing)
    expected_signatures = expected_api.get("signatures") if isinstance(expected_api.get("signatures"), dict) else {}
    candidate_signatures = candidate_api.get("signatures") if isinstance(candidate_api.get("signatures"), dict) else {}
    for symbol, signature in expected_signatures.items():
        if candidate_signatures.get(symbol) != signature:
            failures.append(f"signature_mismatch:{symbol}")
    return {
        "verifier_type": "api_compatibility",
        "passed": not failures,
        "failures": failures,
        "missing_symbols": missing,
        "authority": AUTHORITY_CLOSED,
    }


def determinism_contract_check(outputs: list[Any]) -> dict[str, Any]:
    hashes = [stable_hash(output) for output in outputs]
    failures = [] if len(set(hashes)) <= 1 else ["non_deterministic_outputs"]
    return {
        "verifier_type": "determinism_contract",
        "passed": not failures,
        "failures": failures,
        "output_count": len(outputs),
        "unique_output_hashes": len(set(hashes)),
        "authority": AUTHORITY_CLOSED,
    }


def verifier_card(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for row in rows:
        typ = str(row.get("verifier_type") or "")
        if typ == "semantic_equivalence":
            check = semantic_equivalence_check(str(row.get("candidate", "")), str(row.get("reference", "")), required_symbols=list(row.get("required_symbols") or []))
        elif typ == "property_contract":
            check = property_contract_check(str(row.get("candidate", "")), list(row.get("properties") or []))
        elif typ == "metamorphic_relation":
            check = metamorphic_relation_check(dict(row.get("before") or {}), dict(row.get("after") or {}), dict(row.get("relation") or {}))
        elif typ == "api_compatibility":
            check = api_compatibility_check(dict(row.get("candidate_api") or {}), dict(row.get("expected_api") or {}))
        elif typ == "determinism_contract":
            check = determinism_contract_check(list(row.get("outputs") or []))
        else:
            check = {"verifier_type": typ, "passed": False, "failures": [f"unknown_verifier_type:{typ}"], "authority": AUTHORITY_CLOSED}
        check["row_id"] = str(row.get("row_id") or row.get("id") or "")
        checks.append(check)
    return {
        "rows": len(rows),
        "passed": all(check["passed"] for check in checks),
        "failed_rows": sum(1 for check in checks if not check["passed"]),
        "checks": checks,
        "authority": AUTHORITY_CLOSED,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="No-execution semantic equivalence/metamorphic verifier contract.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = read_jsonl(args.input) if args.input else [
        {"row_id": "eq", "verifier_type": "semantic_equivalence", "candidate": "def f(x):\n    return x\n", "reference": "def f(y):\n    return y\n"},
        {"row_id": "prop", "verifier_type": "property_contract", "candidate": "def validate_token(x):\n    return x\n", "properties": [{"property_id": "symbol", "kind": "must_define_symbol", "value": "validate_token"}]},
    ]
    card = verifier_card(rows)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
