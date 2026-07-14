#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import textwrap
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10139
NAME = "stage10139_first_wave_bundle_runtime_payload"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PAYLOAD = OUT_DIR / "first_wave_bundle_runtime_payload.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FIRST_WAVE_BUNDLE_RUNTIME_PAYLOAD_STAGE10139.md"

SOURCE = ROOT / "runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_admitted_manifest.json"

CELL_KEY_BY_LANGUAGE = {
    "python": "full_product_harness::python::edit_localization",
    "rust": "full_product_harness::rust::edit_localization",
    "c_cpp": "full_product_harness::c_cpp::edit_localization",
    "web_js_ts_html": "full_product_harness::web_js_ts_html::edit_localization",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile one admitted first-wave maintainer bundle per language into executable prompt rows.")
    parser.add_argument("--source", type=Path, default=SOURCE, help="Admitted bundle manifest to compile into the runtime payload.")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR, help="Output directory for the payload artifact.")
    parser.add_argument("--summary", type=Path, default=SUMMARY, help="Summary JSON path.")
    parser.add_argument("--doc", type=Path, default=DOC, help="Documentation output path.")
    return parser.parse_args()


def snippet(text: str, limit: int = 600) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)] + "..."


def selected_test_count(bundle: dict[str, Any]) -> int:
    selected = bundle.get("selected_tests")
    if isinstance(selected, list):
        return len(selected)
    total = 0
    for row in bundle.get("perspective_rows") or []:
        contract = row.get("prompt_contract") if isinstance(row, dict) and isinstance(row.get("prompt_contract"), dict) else {}
        tests = contract.get("selected_tests")
        if isinstance(tests, list):
            total = max(total, len(tests))
    return total


def candidate_path_count(bundle: dict[str, Any]) -> int:
    paths = bundle.get("candidate_paths")
    return len(paths) if isinstance(paths, list) else 0


def choose_bundles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        language = str(row.get("language_family") or "")
        grouped.setdefault(language, []).append(row)
    chosen: list[dict[str, Any]] = []
    for language, cell_key in CELL_KEY_BY_LANGUAGE.items():
        candidates = grouped.get(language) or []
        if not candidates:
            continue
        ranked = sorted(
            candidates,
            key=lambda row: (
                selected_test_count(row),
                candidate_path_count(row),
                len(str(row.get("bundle_id") or "")),
            ),
            reverse=True,
        )
        picked = dict(ranked[0])
        picked["cell_key"] = cell_key
        chosen.append(picked)
    return chosen


def evidence_sections(bundle: dict[str, Any], visible_keys: list[str]) -> str:
    evidence = bundle.get("maintainer_visible_evidence") if isinstance(bundle.get("maintainer_visible_evidence"), dict) else {}
    sections: list[str] = []
    for key in visible_keys:
        values = evidence.get(key)
        if not isinstance(values, list) or not values:
            continue
        lines = []
        for idx, item in enumerate(values[:2], start=1):
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            source_type = str(item.get("source_type") or "")
            text = snippet(str(item.get("text") or ""))
            label = f"{idx}. {path}" if path else f"{idx}."
            if source_type:
                label += f" [{source_type}]"
            lines.append(f"{label}\n{text}")
        if lines:
            sections.append(f"{key}:\n" + "\n\n".join(lines))
    return "\n\n".join(sections)


def answer_instruction(answer_kind: str, gold: dict[str, Any]) -> str:
    if answer_kind == "candidate_path":
        return "Return only the exact candidate path."
    if answer_kind == "selected_test":
        return "Return only the exact selected test path."
    if answer_kind == "visible_evidence_key":
        return "Return only the exact visible evidence key."
    if answer_kind == "abstain":
        return "Return only `ABSTAIN_INSUFFICIENT_EVIDENCE`."
    if answer_kind in {"freeform_explanation", "freeform_risk"}:
        return "Return one short sentence only."
    return f"Return only the exact answer value. Expected kind: {answer_kind}."


def compile_prompt(bundle: dict[str, Any], gold: dict[str, Any]) -> str:
    perspective = str(gold.get("perspective") or "")
    task = ""
    visible_keys: list[str] = []
    candidate_paths = gold.get("candidate_paths") if isinstance(gold.get("candidate_paths"), list) else []
    selected_tests = gold.get("selected_tests") if isinstance(gold.get("selected_tests"), list) else []
    for row in bundle.get("perspective_rows") or []:
        if not isinstance(row, dict) or str(row.get("perspective") or "") != perspective:
            continue
        contract = row.get("prompt_contract") if isinstance(row.get("prompt_contract"), dict) else {}
        task = str(contract.get("task") or "")
        visible_keys = [str(value) for value in contract.get("visible_evidence_keys") or [] if value]
        if not candidate_paths:
            candidate_paths = [str(value) for value in contract.get("candidate_paths") or [] if value]
        if not selected_tests:
            selected_tests = [str(value) for value in contract.get("selected_tests") or [] if value]
        break
    evidence = evidence_sections(bundle, visible_keys)
    answer_kind = str(gold.get("gold_answer_kind") or "")
    prompt = f"""
    You are evaluating a maintainer-grade software maintenance root case.

    Language family: {bundle.get("language_family")}
    Bundle id: {bundle.get("bundle_id")}
    Perspective: {perspective}

    Task:
    {task}

    Candidate paths:
    {chr(10).join(f"- {path}" for path in candidate_paths) if candidate_paths else "- none provided"}

    Selected tests:
    {chr(10).join(f"- {path}" for path in selected_tests) if selected_tests else "- none provided"}

    Visible evidence:
    {evidence if evidence else "No visible evidence blocks were attached."}

    Output rule:
    {answer_instruction(answer_kind, gold)}
    Do not explain your answer unless the answer itself is a one-sentence explanation/risk.
    """
    return textwrap.dedent(prompt).strip() + "\n"


