#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
NAME = "stage11519_source_heldout_smoke_candidate_miner"
OUT_DIR = ART / NAME
OUT_JSON = SUM / f"{NAME}.json"

LANGUAGES = ("python", "rust", "c_cpp", "web_js_ts_html")
MAX_FILE_MB = 64


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def iter_jsonl_rows(path: Path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    yield line_no, row
    except OSError:
        return


def candidate_files() -> list[Path]:
    files: list[Path] = []
    for path in ART.rglob("*.jsonl"):
        try:
            if path.stat().st_size > MAX_FILE_MB * 1024 * 1024:
                continue
        except OSError:
            continue
        name = path.name.lower()
        text = str(path).lower()
        if any(token in name or token in text for token in ("row", "manifest", "heldout", "strict", "support", "verifier", "evidence")):
            files.append(path)
    return sorted(files)


def row_language(row: dict[str, Any]) -> str:
    return str(row.get("language_family") or row.get("language") or row.get("lang") or "unknown")


def row_id(row: dict[str, Any], path: Path, line_no: int) -> str:
    return str(row.get("row_id") or row.get("id") or f"{rel(path)}:{line_no}")


def option_count(row: dict[str, Any]) -> int:
    options = row.get("opaque_options") or row.get("options") or row.get("candidate_options") or []
    if isinstance(options, list):
        return len([opt for opt in options if isinstance(opt, (dict, str))])
    return 0


def bool_field(row: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        if row.get(key) is True:
            return True
        if isinstance(row.get(key), dict):
            # Not used now, but keep this conservative for nested future schemas.
            continue
    return False


def anti_cheat_bool(row: dict[str, Any], key: str) -> bool:
    anti = row.get("anti_cheat")
    if isinstance(anti, dict) and anti.get(key) is True:
        return True
    return row.get(key) is True


def split_hint(row: dict[str, Any], path: Path) -> str:
    bits = [
        str(row.get("split") or ""),
        str(row.get("split_role") or ""),
        str(row.get("source_split_before_stage11436") or ""),
        path.name,
        str(path.parent.name),
    ]
    return " ".join(bits).lower()


def source_heldout_attested(row: dict[str, Any], path: Path) -> bool:
    if row.get("source_heldout_admissible") is True:
        return True
    if row.get("source_heldout") is True:
        return True
    # Treat these as near-miss evidence only elsewhere, not hard admission.
    return False


def heldout_like(row: dict[str, Any], path: Path) -> bool:
    hint = split_hint(row, path)
    return any(token in hint for token in ("heldout", "strict", "eval", "validation"))


def has_prompt_target_leak(row: dict[str, Any]) -> bool:
    if row.get("prompt_target_value_leak") is True:
        return True
    anti = row.get("anti_cheat")
    if isinstance(anti, dict) and anti.get("prompt_target_value_leak") is True:
        return True
    return False


def has_verifier(row: dict[str, Any]) -> bool:
    return bool(
        row.get("has_verifier_row_or_transition") is True
        or row.get("verifier_anchor") is True
        or row.get("selected_test_anchor") is True
        or row.get("verifier_transition")
        or row.get("selected_test_id")
        or row.get("test_id")
    )


def has_patch_or_abstain(row: dict[str, Any]) -> bool:
    task = str(row.get("task_type") or row.get("perspective") or "").lower()
    return bool(
        row.get("has_patch_or_abstain_row") is True
        or "patch" in task
        or "abstention" in task
        or str(row.get("decoder_text") or row.get("target") or "").upper().startswith("ABSTAIN")
    )


def row_summary(row: dict[str, Any], path: Path, line_no: int, blockers: list[str]) -> dict[str, Any]:
    return {
        "row_id": row_id(row, path, line_no),
        "source_file": rel(path),
        "line_no": line_no,
        "language_family": row_language(row),
        "repo_family": row.get("repo_family") or row.get("repo_id"),
        "source_root_id": row.get("source_root_id") or row.get("root_id") or row.get("source_bundle_id"),
        "task_type": row.get("task_type") or row.get("perspective") or row.get("target_type"),
        "split": row.get("split"),
        "split_role": row.get("split_role"),
        "option_count": option_count(row),
        "source_heldout_admissible": row.get("source_heldout_admissible"),
        "heldout_like": heldout_like(row, path),
        "deterministic_option_shuffle": anti_cheat_bool(row, "deterministic_option_shuffle"),
        "opaque_labels": anti_cheat_bool(row, "opaque_labels") or option_count(row) > 1,
        "selected_test_anchor": row.get("selected_test_anchor"),
        "verifier_anchor": row.get("verifier_anchor"),
        "has_verifier_row_or_transition": row.get("has_verifier_row_or_transition"),
        "has_patch_or_abstain_row": row.get("has_patch_or_abstain_row"),
        "prompt_target_value_leak": has_prompt_target_leak(row),
        "blockers": blockers,
    }


def blockers_for(row: dict[str, Any], path: Path) -> list[str]:
    blockers: list[str] = []
    if row_language(row) not in LANGUAGES:
        blockers.append("unsupported_or_missing_language")
    if not source_heldout_attested(row, path):
        blockers.append("source_heldout_not_attested")
    if not anti_cheat_bool(row, "deterministic_option_shuffle"):
        blockers.append("option_shuffle_not_declared")
    if option_count(row) < 2:
        blockers.append("singleton_or_missing_options")
    if has_prompt_target_leak(row):
        blockers.append("prompt_target_value_leak")
    if not has_verifier(row):
        blockers.append("missing_verifier_or_selected_test_anchor")
    if not has_patch_or_abstain(row):
        blockers.append("missing_patch_or_abstain_signal")
    return blockers


def main() -> None:
    files = candidate_files()
    admitted: list[dict[str, Any]] = []
    near_attestation: list[dict[str, Any]] = []
    near_repairable: list[dict[str, Any]] = []
    blocker_counts: dict[str, Counter[str]] = defaultdict(Counter)
    scanned_rows = 0
    language_counts: Counter[str] = Counter()

    for path in files:
        for line_no, row in iter_jsonl_rows(path):
            scanned_rows += 1
            lang = row_language(row)
            language_counts[lang] += 1
            if lang not in LANGUAGES:
                continue
            blockers = blockers_for(row, path)
            for blocker in blockers:
                blocker_counts[lang][blocker] += 1
            summary = row_summary(row, path, line_no, blockers)
            if not blockers:
                admitted.append(summary)
            elif blockers == ["source_heldout_not_attested"] and heldout_like(row, path):
                near_attestation.append(summary)
            elif len(blockers) <= 2 and "prompt_target_value_leak" not in blockers and "singleton_or_missing_options" not in blockers:
                near_repairable.append(summary)

    def by_language(rows: list[dict[str, Any]]) -> dict[str, int]:
        counts: Counter[str] = Counter(str(row.get("language_family") or "unknown") for row in rows)
        return {lang: counts.get(lang, 0) for lang in LANGUAGES}

    min_smoke_ready = all(by_language(admitted).get(lang, 0) >= 1 for lang in LANGUAGES)
    payload = {
        "stage": 11519,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "minimal_source_heldout_smoke_candidates_found" if min_smoke_ready else "minimal_source_heldout_smoke_still_needs_materialization",
        "metrics": {
            "files_scanned": len(files),
            "rows_scanned": scanned_rows,
            "language_counts": dict(sorted(language_counts.items())),
            "admitted_candidates": len(admitted),
            "admitted_by_language": by_language(admitted),
            "near_source_heldout_attestation_only": len(near_attestation),
            "near_attestation_by_language": by_language(near_attestation),
            "near_repairable_candidates": len(near_repairable),
            "near_repairable_by_language": by_language(near_repairable),
            "blockers_by_language": {
                lang: dict(sorted(blocker_counts.get(lang, Counter()).items())) for lang in LANGUAGES
            },
            "minimal_smoke_ready": min_smoke_ready,
        },
        "admitted_sample": admitted[:50],
        "near_source_heldout_attestation_sample": near_attestation[:50],
        "near_repairable_sample": near_repairable[:50],
        "claim_boundary": [
            "Hard admission requires explicit source_heldout_admissible/source_heldout attestation; heldout-like filenames alone are near-miss evidence, not enough.",
            "This stage mines existing artifacts only. It does not fabricate fresh roots or run model/Gemma execution.",
        ],
        "outputs": {
            "admitted_candidates_jsonl": rel(OUT_DIR / "admitted_source_heldout_smoke_candidates.jsonl"),
            "near_attestation_jsonl": rel(OUT_DIR / "near_source_heldout_attestation_candidates.jsonl"),
            "near_repairable_jsonl": rel(OUT_DIR / "near_repairable_smoke_candidates.jsonl"),
        },
        "next_best_step": "If admitted_by_language is incomplete, materialize fresh source-heldout rows for missing languages or add explicit source-heldout attestation to near candidates only when provenance proves it.",
    }
    write_jsonl(OUT_DIR / "admitted_source_heldout_smoke_candidates.jsonl", admitted)
    write_jsonl(OUT_DIR / "near_source_heldout_attestation_candidates.jsonl", near_attestation)
    write_jsonl(OUT_DIR / "near_repairable_smoke_candidates.jsonl", near_repairable)
    write_json(OUT_DIR / f"{NAME}.json", payload)
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
