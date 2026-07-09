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
STAGE = 9634
NAME = "stage9634_counterbalanced_observe_continuation_manifest"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9633_non_generative_continuation_shortcut_audit.json"
BASE_MANIFEST = ROOT / "runs/local/artifacts/stage9632_non_generative_repetition_eos_continuation_preflight/non_generative_repetition_eos_continuation_manifest.jsonl"
BASELINE_SAMPLES = ROOT / "runs/local/artifacts/stage9623_tri_phase_reconnect_tiny_probe/tri_phase_probe/phase3_full_residual_denoise_probe/sample_generation_audit.json"
GUARDED_SAMPLES = ROOT / "runs/local/artifacts/stage9630_tri_phase_repetition_guard_tiny_probe/tri_phase_probe/phase3_full_residual_denoise_probe/sample_generation_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "counterbalanced_observe_continuation_manifest.jsonl"
RUN_DIR = OUT_DIR / "episode_step_contract"
AUDIT = OUT_DIR / "counterbalanced_observe_continuation_manifest_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COUNTERBALANCED_OBSERVE_CONTINUATION_MANIFEST_STAGE9634.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path("/data/tmp")
LOSS_MASK = {
    "decoder_ce": False, "denoise_ce": False, "runtime_reward": False,
    "episode_repair_outcome_ce": True, "episode_failure_type_ce": True,
    "episode_boundary_match_ce": True, "episode_target_prefix_match_ce": True,
    "episode_step_value_mse": True,
}
FORBIDDEN_ENCODER_MARKERS = ["target_prefix_match=", "boundary_next_token_match=", "prefix_start_match=", "stopped_on_eos=", "repair_outcome=", "failure_type=", "reward="]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def split_for(index: int) -> str:
    return ["train", "eval", "strict_eval"][index % 3]


def positive_rows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    samples = []
    for source_name, path in [("stage9623_baseline", BASELINE_SAMPLES), ("stage9630_guarded", GUARDED_SAMPLES)]:
        for sample in load_json(path).get("samples") or []:
            if not sample.get("target_prefix_match"):
                samples.append((source_name, sample))
    for idx, (source_name, sample) in enumerate(samples[:12]):
        target = str(sample.get("target_text") or "").strip()
        if not target:
            continue
        boundary = sample.get("boundary_next_token") if isinstance(sample.get("boundary_next_token"), dict) else {}
        row = {
            "row_id": f"stage9634_counterpositive_{idx:03d}",
            "source_sample_row_id": sample.get("row_id"),
            "split": split_for(idx),
            "language_family": "mixed",
            "transition_schema": "episode_step_suffix_transition_v1",
            "objective_family": "counterbalanced_observe_continuation",
            "encoder_text": "\n".join([
                "episode_step_suffix_transition_v1",
                f"source={source_name}",
                f"generated_text={target}",
                f"generation_prefix_text={sample.get('generation_prefix_text') or ''}",
                f"boundary_expected_token_text={boundary.get('expected_token_text') or ''}",
                f"boundary_generated_token_text={boundary.get('expected_token_text') or ''}",
                f"generated_char_len={len(target)}",
                f"guard_event_count={int(sample.get('generation_repetition_guard_event_count') or 0)}",
                "target_text_hidden=true",
                "match_labels_hidden=true",
            ]),
            "episode_transition": {
                "state_t": {"source_stage": source_name, "target_visible": False, "clean_target_hidden_from_model_input": True, "generation_prefix_text": sample.get("generation_prefix_text"), "guard_event_count": int(sample.get("generation_repetition_guard_event_count") or 0)},
                "action_t": {"action": "OBSERVE_GENERATION_AND_SELECT_CONTINUATION_REPAIR", "target_surface": sample.get("surface") or "suffix_continuation"},
                "observation_t": {"generated_text": target, "target_prefix_match": True, "boundary_next_token_match": True, "boundary_expected_rank": 1, "degenerate_repetition": False, "short_or_junk": False, "stopped_on_eos": True, "residual_reasons": []},
                "reward_or_verifier": {"verifier_source": f"{source_name}_counterpositive", "step_passed": True, "reward": 1.0, "failure_type": "none"},
                "state_t_plus_1": {"repair_outcome": "verified_continue"},
            },
            "loss_mask": dict(LOSS_MASK),
            "authority": dict(AUTHORITY_CLOSED),
        }
        out.append(row)
    return out