def compile_row(bundle: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    perspective = str(gold.get("perspective") or "")
    prompt = compile_prompt(bundle, gold)
    answer_kind = str(gold.get("gold_answer_kind") or "")
    return {
        "row_id": f"{bundle['bundle_id']}::{perspective}",
        "bundle_id": bundle["bundle_id"],
        "language_family": bundle["language_family"],
        "route": "DIRECT_ANSWER_MAINTAINER_BUNDLE",
        "objective_family": "maintainer_bundle_direct_answer",
        "surface": "edit_localization",
        "task_type": perspective,
        "perspective": perspective,
        "expected_answer_kind": answer_kind,
        "expected_label": gold.get("gold_answer_value"),
        "prompt": prompt,
        "prompt_text": prompt,
        "input_text": prompt,
        "query_text": f"maintainer_bundle::{bundle['language_family']}::{perspective}::{answer_kind}",
        "target_text": str(gold.get("gold_answer_value") or ""),
        "split": "strict_eval",
        "selected_tests": list(gold.get("selected_tests") or []),
        "candidate_paths": list(gold.get("candidate_paths") or []),
        "visible_evidence_keys": list(gold.get("visible_evidence_keys") or []),
    }


def build_payload(source: Path) -> dict[str, Any]:
    data = load_json(source)
    source_rows = [row for row in data.get("rows") or [] if isinstance(row, dict)]
    chosen = choose_bundles(source_rows)
    failures: list[str] = []
    runs: list[dict[str, Any]] = []
    selection_summary: list[dict[str, Any]] = []
    for bundle in chosen:
        gold_path = ROOT / str(bundle.get("perspective_gold_adjudication") or "")
        gold = load_json(gold_path)
        answers = [row for row in gold.get("perspective_gold_answers") or [] if isinstance(row, dict)]
        if len(answers) != 8:
            failures.append(f"gold_answer_count_not_8::{bundle.get('bundle_id')}")
            continue
        rows = [compile_row(bundle, answer) for answer in answers]
        task_pack = {
            "bundle_id": bundle["bundle_id"],
            "task_pack_id": bundle["bundle_id"],
            "source_id": bundle["bundle_id"],
            "lineage_hash": bundle["bundle_id"],
            "split_role": "locked_regression",
            "train_eligible": False,
            "promotion_only": True,
            "hidden_final": False,
            "language_family": bundle["language_family"],
            "skill_area": "edit_localization",
            "slice_tags": ["maintainer_bundle", bundle["language_family"], "first_wave", "admitted"],
            "thresholds": {"must_compare_100m_and_gemma": True, "root_scoring_primary": True},
            "blocked_training_reason": "first_wave_admitted_bundle_eval_only",
            "rows": rows,
            "maintainer_bundle_mode": True,
            "gold_answers_path": display(gold_path),
            "selected_tests": list(bundle.get("selected_tests") or []),
            "candidate_paths": list(bundle.get("candidate_paths") or []),
        }
        runs.append(
            {
                "cell_key": bundle["cell_key"],
                "task_pack": task_pack,
                "hundred_m_backend": {
                    "kind": "preserved_bundle_prompt_generation",
                    "model_bundle_manifest": "/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/agentkernel_lite_encdec_manifest.json",
                    "model_weights": "/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/model/model.safetensors",
                    "tokenizer_json": "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json",
                    "tokenizer_config": "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json",
                    "max_encoder_tokens": 1024,
                    "max_new_tokens": 80,
                    "device": "cpu",
                },
                "gemma_backend": {
                    "kind": "ollama_generate",
                    "model": "gemma3:12b",
                    "seed": 0,
                    "temperature": 0.0,
                },
            }
        )
        selection_summary.append(
            {
                "cell_key": bundle["cell_key"],
                "bundle_id": bundle["bundle_id"],
                "language_family": bundle["language_family"],
                "selected_tests": selected_test_count(bundle),
                "candidate_paths": candidate_path_count(bundle),
                "gold_answers_path": display(gold_path),
            }
        )
    return {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures and len(runs) == 4,
        "failures": failures,
        "runtime_payload_version": "stage10139.first_wave.v1",
        "created_at_utc": now_utc(),
        "selection_summary": selection_summary,
        "runs": runs,
    }


def main() -> None:
    args = parse_args()
    out_dir = args.out_dir
    payload_path = out_dir / "first_wave_bundle_runtime_payload.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.doc.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args.source)
    write = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    payload_path.write_text(write, encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": payload["passed"],
        "artifacts": {"payload": display(payload_path), "source": display(args.source), "doc": display(args.doc)},
        "metrics": {
            "selected_runs": len(payload.get("runs") or []),
            "languages": sorted({row.get("language_family") for row in payload.get("selection_summary") or []}),
            "failures": len(payload.get("failures") or []),
        },
        "decision": "Compiled one admitted first-wave maintainer bundle per language into executable prompt rows and mapped them onto the canonical Stage10081 language cell keys so the Stage10140 runner can reuse the reserved machine-artifact writeback path.",
        "next_best_step": "Run Stage10140 first-wave bundle inference for 100M and Gemma on this payload, then write the machine artifacts through the Stage10081 adapter.",
        "created_at_utc": now_utc(),
    }
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.doc.write_text(
        "\n".join(
            [
                "# Stage10139 First-Wave Bundle Runtime Payload",
                "",
                f"Passed: `{summary['passed']}`",
                f"Selected runs: `{summary['metrics']['selected_runs']}`",
                "",
                summary["decision"],
                "",
                f"Next: {summary['next_best_step']}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "payload": display(payload_path), "failures": payload["failures"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
