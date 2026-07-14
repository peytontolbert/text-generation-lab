#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11567
NAME = "stage11567_balanced_web_non_evidence_support_package"
OUT = ART / NAME
SUMMARY = OUT / "balanced_web_non_evidence_support_package.json"
MANIFEST = OUT / "balanced_web_non_evidence_support_manifest.jsonl"
TRAIN_ROWS = OUT / "balanced_web_non_evidence_train_rows.jsonl"
REJECTED = OUT / "balanced_web_non_evidence_rejected_rows.jsonl"
COMMAND = OUT / "balanced_web_non_evidence_probe_command.json"

CANDIDATES = ART / "stage11566_web_non_evidence_support_supply_inventory/web_non_evidence_support_candidates.jsonl"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
INIT_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
WEB_HELDOUT = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
PROBE = ART / "stage11567_balanced_web_non_evidence_support_probe/bounded_decoder_probe"
RUNTIME_OUT = ART / "stage11567_balanced_web_non_evidence_support_probe/runtime_model"

EXCLUDE_REPOS = {"unknown", "code_assist"}
PREFERRED_SOURCE_HINTS = ["stage11550", "stage11523", "stage11375", "stage11394", "stage11364", "stage11388", "stage11347", "stage11354", "stage11535", "stage11537", "stage11545"]
TASK_CAP = 18
REPO_ROOT_CAP = 8


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True)+"\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True)+"\n" for row in rows), encoding="utf-8")


def normalize_row(row: dict[str, Any], split: str | None = None) -> dict[str, Any]:
    mined_root_id = row.get("stage11566_root_id")
    mined_task_type = row.get("stage11566_task_type")
    mined_repo_family = row.get("stage11566_repo_family")
    out = dict(row)
    out.pop("stage11566_source_path", None)
    out.pop("stage11566_root_id", None)
    out.pop("stage11566_task_type", None)
    out.pop("stage11566_repo_family", None)
    if mined_root_id and not out.get("root_id"):
        out["root_id"] = mined_root_id
    if mined_task_type and not out.get("task_type"):
        out["task_type"] = mined_task_type
    if mined_repo_family and not out.get("repo_family"):
        out["repo_family"] = "openhands" if mined_repo_family == "openhands_openhands_frontend" else mined_repo_family
    out["stage11567_mined_root_id"] = mined_root_id
    out["stage11567_mined_task_type"] = mined_task_type
    out["stage11567_mined_repo_family"] = mined_repo_family
    if split is not None:
        out["split"] = split
    out.setdefault("prompt_text", out.get("input_text") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    if not isinstance(out.get("loss_mask"), dict):
        out["loss_mask"] = {"decoder_ce": True}
    out.setdefault("expected_enabled_loss", "decoder_ce")
    src = dict(out.get("standalone_projection_source") or {})
    src.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = src
    if "target" not in out or not isinstance(out.get("target"), dict):
        out["target"] = {"decoder_text": out.get("decoder_text"), "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text")}
    ac = dict(out.get("anti_cheat") or {})
    ac.update({"stage11567_balanced_web_support": True, "train_support_only": True, "not_strict_eval_eligible": True})
    out["anti_cheat"] = ac
    return out


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("stage11566_root_id") or row.get("root_id") or row.get("source_bundle_id") or str(row.get("row_id") or "").split("::")[0])


def task(row: dict[str, Any]) -> str:
    return str(row.get("stage11566_task_type") or row.get("task_type") or "")


def repo(row: dict[str, Any]) -> str:
    val = str(row.get("stage11566_repo_family") or row.get("repo_family") or "")
    if val == "openhands_openhands_frontend":
        return "openhands"
    return val


def source_score(row: dict[str, Any]) -> tuple[int, int, str]:
    path = str(row.get("stage11566_source_path") or "")
    hint_score = max((len(PREFERRED_SOURCE_HINTS)-i for i,h in enumerate(PREFERRED_SOURCE_HINTS) if h in path), default=0)
    nums = [int(x) for x in re.findall(r"stage(\d+)", path)]
    stage_num = max(nums) if nums else 0
    return (hint_score, stage_num, path)