def counternegative_rows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    samples = []
    for source_name, path in [("stage9623_baseline", BASELINE_SAMPLES), ("stage9630_guarded", GUARDED_SAMPLES)]:
        for sample in load_json(path).get("samples") or []:
            samples.append((source_name, sample))
    for idx, (source_name, sample) in enumerate(samples[:12]):
        prefix = str(sample.get("generation_prefix_text") or "Return the requested value")
        boundary = sample.get("boundary_next_token") if isinstance(sample.get("boundary_next_token"), dict) else {}
        expected = str(boundary.get("expected_token_text") or "expected")
        wrong = "wrong" if expected.strip().lower() != "wrong" else "mismatch"
        generated = f"{prefix} {wrong} continuation"
        row = {
            "row_id": f"stage9634_counternegative_{idx:03d}",
            "source_sample_row_id": sample.get("row_id"),
            "split": split_for(idx),
            "language_family": "mixed",
            "transition_schema": "episode_step_suffix_transition_v1",
            "objective_family": "counterbalanced_observe_continuation",
            "encoder_text": "\n".join([
                "episode_step_suffix_transition_v1",
                f"source={source_name}",
                f"generated_text={generated}",
                f"generation_prefix_text={prefix}",
                f"boundary_expected_token_text={expected}",
                f"boundary_generated_token_text={wrong}",
                f"generated_char_len={len(generated)}",
                f"guard_event_count={int(sample.get('generation_repetition_guard_event_count') or 0)}",
                "target_text_hidden=true",
                "match_labels_hidden=true",
            ]),
            "episode_transition": {
                "state_t": {"source_stage": source_name, "target_visible": False, "clean_target_hidden_from_model_input": True, "generation_prefix_text": prefix, "guard_event_count": int(sample.get("generation_repetition_guard_event_count") or 0)},
                "action_t": {"action": "OBSERVE_GENERATION_AND_SELECT_CONTINUATION_REPAIR", "target_surface": sample.get("surface") or "suffix_continuation"},
                "observation_t": {"generated_text": generated, "target_prefix_match": False, "boundary_next_token_match": False, "boundary_expected_rank": 99, "degenerate_repetition": False, "short_or_junk": False, "stopped_on_eos": True, "residual_reasons": ["boundary_next_token_miss", "target_prefix_miss"]},
                "reward_or_verifier": {"verifier_source": f"{source_name}_counternegative", "step_passed": False, "reward": 0.0, "failure_type": "boundary_next_token_miss+target_prefix_miss"},
                "state_t_plus_1": {"repair_outcome": "repair_prefix_boundary"},
            },
            "loss_mask": dict(LOSS_MASK),
            "authority": dict(AUTHORITY_CLOSED),
        }
        out.append(row)
    return out


def label(row: dict[str, Any], target: str) -> str:
    tr = row["episode_transition"]
    if target == "repair_outcome": return str(tr["state_t_plus_1"].get("repair_outcome"))
    if target == "target_prefix_match": return str(tr["observation_t"].get("target_prefix_match"))
    if target == "boundary_match": return str(tr["observation_t"].get("boundary_next_token_match"))
    return str(tr["reward_or_verifier"].get("failure_type"))


def feature(row: dict[str, Any], name: str) -> str:
    tr = row["episode_transition"]; state=tr["state_t"]; obs=tr["observation_t"]
    if name == "source_stage": return str(state.get("source_stage"))
    if name == "guard_event_count_bucket":
        n=int(state.get("guard_event_count") or 0); return "zero" if n == 0 else ("one" if n == 1 else "many")
    if name == "generated_len_bucket":
        n=len(str(obs.get("generated_text") or "")); return "short" if n < 60 else ("medium" if n < 100 else "long")
    if name == "prefix_token_count_bucket":
        n=len(str(state.get("generation_prefix_text") or "").split()); return "short" if n <= 5 else "long"
    return ""


def baseline_exact(rows: list[dict[str, Any]], feat: str, tgt: str) -> float:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows: table[feature(row, feat)][label(row, tgt)] += 1
    mapping={k:v.most_common(1)[0][0] for k,v in table.items() if v}
    return sum(1 for row in rows if mapping.get(feature(row, feat)) == label(row, tgt)) / len(rows) if rows else 0.0


