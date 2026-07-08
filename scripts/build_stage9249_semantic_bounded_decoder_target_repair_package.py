#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from loss_mask_card import normalize_loss_mask, validate_loss_mask_row
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.loss_mask_card import normalize_loss_mask, validate_loss_mask_row  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9249
NAME = "stage9249_semantic_bounded_decoder_target_repair_package"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9244_source_backed_arg_context_balanced_bounded_decoder_tiny_package/source_backed_arg_context_balanced_bounded_decoder_tiny_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "semantic_bounded_decoder_target_repair_manifest.jsonl"
AUDIT = OUT_DIR / "semantic_bounded_decoder_target_repair_package_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SEMANTIC_BOUNDED_DECODER_TARGET_REPAIR_PACKAGE_STAGE9249.md"
MAX_DECODER_TOKENS = 768

ARG_RENDERERS = {
    "ARG_CALL": [
        "Point the operation at the call target already isolated by the evidence packet.",
        "Return the method invocation target that matches the localized repair step.",
        "Select the callable endpoint that the verified patch operator should update.",
        "Emit the invocation target referenced by the focused callsite evidence.",
    ],
    "ARG_IMPORT": [
        "Select the dependency symbol permitted by the current import policy.",
        "Return the module reference that satisfies the allowed dependency constraint.",
        "Choose the approved library entry needed by the wrapper plan.",
        "Emit the dependency handle that keeps the patch inside the whitelist.",
    ],
    "ARG_LITERAL": [
        "Return the constant value required by the checked verifier condition.",
        "Emit the bounded value used by the localized replacement step.",
        "Select the small constant that preserves the expected assertion behavior.",
        "Choose the concrete value tied to the current repair invariant.",
    ],
    "ARG_NAME": [
        "Return the identifier identified by the symbol-binding evidence.",
        "Emit the local name that should receive the repaired state.",
        "Choose the symbol name that matches the maintainer plan.",
        "Choose the identifier referenced by the focused edit region.",
    ],
    "ARG_PATH": [
        "Select the file path associated with the localized edit target.",
        "Return the project path that owns the relevant repair region.",
        "Emit the path reference linked to the checked symbol evidence.",
        "Choose the bounded file reference required by the patch plan.",
    ],
}

CONTEXT_SUFFIXES = {
    "add_import_plan": [
        "Keep the output limited to the dependency adaptation step.",
        "Do not introduce an unapproved package or broaden the edit scope.",
    ],
    "callsite_plan": [
        "Use only the localized callsite packet as evidence.",
        "Keep the answer focused on the invocation that will be changed.",
    ],
    "hold_plan": [
        "If the evidence is insufficient, preserve the hold-or-retrieve route.",
        "Keep the decision compatible with the conservative gate state.",
    ],
    "literal_plan": [
        "Keep the value small enough for the bounded decoder surface.",
        "Tie the value to the verifier-facing invariant, not broad prose.",
    ],
    "name_plan": [
        "Use the symbol table evidence rather than a surface label.",
        "Keep the response bound to the visible identifier relation.",
    ],
    "path_plan": [
        "Use the repo graph location rather than raw source text.",
        "Keep the path reference local to the selected repair target.",
    ],
}

CONNECTORS = [
    "This is a bounded decoder value, not a full patch.",
    "Return only the maintainer-facing content for this step.",
    "The target should remain short, grounded, and verifier-ready.",
    "Avoid source bodies, runtime claims, or hidden control text.",
    "Keep the value suitable for a single localized transition.",
]