def root_ids(rows: list[dict[str, Any]]) -> set[str]:
    out=set()
    for row in rows:
        rid=row.get("root_id") or row.get("source_bundle_id")
        if rid:
            out.add(str(rid)); continue
        parts=str(row.get("row_id") or "").split("::")
        out.add("::".join(parts[:2]) if len(parts)>=2 else str(row.get("row_id") or ""))
    return out


def main() -> None:
    candidates = load_jsonl(CANDIDATES)
    rejected=[]
    grouped: dict[tuple[str,str], list[dict[str,Any]]] = defaultdict(list)
    for row in candidates:
        r=repo(row)
        if r in EXCLUDE_REPOS:
            rejected.append({"row_id": row.get("row_id"), "reason": "excluded_repo_family", "repo_family": r, "root_id": root_id(row), "task_type": task(row)})
            continue
        grouped[(root_id(row), task(row))].append(row)
    deduped=[]
    for key, rows in grouped.items():
        rows=sorted(rows, key=source_score, reverse=True)
        item=dict(rows[0])
        item["stage11567_dedupe_key"] = {"root_id": key[0], "task_type": key[1]}
        item["stage11567_source_candidates_collapsed"] = len(rows)
        deduped.append(item)
    # Cap repo roots first, then cap tasks to keep a balanced compact diagnostic package.
    roots_by_repo: dict[str, set[str]] = defaultdict(set)
    selected=[]
    for row in sorted(deduped, key=lambda r: (repo(r), root_id(r), task(r))):
        r=repo(row); rid=root_id(row)
        if len(roots_by_repo[r]) >= REPO_ROOT_CAP and rid not in roots_by_repo[r]:
            rejected.append({"row_id": row.get("row_id"), "reason": "repo_root_cap", "repo_family": r, "root_id": rid, "task_type": task(row)})
            continue
        roots_by_repo[r].add(rid)
        selected.append(row)
    task_counts=Counter()
    train=[]
    for row in sorted(selected, key=lambda r: (task_counts[task(r)], task(r), repo(r), root_id(r))):
        t=task(row)
        if task_counts[t] >= TASK_CAP:
            rejected.append({"row_id": row.get("row_id"), "reason": "task_cap", "repo_family": repo(row), "root_id": root_id(row), "task_type": t})
            continue
        task_counts[t]+=1
        train.append(normalize_row(row, "train"))
    validation=[normalize_row(row,"eval") for row in load_jsonl(FILTERED_VALIDATION)]
    strict=[normalize_row(row,"strict_eval") for row in load_jsonl(FILTERED_STRICT)]
    heldout=load_jsonl(WEB_HELDOUT)
    train_roots=root_ids(train)
    overlaps={
        "train_vs_validation": sorted(train_roots & root_ids(validation)),
        "train_vs_strict": sorted(train_roots & root_ids(strict)),
        "train_vs_web_heldout": sorted(train_roots & root_ids(heldout)),
    }
    manifest=train+validation+strict
    command=[
        "env","CUDA_VISIBLE_DEVICES=2","NVIDIA_VISIBLE_DEVICES=2","AGENTKERNEL_EVAL_DEVICE=cuda:0","PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True","TMPDIR=/data/tmp","TEMP=/data/tmp","TMP=/data/tmp",
        "conda","run","-n","trellis","python",str(ROOT/"legacy_src/scripts/train_agentkernel_lite_encdec.py"),
        "--repo-root",str(ROOT),"--manifest",str(MANIFEST),"--mode","bounded_decoder_ce_probe","--probe-scale","target_100m","--implementation","transformer",
        "--model-config",str(ROOT/"configs/model/agentkernel_100m_seq2seq_recovered_target.json"),"--tokenizer-json",str(ROOT/"configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"),"--tokenizer-config",str(ROOT/"configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"),"--tokenizer-hashlock",str(ROOT/"configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"),
        "--execution-authorized-for-recovery-probe","--max-train-rows",str(len(train)),"--max-eval-rows",str(len(validation)),"--max-strict-rows",str(len(strict)),"--max-steps","128","--batch-size","4","--learning-rate","6e-7","--max-encoder-tokens","768","--max-decoder-tokens","16","--decoder-ce-weight","0.04","--bounded-choice-aux-weight","3.0","--bounded-choice-aux-source","encoder_option_retrieval_evidence_judgment_head","--bounded-decoder-train-sampler","cyclic","--structured-aux-weight","0.0","--denoise-weight","0.0","--eos-loss-weight","4.0","--enable-generation-audit","--max-generation-rows","8","--max-generation-tokens","16","--require-loss-mask-enforcement-audit","--allow-runtime-model-save-for-harness","--runtime-model-save-dir",str(RUNTIME_OUT),"--initialize-from-runtime-model",str(INIT_RUNTIME),"--preservation-reference-runtime-model",str(INIT_RUNTIME),"--bounded-choice-contrast-weight","0.0","--bounded-choice-contrast-margin","0.05","--preservation-kl-weight","4.0","--no-final-checkpoint-export","--output-dir",str(PROBE)
    ]
    gates={
        "train_rows_present": len(train)>=40,
        "train_roots_present": len(train_roots)>=12,
        "repo_families_present": len({repo(r) for r in train})>=5,
        "contains_openhands": any(repo(r)=="openhands" for r in train),
        "contains_non_openhands": any(repo(r)!="openhands" for r in train),
        "no_root_overlap": all(not vals for vals in overlaps.values()),
        "strict_and_validation_present": len(validation)>0 and len(strict)>0,
    }
    summary={
        "stage":STAGE,"stage_name":NAME,"created_at_utc":now(),"passed":all(gates.values()),"decision":"balanced_web_non_evidence_support_probe_ready" if all(gates.values()) else "balanced_web_non_evidence_support_probe_blocked",
        "metrics":{
            "input_candidate_rows":len(candidates),"deduped_root_task_rows":len(deduped),"train_rows":len(train),"train_roots":len(train_roots),"train_task_counts":dict(Counter(task(r) for r in train)),"train_repo_counts":dict(Counter(repo(r) for r in train)),"train_root_counts_by_repo":{k:len(v) for k,v in roots_by_repo.items()},"rejected_rows":len(rejected),"rejection_counts":dict(Counter(r["reason"] for r in rejected)),"root_overlaps":overlaps,"validation_rows":len(validation),"strict_rows":len(strict)
        },
        "gates":gates,"command":command,
        "claim_boundary":["Diagnostic support package only.","Rows are deduplicated by root/task and root-disjoint from Web heldout plus protected canaries.","Promotion requires postrun audit against Stage11507 residual/strict gates and same-manifest Gemma Web baseline."],
        "source_artifacts":{"candidates":rel(CANDIDATES),"filtered_validation":rel(FILTERED_VALIDATION),"filtered_strict":rel(FILTERED_STRICT),"web_heldout":rel(WEB_HELDOUT),"init_runtime":rel(INIT_RUNTIME)},
        "outputs":{"train_rows":rel(TRAIN_ROWS),"manifest":rel(MANIFEST),"rejected":rel(REJECTED),"command":rel(COMMAND),"probe_dir":rel(PROBE),"runtime_model":rel(RUNTIME_OUT),"summary":rel(SUMMARY)}
    }
    OUT.mkdir(parents=True,exist_ok=True)
    write_jsonl(TRAIN_ROWS,train); write_jsonl(MANIFEST,manifest); write_jsonl(REJECTED,rejected); write_json(COMMAND,{"command":command}); write_json(SUMMARY,summary)
    SUMMARIES.mkdir(parents=True,exist_ok=True); shutil.copyfile(SUMMARY,SUMMARIES/f"{NAME}.json")
    print(json.dumps({"decision":summary["decision"],"metrics":summary["metrics"],"gates":gates},indent=2,sort_keys=True))

if __name__ == "__main__":
    main()