def command() -> list[str]:
    return ["env", f"TMPDIR={TMPDIR}", f"TEMP={TMPDIR}", f"TMP={TMPDIR}", "conda", "run", "-n", "trellis", "python", str(TRAINER),
        "--repo-root", str(ROOT), "--manifest", str(MANIFEST), "--mode", "episode_step_structured_probe", "--probe-scale", "target_100m", "--implementation", "transformer",
        "--model-config", str(MODEL_CONFIG), "--tokenizer-json", str(TOKENIZER_JSON), "--tokenizer-config", str(TOKENIZER_CONFIG), "--tokenizer-hashlock", str(TOKENIZER_HASHLOCK),
        "--max-train-rows", "16", "--max-eval-rows", "16", "--max-strict-rows", "16", "--max-steps", "0", "--batch-size", "2", "--learning-rate", "2e-4",
        "--max-encoder-tokens", "512", "--max-decoder-tokens", "8", "--decoder-ce-weight", "0.0", "--structured-aux-weight", "1.0", "--denoise-weight", "0.0",
        "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--skip-final-model-save", "1",
        "--output-dir", str(RUN_DIR), "--run-id", "stage9634_counterbalanced_observe_continuation_contract", "--contract-only"]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows=[row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE,"stage_name": NAME,"passed": summary["passed"],"path": str(SUMMARY),"authority": dict(AUTHORITY_CLOSED),"next_best_step": summary["next_best_step"]})
    registry["rows"]=sorted(rows,key=lambda row:(int(row.get("stage",-1)),row.get("stage_name","")))
    registry["passed"]=bool(registry["rows"])
    registry["metrics"]={**(registry.get("metrics") or {}),"latest_stage":STAGE,"latest_stage_name":NAME,"latest_stage_next_best_step":summary["next_best_step"],"max_stage":STAGE,"registry_rows":len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source=load_json(SOURCE_SUMMARY)
    rows=load_jsonl(BASE_MANIFEST)+positive_rows()+counternegative_rows()
    for idx,row in enumerate(rows): row["split"] = split_for(idx)
    write_jsonl(MANIFEST, rows)
    failures=[]
    if source.get("passed") is not True: failures.append("stage9633_not_passed")
    split_counts={s:sum(1 for row in rows if row.get("split")==s) for s in ["train","eval","strict_eval"]}
    if split_counts != {"train":16,"eval":16,"strict_eval":16}: failures.append("split_counts_not_16_each")
    forbidden=[]
    for row in rows:
        text=str(row.get("encoder_text") or "")
        hits=[m for m in FORBIDDEN_ENCODER_MARKERS if m in text]
        if hits: forbidden.append({"row_id":row.get("row_id"),"hits":hits})
    if forbidden: failures.append("forbidden_encoder_label_markers_present")
    targets=["repair_outcome","failure_type","boundary_match","target_prefix_match"]
    features=["source_stage","guard_event_count_bucket","generated_len_bucket","prefix_token_count_bucket"]
    baselines={f"{feat}->{tgt}": baseline_exact(rows,feat,tgt) for feat in features for tgt in targets}
    strongest=max(baselines.values()) if baselines else 0.0
    strongest_key=max(baselines,key=baselines.get) if baselines else None
    if strongest >= 0.80: failures.append("single_feature_baseline_too_high")
    run=subprocess.run(command(),cwd=ROOT,text=True,capture_output=True,check=False) if not failures else None
    if run is not None and run.returncode != 0: failures.append("contract_command_failed")
    card=load_json(RUN_DIR / "probe_contract_audit.json")
    if not card: failures.append("missing_probe_contract_audit")
    elif card.get("passed") is not True: failures.append("probe_contract_not_passed")
    label_counts={t:dict(Counter(label(row,t) for row in rows)) for t in targets}
    audit={"passed":not failures,"failures":failures,"source_summary":str(SOURCE_SUMMARY.relative_to(ROOT)),"manifest":str(MANIFEST.relative_to(ROOT)),"rows":len(rows),"split_counts":split_counts,"counterpositive_rows":len(positive_rows()),"counternegative_rows":len(counternegative_rows()),"forbidden_encoder_label_marker_rows":len(forbidden),"single_feature_baselines":baselines,"strongest_single_feature_baseline":strongest,"strongest_single_feature_baseline_key":strongest_key,"label_counts":label_counts,"contract_passed":card.get("passed"),"loss_counts":card.get("loss_counts"),"model_execution_attempted":card.get("model_execution_attempted"),"authority":dict(AUTHORITY_CLOSED)}
    AUDIT.write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    next_step="If Stage9634 passes, run a tiny episode-step structured probe; if it fails, construct more same-feature/different-label counterpositives."
    summary={"stage":STAGE,"stage_name":NAME,"name":NAME,"passed":audit["passed"],"authority":dict(AUTHORITY_CLOSED),"metrics":{**dict(AUTHORITY_CLOSED),**audit},"artifacts":{"audit":str(AUDIT.relative_to(ROOT)),"doc":str(DOC.relative_to(ROOT)),"manifest":str(MANIFEST.relative_to(ROOT)),"run_dir":str(RUN_DIR.relative_to(ROOT))},"decision":"Counterbalanced observe-phase continuation manifest passed shortcut and contract preflight; no model execution occurred." if audit["passed"] else "Counterbalance manifest failed; do not execute.","next_best_step":next_step,"created_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
    SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9634 Counterbalanced Observe Continuation Manifest","",f"Passed: `{audit['passed']}`",f"Rows: `{audit['rows']}`",f"Splits: `{audit['split_counts']}`",f"Strongest single-feature baseline: `{strongest}` via `{strongest_key}`",f"Counterpositive rows: `{audit['counterpositive_rows']}`",f"Counternegative rows: `{audit['counternegative_rows']}`","","Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.","",f"Next: {next_step}",""]),encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage":STAGE,"passed":audit["passed"],"failures":failures,"strongest_single_feature_baseline":strongest,"next_best_step":next_step},indent=2,sort_keys=True))
    if failures: raise SystemExit(1)

if __name__ == "__main__": main()