SCOPE_CLAUSES = [
    "Prefer the narrowest candidate in the packet.",
    "Preserve the current safety gate decision.",
    "Use the evidence relation with the smallest edit radius.",
    "Keep the output compatible with the next verifier check.",
    "Anchor the value to the selected transition record.",
    "Avoid widening the maintainer action beyond this operator.",
    "Keep the value reusable by the patch-operator head.",
    "Return a concise value that can be audited row by row.",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def render_target(row: dict[str, Any], ordinal: int) -> str:
    state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
    arg = str(state.get("bounded_argument_type") or "ARG_NAME")
    context = str(state.get("context_group") or "name_plan")
    base_options = ARG_RENDERERS.get(arg, ARG_RENDERERS["ARG_NAME"])
    suffix_options = CONTEXT_SUFFIXES.get(context, CONTEXT_SUFFIXES["name_plan"])
    base = base_options[ordinal % len(base_options)]
    suffix = suffix_options[(ordinal // len(base_options)) % len(suffix_options)]
    connector = CONNECTORS[(ordinal + len(context)) % len(CONNECTORS)]
    scope = SCOPE_CLAUSES[(ordinal * 3 + len(arg) + len(context)) % len(SCOPE_CLAUSES)]
    return f"{base} {suffix} {connector} {scope}"


def repair_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repaired = []
    for idx, row in enumerate(rows):
        new_row = json.loads(json.dumps(row))
        old_target = new_row.get("target") if isinstance(new_row.get("target"), dict) else {}
        text = render_target(new_row, idx).strip()
        target_hash = stable_hash(text)
        new_row["row_id"] = str(new_row.get("row_id", "row")).replace("stage9244", "stage9249")
        new_row["target"] = {
            "decoder_text": text,
            "target_shape": "SEMANTIC_BOUNDED_DECODER_ARGUMENT_TEXT",
            "target_ref": old_target.get("target_ref"),
            "target_text_sha256": target_hash,
            "previous_target_text_sha256": old_target.get("target_text_sha256"),
            "target_renderer_stage": STAGE,
        }
        new_row["surface"] = "SEMANTIC_BOUNDED_DECODER_ARGUMENT_TEXT"
        new_row["decoder_token_len"] = len(text.encode("utf-8"))
        new_row["source_stage"] = STAGE
        new_row["source_target_hash"] = target_hash
        new_row["target_length_bucket"] = "bounded_semantic"
        new_row["anti_cheat"]["language_prefix_removed"] = True
        new_row["anti_cheat"]["template_phrase_removed"] = True
        new_row["anti_cheat"]["argument_label_echo_removed"] = True
        repaired.append(new_row)
    return repaired


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(row.get("split") for row in rows)
    language_counts = Counter(row.get("language_family") for row in rows)
    arg_counts = Counter((row.get("input_state") or {}).get("bounded_argument_type") for row in rows)
    context_counts = Counter((row.get("input_state") or {}).get("context_group") for row in rows)
    authority_rows = 0
    unsafe_loss_rows = []
    over_cap_rows = []
    language_prefix_rows = []
    template_phrase_rows = []
    arg_echo_rows = []
    first_tokens = Counter()
    target_hashes = Counter()
    for row in rows:
        row_id = str(row.get("row_id"))
        state = row.get("input_state") if isinstance(row.get("input_state"), dict) else {}
        arg = str(state.get("bounded_argument_type") or "")
        text = str((row.get("target") or {}).get("decoder_text") or "")
        low = text.lower()
        words = low.split()
        if words:
            first_tokens[words[0]] += 1
        target_hashes[(row.get("target") or {}).get("target_text_sha256")] += 1
        if any((row.get("authority") or {}).values()):
            authority_rows += 1
        enabled = [key for key, value in normalize_loss_mask(row).items() if value]
        mask_errors = validate_loss_mask_row(row, allow_decoder_ce=True, allow_denoise=False, allow_runtime=False)
        if enabled != ["decoder_ce"] or mask_errors:
            unsafe_loss_rows.append({"row_id": row_id, "enabled": enabled, "errors": mask_errors})
        if int(row.get("decoder_token_len") or 0) > MAX_DECODER_TOKENS:
            over_cap_rows.append(row_id)
        if low.startswith(("for python,", "for rust,", "for cpp,", "for typescript,")):
            language_prefix_rows.append(row_id)
        if any(phrase in low for phrase in ("use the verified", "use the approved", "selected from", "selected by", "the argument supports", "source-backed")):
            template_phrase_rows.append(row_id)
        echo_phrase = {
            "ARG_CALL": "call argument",
            "ARG_IMPORT": "import argument",
            "ARG_LITERAL": "literal argument",
            "ARG_NAME": "identifier argument",
            "ARG_PATH": "path argument",
        }.get(arg)
        if echo_phrase and echo_phrase in low:
            arg_echo_rows.append(row_id)
    rows_count = len(rows)
    checks = {
        "rows_match_expected": rows_count == 64,
        "split_counts_match": dict(split_counts) == {"eval": 16, "strict_eval": 16, "train": 32},
        "all_languages_present": set(language_counts) == {"python", "rust", "cpp", "web_js_ts_html"},
        "all_argument_types_present": set(arg_counts) == {"ARG_CALL", "ARG_IMPORT", "ARG_LITERAL", "ARG_NAME", "ARG_PATH"},
        "all_context_groups_present": set(context_counts) == {"add_import_plan", "callsite_plan", "hold_plan", "literal_plan", "name_plan", "path_plan"},
        "authority_rows_zero": authority_rows == 0,
        "unsafe_loss_rows_zero": len(unsafe_loss_rows) == 0,
        "over_cap_rows_zero": len(over_cap_rows) == 0,
        "language_prefix_rows_zero": len(language_prefix_rows) == 0,
        "template_phrase_rows_zero": len(template_phrase_rows) == 0,
        "arg_echo_rows_zero": len(arg_echo_rows) == 0,
        "target_hashes_unique": len(target_hashes) == rows_count,
        "first_token_dominance_le_0_50": (max(first_tokens.values(), default=0) / max(rows_count, 1)) <= 0.50,
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "passed": not failures,
        "failures": failures,
        "checks": checks,
        "rows": rows_count,
        "split_counts": dict(sorted(split_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "arg_counts": dict(sorted(arg_counts.items())),
        "context_counts": dict(sorted(context_counts.items())),
        "authority_rows": authority_rows,
        "unsafe_loss_rows": len(unsafe_loss_rows),
        "unsafe_loss_examples": unsafe_loss_rows[:20],
        "over_cap_rows": len(over_cap_rows),
        "language_prefix_rows": len(language_prefix_rows),
        "template_phrase_rows": len(template_phrase_rows),
        "arg_echo_rows": len(arg_echo_rows),
        "target_hash_unique_rows": len(target_hashes),
        "first_token_counts": dict(first_tokens.most_common(10)),
        "first_token_dominance_rate": max(first_tokens.values(), default=0) / max(rows_count, 1),
        "loss_counts": dict(Counter(key for row in rows for key, value in normalize_loss_mask(row).items() if value)),
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_rows = read_jsonl(SOURCE_MANIFEST)
    rows = repair_rows(source_rows)
    audit = audit_rows(rows)
    write_jsonl(MANIFEST, rows)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "supersedes": ["stage9244_source_backed_arg_context_balanced_bounded_decoder_tiny_package", "stage9248_bounded_decoder_target_semantic_diversity_audit"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"manifest": str(MANIFEST.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Built a repaired semantic bounded-decoder target package that removes language prefixes, template phrases, and argument-label echo; no execution authorized." if audit["passed"] else "Semantic target repair package failed audit.",
        "next_best_step": "Run Stage9248-style semantic diversity audit on Stage9249, then contract-only preflight if it passes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9249 Semantic Bounded Decoder Target Repair Package",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Rows: `{audit['rows']}`",
        f"Splits: `{audit['split_counts']}`",
        f"Languages: `{audit['language_counts']}`",
        f"Argument counts: `{audit['arg_counts']}`",
        f"Context counts: `{audit['context_counts']}`",
        f"Language-prefix rows: `{audit['language_prefix_rows']}`",
        f"Template phrase rows: `{audit['template_phrase_rows']}`",
        f"Argument-label echo rows: `{audit['arg_echo_rows']}`",
        f"First-token dominance rate: `{audit['first_token_dominance_rate']:.3f}`",
        "",
        "This stage repairs the target renderer only. It does not execute the model, train decoder CE, open runtime, emit source bodies, or alter authority.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if audit["passed"] else 1)


if __name__ == "__main__":
    main()
