#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.request
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.training_data import _row_text

MANIFEST = ROOT / "runs/local/artifacts/stage10378_balanced_residual_probe_execution_request/balanced_residual_probe_manifest.jsonl"
POLICY_100M = ROOT / "runs/local/artifacts/stage10404_generic_policy_frontier_eval/language_conditioned_frontier_eval.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage10406_gemma_same_frontier_comparison"
ROWS_PATH = OUT_DIR / "gemma_same_frontier_rows.jsonl"
SUMMARY_PATH = OUT_DIR / "gemma_same_frontier_comparison.json"
MODEL = "gemma3:12b"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def perspective(row: dict[str, object]) -> str:
    prompt = str(row.get("prompt_text") or "")
    for line in prompt.splitlines():
        if line.startswith("Perspective: "):
            return line.split(": ", 1)[1].strip()
    return ""


def option_pairs(row: dict[str, object]) -> list[tuple[str, str]]:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    return [(str(option["label"]), str(option["value"])) for option in options]


def prompt_surface_hash(rows: list[dict[str, object]]) -> str:
    payload = []
    for row in sorted(rows, key=lambda item: str(item["row_id"])):
        payload.append(
            {
                "row_id": row["row_id"],
                "language_family": row.get("language_family"),
                "perspective": perspective(row),
                "target": row.get("decoder_text"),
                "surface_text": _row_text(row),
                "opaque_options": option_pairs(row),
            }
        )
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_prompt(row: dict[str, object]) -> str:
    labels = [label for label, _ in option_pairs(row)]
    return "\n".join(
        [
            "You are evaluating a structured software-maintenance state.",
            f"Return only one exact opaque label from: {', '.join(labels)}",
            "Do not explain your answer. Output one label only.",
            "",
            "Structured input surface:",
            _row_text(row),
        ]
    )


def ollama_generate(prompt: str, *, model: str = MODEL, seed: int = 0, temperature: float = 0.0) -> str:
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"seed": seed, "temperature": temperature},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def normalize_label(raw_output: str) -> str:
    if not raw_output:
        return ""
    return raw_output.splitlines()[0].strip()


def main() -> None:
    manifest_rows = [row for row in load_jsonl(MANIFEST) if row.get("split") == "strict_eval"]
    manifest_rows.sort(key=lambda row: str(row["row_id"]))
    frontier_100m = load_json(POLICY_100M)
    hundred_map = {row["row_id"]: row for row in frontier_100m["row_cards"]}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_row = []
    correct = 0
    lang_totals: dict[str, int] = defaultdict(int)
    lang_correct: dict[str, int] = defaultdict(int)
    for row in manifest_rows:
        row_id = str(row["row_id"])
        prompt = build_prompt(row)
        raw = ollama_generate(prompt)
        pred = normalize_label(raw)
        target = str(row["decoder_text"])
        is_correct = pred == target
        language = str(row.get("language_family") or "unknown")
        if is_correct:
            correct += 1
            lang_correct[language] += 1
        lang_totals[language] += 1
        per_row.append(
            {
                "row_id": row_id,
                "language_family": language,
                "perspective": perspective(row),
                "prompt": prompt,
                "target": target,
                "gemma_raw_output": raw,
                "gemma_pred": pred,
                "gemma_correct": is_correct,
                "hundred_m_pred": hundred_map[row_id]["pred"],
                "hundred_m_correct": hundred_map[row_id]["correct"],
            }
        )

    ROWS_PATH.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in per_row), encoding="utf-8")

    per_language = {}
    hundred_lang: dict[str, list[bool]] = defaultdict(list)
    gemma_lang: dict[str, list[bool]] = defaultdict(list)
    for row in per_row:
        language = row["language_family"]
        hundred_lang[language].append(bool(row["hundred_m_correct"]))
        gemma_lang[language].append(bool(row["gemma_correct"]))
    for language in sorted(lang_totals):
        h_acc = sum(hundred_lang[language]) / len(hundred_lang[language])
        g_acc = sum(gemma_lang[language]) / len(gemma_lang[language])
        if h_acc > g_acc:
            verdict = "100m_better"
        elif h_acc < g_acc:
            verdict = "gemma_better"
        else:
            verdict = "tie"
        per_language[language] = {
            "rows": lang_totals[language],
            "hundred_m_accuracy": h_acc,
            "gemma_accuracy": g_acc,
            "delta_hundred_m_minus_gemma": h_acc - g_acc,
            "verdict": verdict,
        }

    hundred_correct = frontier_100m["correct"]
    gemma_accuracy = correct / len(per_row)
    hundred_accuracy = frontier_100m["accuracy"]
    summary = {
        "stage_name": "stage10406_gemma_same_frontier_comparison",
        "model": MODEL,
        "rows": len(per_row),
        "prompt_surface_hash": prompt_surface_hash(manifest_rows),
        "hundred_m_policy": frontier_100m.get("policy"),
        "hundred_m_accuracy": hundred_accuracy,
        "gemma_accuracy": gemma_accuracy,
        "delta_hundred_m_minus_gemma": hundred_accuracy - gemma_accuracy,
        "hundred_m_correct": hundred_correct,
        "gemma_correct": correct,
        "per_language": per_language,
        "rows_path": str(ROWS_PATH.relative_to(ROOT)),
        "policy_artifact": str(POLICY_100M.relative_to(ROOT)),
        "claim_boundary": [
            "Same admitted 47-row frontier for both models.",
            "100M uses policy-level scorer python_verifier_drop_extension_v1.",
            "Gemma is evaluated by direct opaque-label generation on the same row surface.",
            "This is still a frontier comparison, not yet a disjoint-root promotable benchmark win.",
        ],
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(SUMMARY_PATH)


if __name__ == "__main__":
    main()
