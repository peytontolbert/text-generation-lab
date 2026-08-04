#!/usr/bin/env python3
"""Build one fail-closed CPU causal episode from a pinned Unsloth replay."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, re, shlex, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12583_causal_episode_microfactory"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCE_REPO = Path("/arxiv/repositories/unsloth")
BEFORE = "420799b61ef35d6cfd87c4f4b02c98152fdf6599"
AFTER = "76a2b9edf160d68208dc30c02c6523bc6551f950"
TEST_PATHS = ("studio/backend/tests/test_llama_cpp_mtp_detection.py",)
PRODUCTION_PATHS = ("studio/backend/core/inference/llama_cpp.py", "studio/backend/models/inference.py")
EXPECTED_PATHS = (*PRODUCTION_PATHS, *TEST_PATHS,
    "studio/frontend/src/features/chat/chat-settings-sheet.tsx",
    "studio/frontend/src/features/chat/types/api.ts")
TEST_PATCH_SHA256 = "a543f9237788f1d81877227dfb14764e88fdd856626f9bf9e67b64170444e728"
PRODUCTION_PATCH_SHA256 = "383366d6021a227610afef0dc387a66b7637741d7044a85c40e54f37edc19351"
PYTHON = "/home/peyton/miniconda3/envs/ai/bin/python"
VERIFIER_TARGETS = ("tests/test_llama_cpp_mtp_detection.py", "tests/test_inference_model_validation.py")
TIMEOUT = 300
_GUARD_SPEC=importlib.util.spec_from_file_location("stage12583_common_source_lineage_guard",ROOT/"scripts/source_lineage_guard.py")
if _GUARD_SPEC is None or _GUARD_SPEC.loader is None: raise ImportError("common source_lineage_guard unavailable")
COMMON_GUARD=importlib.util.module_from_spec(_GUARD_SPEC)
sys.modules[_GUARD_SPEC.name]=COMMON_GUARD
_GUARD_SPEC.loader.exec_module(COMMON_GUARD)
CENTRAL_DENYLIST=ROOT/"configs/software_maintainer/future_eval_identity_denylist_v1.json"
HARNESS_REFERENCE_PATH="runs/local/artifacts/stage11511_selected_frontier_harness_payload/selected_frontier_harness_payload.json"
HARNESS_REFERENCE_SHA256="5b42aabe50e307d1d5ebfe7ffa156d0c0695fe837b28cc5aa8329aaa78d04bd9"
AUTHORITATIVE_SELECTED_ROWS={
 "runs/local/artifacts/stage11510_selected_frontier_same_manifest_gemma_comparison/matched_comparison_rows.jsonl":("afa0c8aec04e5e075b2439c19feb374a11f89dffd4ef2406a72de8cfdd9a7f31",23),
 "runs/local/artifacts/stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl":("6751f82dffb254ea70a23c3eac24586fba60615de80773091d3e7dc8eb13ec25",22),
 "runs/local/artifacts/stage11436_full_coverage_semantic_candidate_package/agentkernel_lite_encdec_strict_eval.jsonl":("36b0175949d33c3efaa86f45d17d41224769d6701fd481f9e73efd526a1ebac9",23),
 "runs/local/artifacts/stage11897_transition_record_projection_rows/transition_projection_rows.jsonl":("7ce8c030d429d948d3805e836d9e6522bcd0320252cfcb27b59475d8c1cb64bc",640),
 "runs/local/artifacts/stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl":("4fb89e5b3138cebb4a74911274b5fb653234c3a468fda527df2bbfa9646a41ce",10),
 "runs/local/artifacts/stage11740_verifier_grounded_source_heldout_successor_score/verifier_grounded_successor_rows.jsonl":("9aa58bc877ff381ee38c21604e72fd582375935323e2e4c8c3952bd480276da6",12),
}

PROJECTION_SCHEMA = "stage12583_selected_gate_train_admission_v1"
SELECTED_GATE_FILES = {
    "runs/local/artifacts/stage11511_selected_frontier_harness_payload/selected_frontier_harness_payload.json": "5b42aabe50e307d1d5ebfe7ffa156d0c0695fe837b28cc5aa8329aaa78d04bd9",
    "runs/local/artifacts/stage11510_selected_frontier_same_manifest_gemma_comparison/matched_comparison_rows.jsonl": "afa0c8aec04e5e075b2439c19feb374a11f89dffd4ef2406a72de8cfdd9a7f31",
    "runs/local/artifacts/stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl": "6751f82dffb254ea70a23c3eac24586fba60615de80773091d3e7dc8eb13ec25",
    "runs/local/artifacts/stage11436_full_coverage_semantic_candidate_package/agentkernel_lite_encdec_strict_eval.jsonl": "36b0175949d33c3efaa86f45d17d41224769d6701fd481f9e73efd526a1ebac9",
    "runs/local/artifacts/stage11897_transition_record_projection_rows/transition_projection_rows.jsonl": "7ce8c030d429d948d3805e836d9e6522bcd0320252cfcb27b59475d8c1cb64bc",
    "runs/local/artifacts/stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl": "4fb89e5b3138cebb4a74911274b5fb653234c3a468fda527df2bbfa9646a41ce",
    "runs/local/artifacts/stage11740_verifier_grounded_source_heldout_successor_score/verifier_grounded_successor_rows.jsonl": "9aa58bc877ff381ee38c21604e72fd582375935323e2e4c8c3952bd480276da6",
}



class GateError(RuntimeError): pass
def sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def stable(value: Any) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))

def run(argv: list[str], *, cwd: Path | None = None, env=None, timeout=TIMEOUT) -> dict[str, Any]:
    start = time.monotonic()
    try:
        p = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout, check=False)
        code, stdout, stderr, timed_out = p.returncode, p.stdout, p.stderr, False
    except subprocess.TimeoutExpired as e:
        code, stdout, stderr, timed_out = 124, e.stdout or b"", e.stderr or b"", True
    return {"argv": argv, "command": shlex.join(argv), "cwd": str(cwd) if cwd else None,
            "return_code": code, "timed_out": timed_out,
            "stdout": stdout.decode("utf-8", "replace")[-12000:],
            "stderr": stderr.decode("utf-8", "replace")[-12000:],
            "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
            "stdout_bytes": len(stdout), "stderr_bytes": len(stderr),
            "duration_seconds": round(time.monotonic() - start, 3)}

def git(repo: Path, *args: str, timeout=TIMEOUT) -> dict[str, Any]:
    return run(["git", "-C", str(repo), *args], timeout=timeout)
def require_ok(obs: dict[str, Any], blocker: str) -> None:
    if obs["return_code"] or obs["timed_out"]: raise GateError(blocker)
def git_stdout(repo: Path, *args: str) -> str:
    obs = git(repo, *args); require_ok(obs, "git_failed:" + " ".join(args)); return obs["stdout"].strip()
def patch_bytes(paths: tuple[str, ...]) -> bytes:
    p = subprocess.run(["git", "-C", str(SOURCE_REPO), "diff", "--binary", BEFORE, AFTER,
                        "--", *paths], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode or not p.stdout: raise GateError("partition_diff_regeneration_failed")
    return p.stdout

def env_for(worktree: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({"CUDA_VISIBLE_DEVICES": "", "PYTHONDONTWRITEBYTECODE": "1",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "WANDB_DISABLED": "true",
        "PIP_NO_INDEX": "1", "OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "",
        "PYTHONPATH": os.pathsep.join((str(worktree), str(worktree / "studio/backend")))})
    return env

def state(repo: Path) -> dict[str, Any]:
    head, tree = git_stdout(repo, "rev-parse", "HEAD"), git_stdout(repo, "rev-parse", "HEAD^{tree}")
    status_obs = git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    require_ok(status_obs, "git_status_failed")
    status = status_obs["stdout"].rstrip("\n")
    p = subprocess.run(["git", "-C", str(repo), "diff", "--binary"], stdout=subprocess.PIPE, check=False)
    if p.returncode: raise GateError("working_diff_capture_failed")
    paths = sorted(line[3:] for line in status.splitlines() if len(line) >= 4)
    return {"head": head, "head_tree": tree, "clean": not status, "status_porcelain": status,
            "changed_paths": paths, "working_diff_sha256": sha(p.stdout),
            "working_diff_bytes": len(p.stdout), "identity_sha256": stable([head, tree, status, sha(p.stdout)])}

def candidate_commitment() -> dict[str, Any]:
    actions = [
      {"action_id":"A","role":"inspect the before tree for the missing symbol and prepare a minimal production repair, then run the pinned verifier"},
      {"action_id":"B","role":"edit only the failing import site without adding the missing implementation, then run the pinned verifier","semantic_hard_negative":True},
      {"action_id":"C","role":"change validation behavior without resolving the missing symbol, then run the pinned verifier","semantic_hard_negative":True},
      {"action_id":"D","role":"set an environment override without changing production files, then run the pinned verifier","semantic_hard_negative":True},
      {"action_id":"E","role":"apply a broad unrelated source change, then run the pinned verifier","semantic_hard_negative":True},
      {"action_id":"F","role":"make no production change and rerun the pinned verifier"}]
    body = {"commitment_phase":"post_failure_pre_repair_outcome",
      "sealed_before_repair_outcome":True,"includes_prior_verifier_observation":True,
      "candidate_actions":actions,
      "semantic_hard_negative_count":sum(bool(x.get("semantic_hard_negative")) for x in actions),
      "candidate_provenance":{"basis":"before_tree_failure_and_test_setup_only",
        "successful_after_diff_read":False,"historical_nonleaky_provenance":False},
      "inputs":{"before":BEFORE,"test_patch_sha256":TEST_PATCH_SHA256,
                "verifier_targets":list(VERIFIER_TARGETS),
                "observed_failure_identity":"ImportError:_mla_mtp_auto_enabled"}}
    return {**body, "commitment_sha256": stable(body)}

def verifier_identity(cache:Path,worktree:Path)->dict[str,Any]:
    argv=[PYTHON,"-m","pytest","-q","-c","/dev/null","-o",f"cache_dir={cache}",*VERIFIER_TARGETS]
    env=env_for(worktree)
    selected_hashes={target:sha((worktree/"studio/backend"/target).read_bytes()) for target in VERIFIER_TARGETS}
    normalized={"python":PYTHON,"python_executable_sha256":sha(Path(PYTHON).read_bytes()),
      "argv":[*argv[:7],"cache_dir=<temp>",*argv[8:]],"cwd":"studio/backend","cpu_only":True,
      "environment":{"CUDA_VISIBLE_DEVICES":env["CUDA_VISIBLE_DEVICES"],
       "PYTHONDONTWRITEBYTECODE":env["PYTHONDONTWRITEBYTECODE"],"HF_HUB_OFFLINE":env["HF_HUB_OFFLINE"],
       "TRANSFORMERS_OFFLINE":env["TRANSFORMERS_OFFLINE"],"PIP_NO_INDEX":env["PIP_NO_INDEX"],
       "WANDB_DISABLED":env["WANDB_DISABLED"],"OPENAI_API_KEY":"<cleared>","ANTHROPIC_API_KEY":"<cleared>",
       "PYTHONPATH":"<worktree>:<worktree>/studio/backend"},"selected_test_content_sha256":selected_hashes}
    return {"argv":argv,"normalized":normalized,"digest":stable(normalized)}
def verify(repo: Path, identity: dict[str, Any]) -> dict[str, Any]:
    obs = run(identity["argv"], cwd=repo/"studio/backend", env=env_for(repo))
    obs["verifier_identity_digest"] = identity["digest"]; return obs
def apply_patch(repo: Path, path: Path, label: str) -> dict[str, Any]:
    check = git(repo, "apply", "--check", "--verbose", str(path)); require_ok(check, label+"_apply_check_failed")
    applied = git(repo, "apply", "--verbose", str(path)); require_ok(applied, label+"_apply_failed")
    text = (applied["stdout"]+applied["stderr"]).lower()
    if "offset" in text or "fuzz" in text: raise GateError(label+"_apply_not_exact")
    return {"check":check,"apply":applied,"zero_fuzz":True}
def exact_subset(repo: Path, paths: tuple[str,...], expected: bytes, blocker: str) -> None:
    p = subprocess.run(["git","-C",str(repo),"diff","--binary","--",*paths],stdout=subprocess.PIPE)
    if p.returncode or p.stdout != expected: raise GateError(blocker)

def selected_gate_evidence(root:Path=ROOT,
 files:dict[str,tuple[str,int]]|None=None)->dict[str,Any]:
    pinned=AUTHORITATIVE_SELECTED_ROWS if files is None else files
    denylist=COMMON_GUARD.load_future_eval_identity_denylist(CENTRAL_DENYLIST)
    checked=[];total=0
    for relative,(expected_digest,expected_count) in sorted(pinned.items()):
        path=root/relative
        if not path.is_file(): raise GateError("selected_gate_file_missing:"+relative)
        raw=path.read_bytes()
        if sha(raw)!=expected_digest: raise GateError("selected_gate_hash_mismatch:"+relative)
        rows=[]
        for line_number,line in enumerate(raw.decode("utf-8").splitlines(),1):
            if not line.strip(): continue
            try: row=json.loads(line)
            except json.JSONDecodeError as exc: raise GateError(f"selected_gate_malformed_json:{relative}:{line_number}") from exc
            if not isinstance(row,dict): raise GateError(f"selected_gate_malformed_row:{relative}:{line_number}")
            extraction=COMMON_GUARD.extract_future_eval_identities(row)
            if extraction.malformed_paths: raise GateError(f"selected_gate_malformed_identity:{relative}:{line_number}")
            if not extraction.has_identity: raise GateError(f"selected_gate_identityless:{relative}:{line_number}")
            denied={kind:sorted(values&denylist[kind]) for kind,values in extraction.identities.items()
                    if values&denylist[kind]}
            if denied: raise GateError(f"selected_gate_unsloth_overlap:{relative}:{line_number}:{denied}")
            rows.append(row)
        if len(rows)!=expected_count: raise GateError("selected_gate_row_count_mismatch:"+relative)
        total+=len(rows);checked.append({"path":relative,"sha256":expected_digest,"row_count":len(rows),
          "identityless_count":0,"malformed_count":0,"denied_identity_count":0})
    if files is None and total!=730: raise GateError("selected_gate_total_row_count_mismatch")
    harness=root/HARNESS_REFERENCE_PATH
    if files is None and (not harness.is_file() or sha(harness.read_bytes())!=HARNESS_REFERENCE_SHA256):
        raise GateError("harness_reference_missing_or_hash_mismatch")
    return {"selected_gates_clear":True,"common_guard_path":"scripts/source_lineage_guard.py",
      "central_denylist_path":str(CENTRAL_DENYLIST.relative_to(ROOT)),
      "central_denylist_sha256":sha(CENTRAL_DENYLIST.read_bytes()),
      "authoritative_row_file_count":len(checked),"total_rows_checked":total,
      "identityless_count":0,"malformed_count":0,"unsloth_identity_count":0,
      "checked_files":checked,
      "harness_reference":{"path":HARNESS_REFERENCE_PATH,"sha256":HARNESS_REFERENCE_SHA256,
       "authoritative":False} if files is None else None}

def lineage_evidence(out:Path|None=None,root:Path=ROOT,
 files:dict[str,tuple[str,int]]|None=None)->dict[str,Any]:
    selected=selected_gate_evidence(root,files)
    return {**selected,"central_trainer_denylist_enforced":True,
      "trainer_enforcement_entrypoint":"recovered_trainer.load_manifest(primary_and_phase_manifests)",
      "standalone_scripts_authoritative":False,"training_admission_allowed":False,
      "training_admission_blockers":["custom_projection_not_trainer_native"],
      "strict_eval":False,"source_heldout":False}


def validate_lineage_evidence_structure(lineage:dict[str,Any])->None:
    required={"selected_gates_clear","central_denylist_path","central_denylist_sha256",
      "central_trainer_denylist_enforced","trainer_enforcement_entrypoint",
      "training_admission_allowed","training_admission_blockers","strict_eval","source_heldout"}
    if not isinstance(lineage,dict) or not required.issubset(lineage):
        raise GateError("lineage_evidence_structure_invalid")
    if lineage["central_denylist_path"]!=str(CENTRAL_DENYLIST.relative_to(ROOT)):
        raise GateError("lineage_denylist_path_invalid")
    if lineage["central_denylist_sha256"]!=sha(CENTRAL_DENYLIST.read_bytes()):
        raise GateError("lineage_denylist_hash_invalid")
    if lineage["training_admission_allowed"] is not False:
        raise GateError("lineage_training_admission_must_be_false")
    if lineage["strict_eval"] is not False or lineage["source_heldout"] is not False:
        raise GateError("lineage_split_claim_invalid")


EXPECTED_EVENTS=["TEST_SETUP","VERIFIER_FAIL","CANDIDATE_COMMITMENT","CHOSEN_PRODUCTION_ACTION",
 "PRODUCTION_PATCH_APPLY","SAME_VERIFIER_PASS","STATE_UPDATE","CONTINUE"]
def validate_ordered_events(events:list[dict[str,Any]])->None:
    if events and events[-1].get("event")=="STOP":
        raise GateError("focused_verifier_cannot_justify_stop")
    if [x.get("event") for x in events]!=EXPECTED_EVENTS: raise GateError("causal_event_order_invalid")
    if events[1].get("observation")!="before" or events[5].get("observation")!="after":
        raise GateError("verifier_observation_order_invalid")
    if events[-1].get("decision")!="CONTINUE" or events[-1].get("next_action")!="RUN_BROADER_REGRESSION":
        raise GateError("focused_verifier_cannot_justify_stop")

def parse_passed_count(text:str)->int:
    matches=re.findall(r"(?:^|\s)(\d+) passed\b",text)
    return int(matches[-1]) if matches else 0

def replay(out:Path)->tuple[dict[str,Any]|None,dict[str,Any]]:
    diag={"status":"REJECTED","gates_passed":[]}; disposable=None
    try:
        lineage=lineage_evidence(out)
        validate_lineage_evidence_structure(lineage)
        if not SOURCE_REPO.is_dir(): raise GateError("source_repository_missing")
        if git_stdout(SOURCE_REPO,"rev-parse",f"{BEFORE}^{{commit}}")!=BEFORE: raise GateError("before_commit_identity_mismatch")
        if git_stdout(SOURCE_REPO,"rev-parse",f"{AFTER}^{{commit}}")!=AFTER: raise GateError("after_commit_identity_mismatch")
        require_ok(git(SOURCE_REPO,"merge-base","--is-ancestor",BEFORE,AFTER),"commit_pair_not_ordered")
        commit_paths=sorted(git_stdout(SOURCE_REPO,"diff","--name-only",BEFORE,AFTER).splitlines())
        if commit_paths!=sorted(EXPECTED_PATHS): raise GateError("commit_changed_path_set_mismatch")
        test_patch,prod_patch=patch_bytes(TEST_PATHS),patch_bytes(PRODUCTION_PATHS)
        if sha(test_patch)!=TEST_PATCH_SHA256: raise GateError("test_patch_digest_mismatch")
        if sha(prod_patch)!=PRODUCTION_PATCH_SHA256: raise GateError("production_patch_digest_mismatch")
        diag["gates_passed"].append("commit_identity_paths_patch_digests")
        partitions=out/"partitions"; partitions.mkdir(parents=True,exist_ok=True)
        test_file,prod_file=partitions/"test_setup.patch",partitions/"production_repair.patch"
        test_file.write_bytes(test_patch); prod_file.write_bytes(prod_patch)
        disposable=Path(tempfile.mkdtemp(prefix=STAGE+"-",dir="/data/tmp")); repo=disposable/"repo"; cache=disposable/"cache"
        require_ok(run(["git","clone","--no-hardlinks","--no-checkout",str(SOURCE_REPO),str(repo)],timeout=300),"disposable_clone_failed")
        require_ok(git(repo,"checkout","--detach",BEFORE),"baseline_checkout_failed")
        baseline=state(repo); tree=git_stdout(SOURCE_REPO,"rev-parse",f"{BEFORE}^{{tree}}")
        if baseline["head"]!=BEFORE or baseline["head_tree"]!=tree or not baseline["clean"]:
            raise GateError("baseline_identity_or_cleanliness_mismatch")
        diag["gates_passed"].append("exact_clean_baseline")
        test_application=apply_patch(repo,test_file,"test_setup"); test_setup_state=state(repo)
        if test_setup_state["changed_paths"]!=sorted(TEST_PATHS): raise GateError("test_setup_path_residue")
        exact_subset(repo,TEST_PATHS,test_patch,"test_setup_not_exact")
        identity=verifier_identity(cache,repo); before=verify(repo,identity); text=before["stdout"]+before["stderr"]
        if before["timed_out"] or before["return_code"]!=2: raise GateError("before_not_expected_return_2")
        if "ImportError" not in text or "_mla_mtp_auto_enabled" not in text: raise GateError("before_missing_relevant_import_error")
        before["failure_identity"]="ImportError:_mla_mtp_auto_enabled"; diag["gates_passed"].append("relevant_test_only_failure")
        state_before={**state(repo),"operational":{"phase":"repair_action_selection",
          "unresolved_task":"repair production implementation so the pinned verifier passes","verifier_status":"FAIL",
          "before_observation_identity":stable([before["return_code"],before["failure_identity"],before["verifier_identity_digest"]]),
          "failure_identity":before["failure_identity"]}}
        commitment=candidate_commitment(); write_json(out/"pre_outcome_commitment.json",commitment)
        chosen={"action_id":"A","role":commitment["candidate_actions"][0]["role"],"production_patch_sha256":PRODUCTION_PATCH_SHA256}
        prod_application=apply_patch(repo,prod_file,"production_repair")
        exact_subset(repo,PRODUCTION_PATHS,prod_patch,"production_repair_not_exact")
        after_identity=verifier_identity(cache,repo)
        if identity["digest"]!=after_identity["digest"]: raise GateError("verifier_identity_changed")
        after=verify(repo,after_identity); passed=parse_passed_count(after["stdout"]+after["stderr"])
        if after["timed_out"] or after["return_code"] or passed!=245: raise GateError("after_not_exact_245_pass")
        if before["verifier_identity_digest"]!=after["verifier_identity_digest"]: raise GateError("verifier_identity_changed")
        after["passed_count"]=passed; diag["gates_passed"].append("identical_verifier_fail_to_pass")
        final=state(repo); expected=sorted((*TEST_PATHS,*PRODUCTION_PATHS))
        if final["changed_paths"]!=expected: raise GateError("unrelated_final_residue")
        require_ok(git(repo,"diff","--check"),"final_diff_check_failed")
        combined_patch=patch_bytes((*PRODUCTION_PATHS,*TEST_PATHS))
        exact_subset(repo,(*PRODUCTION_PATHS,*TEST_PATHS),combined_patch,"post_verifier_combined_diff_mismatch")
        if final["working_diff_sha256"]!=sha(combined_patch): raise GateError("post_verifier_final_diff_hash_mismatch")
        state_after={**final,"operational":{"phase":"focused_repair_verified",
          "unresolved_task":"broader regression verification remains","verifier_status":"FOCUSED_PASS",
          "passed_count":245,"next_action":"RUN_BROADER_REGRESSION"}}
        diag["gates_passed"].append("exact_state_delta_no_residue")
        events=[{"order":1,"event":"TEST_SETUP","policy_action":False,"patch_sha256":TEST_PATCH_SHA256},
          {"order":2,"event":"VERIFIER_FAIL","observation":"before","failure_identity":before["failure_identity"]},
          {"order":3,"event":"CANDIDATE_COMMITMENT","commitment_sha256":commitment["commitment_sha256"]},
          {"order":4,"event":"CHOSEN_PRODUCTION_ACTION","action_id":"A"},
          {"order":5,"event":"PRODUCTION_PATCH_APPLY","patch_sha256":PRODUCTION_PATCH_SHA256},
          {"order":6,"event":"SAME_VERIFIER_PASS","observation":"after","passed_count":245},
          {"order":7,"event":"STATE_UPDATE","verifier_status":"FOCUSED_PASS"},
          {"order":8,"event":"CONTINUE","decision":"CONTINUE","next_action":"RUN_BROADER_REGRESSION"}]
        validate_ordered_events(events)
        episode={"episode_id":STAGE+"_"+PRODUCTION_PATCH_SHA256[:16],"support_scope":"train-support-only",
           "projection_schema":"stage12583_private_projection_candidate_v2","strict_eval":False,"source_heldout":False,
          "training_admission_allowed":False,
          "training_admission_blockers":["selected_gate_closure_incomplete","future_eval_denylist_not_enforced"],
          "lineage_evidence":lineage,
          "source":{"repository":str(SOURCE_REPO),"before":BEFORE,"after":AFTER,"ordered":True,"before_tree":tree},
          "path_partition":{"commit_changed_paths":commit_paths,"test_only_paths":list(TEST_PATHS),
            "production_only_paths":list(PRODUCTION_PATHS),
            "excluded_paths":sorted(set(commit_paths)-set(TEST_PATHS)-set(PRODUCTION_PATHS)),"overlap":[]},
          "ordered_events":events,"pre_outcome_commitment":commitment,"state_before":state_before,
          "chosen_action":chosen,"observations":{"before":before,"after":after},"state_after":state_after,
          "state_delta":{"baseline_identity_sha256":baseline["identity_sha256"],
            "state_before_identity_sha256":state_before["identity_sha256"],"state_after_identity_sha256":final["identity_sha256"],
            "actual_changed_paths":final["changed_paths"],"expected_changed_paths":expected,
            "production_changed_paths":list(PRODUCTION_PATHS),"no_unrelated_residue":True},
          "patch_trace":{"regenerated_from_commits":True,"test_patch_sha256":sha(test_patch),
            "production_patch_sha256":sha(prod_patch),"test_application":test_application,"production_application":prod_application},
          "verifier":{"cwd":"studio/backend","targets":list(VERIFIER_TARGETS),"identity_digest":identity["digest"],
            "normalized_identity":identity["normalized"],"identical_before_after":True},
          "stop":{"decision":"CONTINUE","next_action":"RUN_BROADER_REGRESSION",
            "justification":"The focused pinned verifier passed, but selected-test coverage does not establish mission completion; broader regression verification remains required."}}
        signature={"before_return_code":2,"before_failure":before["failure_identity"],"after_return_code":0,
          "after_passed_count":passed,"test_patch_sha256":sha(test_patch),"production_patch_sha256":sha(prod_patch),
          "actual_changed_paths":final["changed_paths"],"verifier_identity_digest":identity["digest"],
          "selected_gates_clear":True,"future_eval_denylist_sha256":lineage["central_denylist_sha256"]}
        episode["replay_contract_signature"]=signature; episode["replay_contract_signature_sha256"]=stable(signature)
        diag.update({"status":"REPLAY_VALIDATED","exact_blocker":None,
          "gates_passed_count":len(diag["gates_passed"]),"selected_gates_clear":True})
        return episode,diag
    except Exception as exc:
        diag["exact_blocker"]=str(exc); return None,diag
    finally:
        if disposable is not None: shutil.rmtree(disposable,ignore_errors=True)

FORBIDDEN_MODEL_INPUT_FIELDS={"after","after_commit","chosen","chosen_action","chosen_action_id",
 "production_patch_sha256","observations","state_after","semantic_signature","semantic_signature_sha256",
 "outcome","target","targets","state_delta","patch_trace"}
FORBIDDEN_MODEL_INPUT_VALUES={AFTER.lower(),PRODUCTION_PATCH_SHA256.lower()}

def audit_model_input(value:Any,path:str="$")->dict[str,Any]:
    checked=0
    def walk(item:Any,location:str)->None:
        nonlocal checked
        checked+=1
        if isinstance(item,dict):
            for key,child in item.items():
                if str(key).lower() in FORBIDDEN_MODEL_INPUT_FIELDS:
                    raise GateError("forbidden_model_input_field:"+location+"."+str(key))
                walk(child,location+"."+str(key))
        elif isinstance(item,list):
            for index,child in enumerate(item): walk(child,f"{location}[{index}]")
        elif isinstance(item,str) and item.lower() in FORBIDDEN_MODEL_INPUT_VALUES:
            raise GateError("forbidden_model_input_value:"+location)
    walk(value,path)
    return {"passed":True,"recursive_values_checked":checked,
      "forbidden_field_count":len(FORBIDDEN_MODEL_INPUT_FIELDS),
      "forbidden_value_count":len(FORBIDDEN_MODEL_INPUT_VALUES)}

def expected_combined_diff_sha256()->str:
    return sha(patch_bytes((*PRODUCTION_PATHS,*TEST_PATHS)))

def reconstructed_verifier_identity()->dict[str,Any]:
    hashes={}
    for target in VERIFIER_TARGETS:
        proc=subprocess.run(["git","-C",str(SOURCE_REPO),"show",f"{AFTER}:studio/backend/{target}"],
          stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
        if proc.returncode: raise GateError("selected_test_blob_missing:"+target)
        hashes[target]=sha(proc.stdout)
    normalized={"python":PYTHON,"python_executable_sha256":sha(Path(PYTHON).read_bytes()),
      "argv":[PYTHON,"-m","pytest","-q","-c","/dev/null","-o","cache_dir=<temp>",*VERIFIER_TARGETS],
      "cwd":"studio/backend","cpu_only":True,
      "environment":{"CUDA_VISIBLE_DEVICES":"","PYTHONDONTWRITEBYTECODE":"1","HF_HUB_OFFLINE":"1",
       "TRANSFORMERS_OFFLINE":"1","PIP_NO_INDEX":"1","WANDB_DISABLED":"true",
       "OPENAI_API_KEY":"<cleared>","ANTHROPIC_API_KEY":"<cleared>",
       "PYTHONPATH":"<worktree>:<worktree>/studio/backend"},"selected_test_content_sha256":hashes}
    return {"normalized":normalized,"digest":stable(normalized),"reconstructed_from_pinned_execution_contract":True}

def expected_events(commitment_sha256:str)->list[dict[str,Any]]:
    return [{"order":1,"event":"TEST_SETUP","policy_action":False,"patch_sha256":TEST_PATCH_SHA256},
      {"order":2,"event":"VERIFIER_FAIL","observation":"before","failure_identity":"ImportError:_mla_mtp_auto_enabled"},
      {"order":3,"event":"CANDIDATE_COMMITMENT","commitment_sha256":commitment_sha256},
      {"order":4,"event":"CHOSEN_PRODUCTION_ACTION","action_id":"A"},
      {"order":5,"event":"PRODUCTION_PATCH_APPLY","patch_sha256":PRODUCTION_PATCH_SHA256},
      {"order":6,"event":"SAME_VERIFIER_PASS","observation":"after","passed_count":245},
      {"order":7,"event":"STATE_UPDATE","verifier_status":"FOCUSED_PASS"},
      {"order":8,"event":"CONTINUE","decision":"CONTINUE","next_action":"RUN_BROADER_REGRESSION"}]


def _expected_status(paths:list[str])->str:
    return "\n".join(" M "+path for path in sorted(paths))


def _expected_state(*,tree:str,paths:list[str],diff:bytes)->dict[str,Any]:
    status=_expected_status(paths)
    identity=stable([BEFORE,tree,status,sha(diff)])
    return {"head":BEFORE,"head_tree":tree,"clean":False,"status_porcelain":status,
      "changed_paths":sorted(paths),"working_diff_sha256":sha(diff),
      "working_diff_bytes":len(diff),"identity_sha256":identity}


def _validate_streams(name:str,obs:dict[str,Any])->None:
    for stream in ("stdout","stderr"):
        value=obs.get(stream)
        if not isinstance(value,str): raise GateError(name+"_"+stream+"_missing")
        encoded=value.encode("utf-8")
        if obs.get(stream+"_bytes")!=len(encoded): raise GateError(name+"_"+stream+"_bytes_invalid")
        if obs.get(stream+"_sha256")!=sha(encoded): raise GateError(name+"_"+stream+"_hash_invalid")


def _validate_observation(name:str,obs:dict[str,Any],identity:dict[str,Any])->dict[str,Any]:
    if not isinstance(obs,dict): raise GateError(name+"_observation_missing")
    _validate_streams(name,obs)
    if obs.get("verifier_identity_digest")!=identity["digest"]:
        raise GateError(name+"_verifier_identity_invalid")
    if obs.get("timed_out") is not False: raise GateError(name+"_timed_out")
    argv=obs.get("argv")
    if not isinstance(argv,list) or len(argv)!=len(identity["normalized"]["argv"]):
        raise GateError(name+"_verifier_argv_invalid")
    normalized_argv=list(argv)
    if not isinstance(normalized_argv[7],str) or not normalized_argv[7].startswith("cache_dir="):
        raise GateError(name+"_verifier_cache_arg_invalid")
    cache=Path(normalized_argv[7].split("=",1)[1])
    normalized_argv[7]="cache_dir=<temp>"
    if normalized_argv!=identity["normalized"]["argv"]:
        raise GateError(name+"_verifier_argv_invalid")
    cwd=obs.get("cwd")
    if not isinstance(cwd,str) or Path(cwd).parts[-3:]!=("repo","studio","backend"):
        raise GateError(name+"_verifier_cwd_invalid")
    if cache.parent!=Path(cwd).parents[2]: raise GateError(name+"_verifier_cache_lineage_invalid")
    if obs.get("command")!=shlex.join(argv): raise GateError(name+"_verifier_command_invalid")
    return {"stdout_sha256":obs["stdout_sha256"],"stderr_sha256":obs["stderr_sha256"],
      "stdout_bytes":obs["stdout_bytes"],"stderr_bytes":obs["stderr_bytes"],
      "return_code":obs.get("return_code")}


def _validate_application(name:str,value:Any,expected_filename:str)->Path:
    if not isinstance(value,dict) or value.get("zero_fuzz") is not True:
        raise GateError(name+"_trace_invalid")
    repo:Path|None=None;patch_file:Path|None=None
    for phase in ("check","apply"):
        obs=value.get(phase)
        if not isinstance(obs,dict) or obs.get("return_code")!=0 or obs.get("timed_out") is not False:
            raise GateError(name+"_"+phase+"_trace_invalid")
        _validate_streams(name+"_"+phase,obs)
        argv=obs.get("argv")
        if not isinstance(argv,list): raise GateError(name+"_"+phase+"_argv_invalid")
        expected_tail=["apply", "--check", "--verbose"] if phase=="check" else ["apply", "--verbose"]
        expected_len=7 if phase=="check" else 6
        if len(argv)!=expected_len or argv[:2]!=["git","-C"] or argv[3:-1]!=expected_tail:
            raise GateError(name+"_"+phase+"_argv_invalid")
        current_repo=Path(argv[2]);current_patch=Path(argv[-1])
        if current_patch.name!=expected_filename or current_patch.parent.name!="partitions":
            raise GateError(name+"_"+phase+"_patch_ref_invalid")
        if repo is not None and current_repo!=repo: raise GateError(name+"_repo_changed")
        if patch_file is not None and current_patch!=patch_file: raise GateError(name+"_patch_ref_changed")
        repo=current_repo;patch_file=current_patch
        if obs.get("cwd") is not None or obs.get("command")!=shlex.join(argv):
            raise GateError(name+"_"+phase+"_command_invalid")
    assert repo is not None
    return repo


def evidence_signature(episode:dict[str,Any],observation_refs:dict[str,Any]|None=None)->dict[str,Any]:
    before,after=episode["observations"]["before"],episode["observations"]["after"]
    refs=observation_refs or {
      "before":{key:before[key] for key in ("stdout_sha256","stderr_sha256","stdout_bytes","stderr_bytes","return_code")},
      "after":{key:after[key] for key in ("stdout_sha256","stderr_sha256","stdout_bytes","stderr_bytes","return_code")}}
    patch_binding={"chosen_action":episode["chosen_action"],
      "test_patch_sha256":episode["patch_trace"]["test_patch_sha256"],
      "production_patch_sha256":episode["patch_trace"]["production_patch_sha256"],
      "final_diff_sha256":episode["state_after"]["working_diff_sha256"],
      "final_diff_bytes":episode["state_after"]["working_diff_bytes"]}
    return {"projection_schema":"stage12583_private_projection_candidate_v2",
      "source_identity":episode["source"],"commitment_sha256":episode["pre_outcome_commitment"]["commitment_sha256"],
      "chosen_action_sha256":stable(episode["chosen_action"]),"patch_binding_sha256":stable(patch_binding),
      "ordered_events_sha256":stable(episode["ordered_events"]),
      "state_before_identity_sha256":episode["state_before"]["identity_sha256"],
      "state_after_identity_sha256":episode["state_after"]["identity_sha256"],
      "final_diff_sha256":episode["state_after"]["working_diff_sha256"],
      "observation_refs":refs,"verifier_identity_digest":episode["verifier"]["identity_digest"]}


def validate_causal_evidence(episode:dict[str,Any])->dict[str,Any]:
    if not isinstance(episode,dict): raise GateError("episode_not_object")
    lineage=episode.get("lineage_evidence")
    validate_lineage_evidence_structure(lineage)
    tree=git_stdout(SOURCE_REPO,"rev-parse",f"{BEFORE}^{{tree}}")
    expected_source={"repository":str(SOURCE_REPO),"before":BEFORE,"after":AFTER,
      "ordered":True,"before_tree":tree}
    if episode.get("source")!=expected_source: raise GateError("source_identity_invalid")
    commit_paths=sorted(EXPECTED_PATHS)
    expected_partition={"commit_changed_paths":commit_paths,"test_only_paths":list(TEST_PATHS),
      "production_only_paths":list(PRODUCTION_PATHS),
      "excluded_paths":sorted(set(commit_paths)-set(TEST_PATHS)-set(PRODUCTION_PATHS)),"overlap":[]}
    if episode.get("path_partition")!=expected_partition: raise GateError("path_partition_invalid")
    commitment=candidate_commitment()
    if episode.get("pre_outcome_commitment")!=commitment: raise GateError("commitment_not_canonical")
    chosen={"action_id":"A","role":commitment["candidate_actions"][0]["role"],
      "production_patch_sha256":PRODUCTION_PATCH_SHA256}
    if episode.get("chosen_action")!=chosen: raise GateError("chosen_action_invalid")
    events=expected_events(commitment["commitment_sha256"])
    validate_ordered_events(episode.get("ordered_events",[]))
    if episode.get("ordered_events")!=events: raise GateError("ordered_events_binding_invalid")

    test_patch=patch_bytes(TEST_PATHS);prod_patch=patch_bytes(PRODUCTION_PATHS)
    combined_patch=patch_bytes((*PRODUCTION_PATHS,*TEST_PATHS))
    patch_trace=episode.get("patch_trace")
    if not isinstance(patch_trace,dict) or patch_trace.get("regenerated_from_commits") is not True:
        raise GateError("patch_trace_invalid")
    if patch_trace.get("test_patch_sha256")!=sha(test_patch) or sha(test_patch)!=TEST_PATCH_SHA256:
        raise GateError("test_patch_binding_invalid")
    if patch_trace.get("production_patch_sha256")!=sha(prod_patch) or sha(prod_patch)!=PRODUCTION_PATCH_SHA256:
        raise GateError("production_patch_binding_invalid")
    test_repo=_validate_application("test_application",patch_trace.get("test_application"),"test_setup.patch")
    production_repo=_validate_application("production_application",patch_trace.get("production_application"),"production_repair.patch")
    if production_repo!=test_repo: raise GateError("patch_application_repo_changed")

    identity=reconstructed_verifier_identity()
    expected_verifier={"cwd":"studio/backend","targets":list(VERIFIER_TARGETS),
      "identity_digest":identity["digest"],"normalized_identity":identity["normalized"],
      "identical_before_after":True}
    if episode.get("verifier")!=expected_verifier: raise GateError("verifier_contract_invalid")
    observations=episode.get("observations")
    if not isinstance(observations,dict): raise GateError("both_verifier_observations_missing")
    before=observations.get("before");after=observations.get("after")
    before_ref=_validate_observation("before",before,identity)
    after_ref=_validate_observation("after",after,identity)
    if before.get("argv")!=after.get("argv") or before.get("cwd")!=after.get("cwd"):
        raise GateError("verifier_observation_contract_changed")
    if Path(before["cwd"]).parents[1]!=test_repo:
        raise GateError("verifier_patch_trace_repo_mismatch")
    if before.get("return_code")!=2 or before.get("failure_identity")!="ImportError:_mla_mtp_auto_enabled":
        raise GateError("before_evidence_invalid")
    if after.get("return_code")!=0 or after.get("passed_count")!=245:
        raise GateError("after_evidence_invalid")

    before_state=_expected_state(tree=tree,paths=list(TEST_PATHS),diff=test_patch)
    after_state=_expected_state(tree=tree,paths=sorted((*TEST_PATHS,*PRODUCTION_PATHS)),diff=combined_patch)
    state_before=episode.get("state_before")
    state_after=episode.get("state_after")
    if not isinstance(state_before,dict) or {key:state_before.get(key) for key in before_state}!=before_state:
        raise GateError("state_before_invalid")
    if not isinstance(state_after,dict) or {key:state_after.get(key) for key in after_state}!=after_state:
        raise GateError("state_after_invalid")
    baseline_identity=stable([BEFORE,tree,"",sha(b"")])
    expected_delta={"baseline_identity_sha256":baseline_identity,
      "state_before_identity_sha256":before_state["identity_sha256"],
      "state_after_identity_sha256":after_state["identity_sha256"],
      "actual_changed_paths":after_state["changed_paths"],"expected_changed_paths":after_state["changed_paths"],
      "production_changed_paths":list(PRODUCTION_PATHS),"no_unrelated_residue":True}
    if episode.get("state_delta")!=expected_delta: raise GateError("state_delta_invalid")
    expected_stop={"decision":"CONTINUE","next_action":"RUN_BROADER_REGRESSION",
      "justification":"The focused pinned verifier passed, but selected-test coverage does not establish mission completion; broader regression verification remains required."}
    if episode.get("stop")!=expected_stop: raise GateError("stop_contract_invalid")
    refs={"before":before_ref,"after":after_ref}
    signature=evidence_signature(episode,refs)
    embedded=episode.get("semantic_signature")
    embedded_digest=episode.get("semantic_signature_sha256")
    if embedded is not None and embedded!=signature: raise GateError("embedded_semantic_signature_invalid")
    if embedded_digest is not None and embedded_digest!=stable(signature):
        raise GateError("embedded_semantic_signature_hash_invalid")
    return {"valid":True,"both_verifier_runs":True,"patch_trace_observed":True,
      "fail_to_pass_observed":True,"final_diff_sha256":sha(combined_patch),
      "observation_refs":refs,"signature":signature,"signature_sha256":stable(signature)}


def build_training_projection(episode:dict[str,Any],validation:dict[str,Any])->dict[str,Any]:
    if validation.get("valid") is not True: raise GateError("projection_evidence_not_validated")
    model_input={"task":{"source_identity":{"repo_family":"unsloth",
       "source_path":str(SOURCE_REPO),"root_identity":STAGE},
       "before_commit":BEFORE,"test_only_paths":list(TEST_PATHS),
       "objective":"diagnose the observed focused verifier failure without access to repair outcomes"},
      "operational_state_before":{"identity_sha256":episode["state_before"]["identity_sha256"],
       "failure_identity":episode["observations"]["before"]["failure_identity"]},
      "prior_verifier_evidence":validation["observation_refs"]["before"]}
    audit=audit_model_input(model_input)
    projection={"record_type":"stage12583_custom_projection_candidate_v2",
      "split":"projection_only","artifact_scope":"projection_candidate_only",
      "training_admission_allowed":False,
      "training_admission_blockers":["custom_projection_not_trainer_native",
        "historical_nonleaky_candidate_set_not_proven"],
      "model_input":model_input,"model_input_forbidden_audit":audit,
      "causal_evidence_signature_sha256":validation["signature_sha256"],
      "chosen_action_projected":False,"targets_projected":False}
    validate_training_projection(projection)
    return projection


def validate_training_projection(projection:dict[str,Any])->None:
    if projection.get("record_type")!="stage12583_custom_projection_candidate_v2":
        raise GateError("projection_record_type_invalid")
    if projection.get("split")!="projection_only": raise GateError("projection_must_not_be_train_split")
    if projection.get("training_admission_allowed") is not False:
        raise GateError("projection_training_admission_must_be_false")
    required_blockers={"custom_projection_not_trainer_native","historical_nonleaky_candidate_set_not_proven"}
    if not required_blockers.issubset(set(projection.get("training_admission_blockers",[]))):
        raise GateError("projection_blockers_missing")
    model_input=projection.get("model_input")
    audit=audit_model_input(model_input)
    if not audit["passed"] or projection.get("model_input_forbidden_audit",{}).get("passed") is not True:
        raise GateError("projection_model_input_audit_invalid")
    extraction=COMMON_GUARD.extract_future_eval_identities(model_input)
    if extraction.malformed_paths: raise GateError("projection_typed_identity_malformed")
    if any(not extraction.identities[kind] for kind in COMMON_GUARD.IDENTITY_TYPES):
        raise GateError("projection_typed_identity_missing")
    forbidden={"candidate_actions","production_path_candidates","chosen_action","chosen_action_id",
      "targets","target","after","after_commit","state_after","patch_trace","ordered_events"}
    def keys(value:Any):
        if isinstance(value,dict):
            for key,child in value.items():
                yield str(key).casefold();yield from keys(child)
        elif isinstance(value,list):
            for child in value:yield from keys(child)
    overlap=forbidden&set(keys(model_input))
    if overlap: raise GateError("projection_outcome_or_candidate_leak:"+",".join(sorted(overlap)))
    if projection.get("chosen_action_projected") is not False or projection.get("targets_projected") is not False:
        raise GateError("projection_answer_projection_invalid")

def load_single_jsonl(path:Path,allow_missing:bool=False)->dict[str,Any]|None:
    if not path.exists():
        if allow_missing:return None
        raise GateError("prior_artifact_missing:"+path.name)
    try: rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    except json.JSONDecodeError as exc: raise GateError("prior_artifact_malformed:"+path.name) from exc
    if len(rows)!=1: raise GateError("prior_artifact_row_count_invalid:"+path.name)
    return rows[0]

def admission_counters(validation:dict[str,Any]|None)->dict[str,int]:
    valid=bool(validation and validation.get("valid") is True)
    patch=bool(valid and validation.get("patch_trace_observed") is True)
    transition=bool(valid and validation.get("fail_to_pass_observed") is True)
    return {"executed_replay_count":int(valid),"materialized_level3_candidate_count":int(valid),
      "observed_patch_trace_count":int(patch),"observed_fail_to_pass_count":int(transition),
      "training_admitted_projection_count":0,"training_admitted_level3_source_count":0}


def blocked_result(selected:dict[str,Any],validation:dict[str,Any])->dict[str,Any]:
    return {"stage":STAGE,"status":"BLOCKED_PROJECTION_ONLY","training_allowed":False,
      "strict_eval":False,"source_heldout":False,"support_scope":"projection-only",
      "selected_gate_evidence":selected,"counters":admission_counters(validation),
      "exact_blocker":"custom_projection_not_trainer_native;historical_nonleaky_candidate_set_not_proven",
      "trainer_enforcement_boundary":{"authoritative_entrypoint":
       "recovered_trainer.load_manifest(primary_and_phase_manifests)",
       "central_denylist":"configs/software_maintainer/future_eval_identity_denylist_v1.json",
       "common_guard":"scripts/source_lineage_guard.py","standalone_scripts_authoritative":False},
      "claim_boundary":("The validated replay is retained only as a private source and blocked custom projection "
       "candidate. The projection is not trainer-native, has no train split, chosen action, target, or exact "
       "production-path candidate set. Zero training projections and zero Level-3 sources are admitted.")}


def materialize_training_admission(episode:dict[str,Any],validation:dict[str,Any],
 out:Path,summary:Path)->dict[str,Any]:
    if validation.get("valid") is not True: raise GateError("materialization_requires_validated_evidence")
    selected=lineage_evidence()
    validate_lineage_evidence_structure(selected)
    episode["artifact_scope"]="private_non_trainer"
    episode["trainer_visible"]=False
    episode["training_admission_allowed"]=False
    episode["training_admission_blockers"]=["raw_trajectory_never_trainer_input",
      "custom_projection_not_trainer_native","historical_nonleaky_candidate_set_not_proven"]
    episode["lineage_evidence"]=selected
    episode["semantic_signature"]=validation["signature"]
    episode["semantic_signature_sha256"]=validation["signature_sha256"]
    projection=build_training_projection(episode,validation)
    write_jsonl(out/"causal_candidates.jsonl",[episode])
    write_jsonl(out/"raw_private_episode.jsonl",[episode])
    write_jsonl(out/"model_training_projection_candidate.jsonl",[projection])
    write_jsonl(out/"admitted_training_projections.jsonl",[])
    write_jsonl(out/"admitted_episodes.jsonl",[])
    result=blocked_result(selected,validation)
    write_json(out/"summary.json",result);write_json(summary,result);return result


def _rejected_result(exc:Exception)->dict[str,Any]:
    return {"stage":STAGE,"status":"REJECTED","training_allowed":False,
      "strict_eval":False,"source_heldout":False,"support_scope":"projection-only",
      "counters":admission_counters(None),"exact_blocker":str(exc),
      "claim_boundary":"Evidence validation rejected; no projection or source admitted for training."}


def rematerialize_existing(out:Path=OUT,summary:Path=SUMMARY)->dict[str,Any]:
    try:
        episode=load_single_jsonl(out/"causal_candidates.jsonl")
        validation=validate_causal_evidence(episode)
        return materialize_training_admission(episode,validation,out,summary)
    except Exception as exc:
        write_jsonl(out/"admitted_training_projections.jsonl",[])
        write_jsonl(out/"admitted_episodes.jsonl",[])
        result=_rejected_result(exc)
        write_json(out/"summary.json",result);write_json(summary,result);return result


def execute(out:Path=OUT,summary:Path=SUMMARY)->dict[str,Any]:
    try:
        episode,diag=replay(out)
        if episode is None: raise GateError(diag.get("exact_blocker") or "replay_rejected")
        validation=validate_causal_evidence(episode)
        return materialize_training_admission(episode,validation,out,summary)
    except Exception as exc:
        write_jsonl(out/"admitted_training_projections.jsonl",[])
        write_jsonl(out/"admitted_episodes.jsonl",[])
        result=_rejected_result(exc)
        write_json(out/"summary.json",result);write_json(summary,result);return result

def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--output-dir",type=Path,default=OUT)
    parser.add_argument("--summary",type=Path,default=SUMMARY)
    parser.add_argument("--rematerialize-existing",action="store_true")
    args=parser.parse_args()
    result=(rematerialize_existing if args.rematerialize_existing else execute)(args.output_dir,args.summary)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["status"]=="BLOCKED_PROJECTION_ONLY" else 2
if __name__=="__main__":raise SystemExit(main())
