#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9640
NAME = "stage9640_per_head_boundary_prefix_observe_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9639_counternegative_upsample_probe_failure_audit.json"
BASE_MANIFEST = ROOT / "runs/local/artifacts/stage9637_counternegative_upsample_observe_manifest/counternegative_upsample_observe_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "per_head_boundary_prefix_observe_manifest.jsonl"
RUN_DIR = OUT_DIR / "episode_step_contract"
AUDIT = OUT_DIR / "per_head_boundary_prefix_observe_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PER_HEAD_BOUNDARY_PREFIX_OBSERVE_MANIFEST_STAGE9640.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")

LOSS_MASK = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "episode_repair_outcome_ce": False,
    "episode_failure_type_ce": False,
    "episode_boundary_match_ce": True,
    "episode_target_prefix_match_ce": True,
    "episode_step_value_mse": False,
}
FORBIDDEN_ENCODER_MARKERS = [
    "target_prefix_match=",
    "boundary_next_token_match=",
    "prefix_start_match=",
    "stopped_on_eos=",
    "repair_outcome=",
    "failure_type=",
    "reward=",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def transition(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("episode_transition") if isinstance(row.get("episode_transition"), dict) else {}


def obs(row: dict[str, Any]) -> dict[str, Any]:
    tr = transition(row)
    return tr.get("observation_t") if isinstance(tr.get("observation_t"), dict) else {}


def state(row: dict[str, Any]) -> dict[str, Any]:
    tr = transition(row)
    return tr.get("state_t") if isinstance(tr.get("state_t"), dict) else {}


def text_len_bucket(text: str) -> str:
    n = len(text)
    return "short" if n < 60 else ("medium" if n < 100 else "long")


def prefix_len_bucket(prefix: str) -> str:
    return "short" if len(prefix.split()) <= 5 else "long"


def guard_bucket(count: int) -> str:
    return "zero" if count == 0 else ("one" if count == 1 else "many")


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in load_jsonl(BASE_MANIFEST):
        clone = json.loads(json.dumps(row))
        clone["row_id"] = f"stage9640_{row.get('row_id')}"
        clone["source_stage9637_row_id"] = row.get("row_id")
        clone["objective_family"] = "per_head_boundary_prefix_observe"
        clone["loss_mask"] = dict(LOSS_MASK)
        clone["authority"] = dict(AUTHORITY_CLOSED)
        rows.append(clone)
    return rows


def label(row: dict[str, Any], target: str) -> str:
    if target == "boundary_match":
        return str(obs(row).get("boundary_next_token_match"))
    if target == "target_prefix_match":
        return str(obs(row).get("target_prefix_match"))
    raise ValueError(target)


def feature(row: dict[str, Any], name: str) -> str:
    st = state(row)
    ob = obs(row)
    if name == "source_stage":
        return str(st.get("source_stage"))
    if name == "guard_event_count_bucket":
        return guard_bucket(int(st.get("guard_event_count") or 0))
    if name == "generated_len_bucket":
        return text_len_bucket(str(ob.get("generated_text") or ""))
    if name == "prefix_token_count_bucket":
        return prefix_len_bucket(str(st.get("generation_prefix_text") or ""))
    if name == "boundary_token_pair_visible":
        text = str(row.get("encoder_text") or "")
        expected = ""
        got = ""
        for line in text.splitlines():
            if line.startswith("boundary_expected_token_text="):
                expected = line.split("=", 1)[1].strip()
            elif line.startswith("boundary_generated_token_text="):
                got = line.split("=", 1)[1].strip()
        return "same" if expected and expected == got else "different"
    return ""


def baseline_exact(rows: list[dict[str, Any]], feat: str, tgt: str) -> float:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        table[feature(row, feat)][label(row, tgt)] += 1
    mapping = {key: counts.most_common(1)[0][0] for key, counts in table.items() if counts}
    return sum(1 for row in rows if mapping.get(feature(row, feat)) == label(row, tgt)) / len(rows) if rows else 0.0


def contract_command() -> list[str]:
    return [
        "env",
        f"TMPDIR={TMPDIR}",
        f"TEMP={TMPDIR}",
        f"TMP={TMPDIR}",
        "conda",
        "run",
        "-n",
        "trellis",
        "python",
        str(TRAINER),
        "--repo-root",
        str(ROOT),
        "--manifest",
        str(MANIFEST),
        "--mode",
        "episode_step_structured_probe",
        "--probe-scale",
        "target_100m",
        "--implementation",
        "transformer",
        "--model-config",
        str(MODEL_CONFIG),
        "--tokenizer-json",
        str(TOKENIZER_JSON),
        "--tokenizer-config",
        str(TOKENIZER_CONFIG),
        "--tokenizer-hashlock",
        str(TOKENIZER_HASHLOCK),
        "--max-train-rows",
        "32",
        "--max-eval-rows",
        "32",
        "--max-strict-rows",
        "32",
        "--max-steps",
        "0",
        "--batch-size",
        "2",
        "--learning-rate",
        "2e-4",
        "--max-encoder-tokens",
        "512",
        "--max-decoder-tokens",
        "8",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "1.0",
        "--denoise-weight",
        "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
        "--skip-final-model-save",
        "1",
        "--output-dir",
        str(RUN_DIR),
        "--run-id",
        "stage9640_per_head_boundary_prefix_observe_contract",
        "--contract-only",
    ]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    rows = build_rows()
    write_jsonl(MANIFEST, rows)

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9639_not_passed")
    if not rows:
        failures.append("empty_manifest")

    split_counts = {split: sum(1 for row in rows if row.get("split") == split) for split in ["train", "eval", "strict_eval"]}
    if max(split_counts.values() or [0]) - min(split_counts.values() or [0]) > 1:
        failures.append("split_counts_unbalanced")

    forbidden = []
    for row in rows:
        text = str(row.get("encoder_text") or "")
        hits = [marker for marker in FORBIDDEN_ENCODER_MARKERS if marker in text]
        if hits:
            forbidden.append({"row_id": row.get("row_id"), "hits": hits})
    if forbidden:
        failures.append("forbidden_encoder_label_markers_present")

    targets = ["boundary_match", "target_prefix_match"]
    features = [
        "source_stage",
        "guard_event_count_bucket",
        "generated_len_bucket",
        "prefix_token_count_bucket",
        "boundary_token_pair_visible",
    ]
    baselines = {f"{feat}->{tgt}": baseline_exact(rows, feat, tgt) for feat in features for tgt in targets}
    strongest = max(baselines.values()) if baselines else 0.0
    strongest_key = max(baselines, key=baselines.get) if baselines else None
    # The expected/generated boundary-token pair is real visible evidence for these heads.
    # It is audited separately so it does not hide a metadata shortcut.
    non_boundary_pair_baselines = {
        key: value for key, value in baselines.items() if not key.startswith("boundary_token_pair_visible->")
    }
    strongest_non_pair = max(non_boundary_pair_baselines.values()) if non_boundary_pair_baselines else 0.0
    if strongest_non_pair >= 0.75:
        failures.append("non_boundary_pair_single_feature_baseline_too_high")

    label_counts = {target: dict(Counter(label(row, target) for row in rows)) for target in targets}

    run = subprocess.run(contract_command(), cwd=ROOT, text=True, capture_output=True, check=False) if not failures else None
    if run is not None and run.returncode != 0:
        failures.append("contract_command_failed")
    card = load_json(RUN_DIR / "probe_contract_audit.json")
    if not card and not failures:
        failures.append("missing_probe_contract_audit")
    elif card and card.get("passed") is not True:
        failures.append("probe_contract_not_passed")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "base_manifest": str(BASE_MANIFEST.relative_to(ROOT)),
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "rows": len(rows),
        "split_counts": split_counts,
        "forbidden_encoder_label_marker_rows": len(forbidden),
        "forbidden_encoder_label_marker_examples": forbidden[:20],
        "single_feature_baselines": baselines,
        "strongest_single_feature_baseline": strongest,
        "strongest_single_feature_baseline_key": strongest_key,
        "strongest_non_boundary_pair_single_feature_baseline": strongest_non_pair,
        "label_counts": label_counts,
        "enabled_losses": ["episode_boundary_match_ce", "episode_target_prefix_match_ce"],
        "disabled_losses": [
            "decoder_ce",
            "denoise_ce",
            "runtime_reward",
            "episode_repair_outcome_ce",
            "episode_failure_type_ce",
            "episode_step_value_mse",
        ],
        "contract_passed": card.get("passed"),
        "loss_counts": card.get("loss_counts"),
        "model_execution_attempted": card.get("model_execution_attempted"),
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "If Stage9640 passes, run Stage9641 tiny target-100M episode-step probe over only "
        "episode_boundary_match and episode_target_prefix_match; do not recombine repair/value heads yet."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "run_dir": str(RUN_DIR.relative_to(ROOT)),
        },
        "decision": (
            "Per-head boundary/prefix observe manifest passed shortcut and contract preflight; no model execution occurred."
            if audit["passed"]
            else "Per-head boundary/prefix observe manifest failed; do not execute."
        ),
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9640 Per-Head Boundary Prefix Observe Manifest",
                "",
                f"Passed: `{audit['passed']}`",
                f"Rows: `{audit['rows']}`",
                f"Splits: `{split_counts}`",
                f"Enabled losses: `{audit['enabled_losses']}`",
                f"Disabled losses: `{audit['disabled_losses']}`",
                f"Strongest non-boundary-pair single-feature baseline: `{strongest_non_pair}`",
                f"Strongest overall single-feature baseline: `{strongest}` via `{strongest_key}`",
                "",
                "The boundary token pair baseline is tracked as real visible evidence, not a metadata shortcut.",
                "",
                "Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "passed": audit["passed"],
                "failures": failures,
                "rows": len(rows),
                "strongest_non_boundary_pair_single_feature_baseline": strongest_non_pair,
                "next_best_step": next_step,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
