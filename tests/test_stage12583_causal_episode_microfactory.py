from __future__ import annotations
import copy, importlib.util, json, sys
from pathlib import Path
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/build_or_run_stage12583_causal_episode_microfactory.py"
ROOT=SCRIPT.parents[1]
SPEC=importlib.util.spec_from_file_location("stage12583",SCRIPT);assert SPEC and SPEC.loader
mod=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=mod;SPEC.loader.exec_module(mod)
RAW=ROOT/"runs/local/artifacts/stage12583_causal_episode_microfactory/causal_candidates.jsonl"

def raw_episode(): return json.loads(RAW.read_text().strip())
def all_keys(value):
    if isinstance(value,dict):
        for key,child in value.items(): yield str(key).casefold();yield from all_keys(child)
    elif isinstance(value,list):
        for child in value:yield from all_keys(child)

def test_commitment_excludes_gold_and_exact_production_paths():
    c=mod.candidate_commitment();encoded=json.dumps(c)
    assert c["sealed_before_repair_outcome"] and c["includes_prior_verifier_observation"]
    assert len(c["candidate_actions"])>=5 and c["semantic_hard_negative_count"]>=3
    assert c["candidate_provenance"]["successful_after_diff_read"] is False
    assert c["candidate_provenance"]["historical_nonleaky_provenance"] is False
    assert "chosen_action_id" not in c and "after" not in c["inputs"]
    assert mod.AFTER not in encoded and mod.PRODUCTION_PATCH_SHA256 not in encoded
    assert all(path not in encoded for path in mod.PRODUCTION_PATHS)

def test_pytest_count_accepts_punctuation():
    assert mod.parse_passed_count("245 passed, 1 warning in 3.20s")==245

def test_focused_verifier_forbids_stop():
    events=[{"event":name} for name in mod.EXPECTED_EVENTS[:-1]]
    events[1]["observation"]="before";events[5]["observation"]="after"
    events.append({"event":"STOP","decision":"STOP"})
    with pytest.raises(mod.GateError,match="focused_verifier_cannot_justify_stop"):
        mod.validate_ordered_events(events)

def test_common_guard_and_central_denylist_are_authoritative():
    assert Path(mod.COMMON_GUARD.__file__).resolve()==(ROOT/"scripts/source_lineage_guard.py").resolve()
    assert mod.CENTRAL_DENYLIST==mod.COMMON_GUARD.DEFAULT_FUTURE_EVAL_IDENTITY_DENYLIST
    deny=mod.COMMON_GUARD.load_future_eval_identity_denylist(mod.CENTRAL_DENYLIST)
    assert "unsloth" in deny["repo_family"]
    assert "/arxiv/repositories/unsloth" in deny["source_path"]
    assert mod.BEFORE in deny["root_identity"] and mod.AFTER in deny["root_identity"]

def test_authoritative_selected_rows_all_730_clear():
    evidence=mod.selected_gate_evidence()
    assert evidence["total_rows_checked"]==730
    assert evidence["authoritative_row_file_count"]==6
    assert evidence["identityless_count"]==evidence["malformed_count"]==evidence["unsloth_identity_count"]==0
    assert evidence["common_guard_path"]=="scripts/source_lineage_guard.py"
    assert evidence["harness_reference"]["authoritative"] is False

def test_selected_gate_hash_mismatch_and_unsloth_overlap(tmp_path):
    gate=tmp_path/"gate.jsonl";gate.write_text(json.dumps({"repo_family":"clear"})+"\n")
    with pytest.raises(mod.GateError,match="selected_gate_hash_mismatch"):
        mod.selected_gate_evidence(tmp_path,{"gate.jsonl":("0"*64,1)})
    gate.write_text(json.dumps({"RePoSiToRy":"UnSlOtH"})+"\n")
    with pytest.raises(mod.GateError,match="selected_gate_unsloth_overlap"):
        mod.selected_gate_evidence(tmp_path,{"gate.jsonl":(mod.sha(gate.read_bytes()),1)})

def test_selected_gate_rejects_identityless_and_malformed(tmp_path):
    gate=tmp_path/"gate.jsonl";gate.write_text("{}\n")
    with pytest.raises(mod.GateError,match="selected_gate_identityless"):
        mod.selected_gate_evidence(tmp_path,{"gate.jsonl":(mod.sha(gate.read_bytes()),1)})
    gate.write_text("{\n")
    with pytest.raises(mod.GateError,match="selected_gate_malformed_json"):
        mod.selected_gate_evidence(tmp_path,{"gate.jsonl":(mod.sha(gate.read_bytes()),1)})

def test_live_replay_lineage_contract_uses_central_denylist_shape():
    lineage=mod.lineage_evidence()
    mod.validate_lineage_evidence_structure(lineage)
    assert lineage["central_denylist_path"]=="configs/software_maintainer/future_eval_identity_denylist_v1.json"
    assert lineage["central_denylist_sha256"]==mod.sha(mod.CENTRAL_DENYLIST.read_bytes())
    assert lineage["training_admission_allowed"] is False
    assert "future_eval_denylist" not in lineage

def test_model_input_recursive_audit_rejects_raw_and_gold():
    with pytest.raises(mod.GateError,match="forbidden_model_input_field"):
        mod.audit_model_input({"nested":[{"state_after":{}}]})
    with pytest.raises(mod.GateError,match="forbidden_model_input_value"):
        mod.audit_model_input({"nested":[mod.AFTER]})

def test_projection_is_blocked_sanitized_and_contains_no_answer():
    episode=raw_episode();validation=mod.validate_causal_evidence(episode)
    projection=mod.build_training_projection(episode,validation)
    assert projection["split"]=="projection_only"
    assert projection["training_admission_allowed"] is False
    assert projection["chosen_action_projected"] is False and projection["targets_projected"] is False
    mod.validate_training_projection(projection)
    keys=set(all_keys(projection["model_input"]))
    forbidden={"candidate_actions","production_path_candidates","chosen_action","chosen_action_id",
      "targets","target","after","after_commit","state_after","patch_trace","ordered_events"}
    assert not forbidden&keys
    encoded=json.dumps(projection["model_input"])
    assert mod.AFTER not in encoded and mod.PRODUCTION_PATCH_SHA256 not in encoded
    assert all(path not in encoded for path in mod.PRODUCTION_PATHS)

def test_projection_rejects_train_or_answer_fields():
    episode=raw_episode();validation=mod.validate_causal_evidence(episode)
    projection=mod.build_training_projection(episode,validation)
    projection["split"]="train"
    with pytest.raises(mod.GateError,match="projection_must_not_be_train_split"):
        mod.validate_training_projection(projection)
    projection=mod.build_training_projection(episode,validation)
    projection["model_input"]["candidate_actions"]=episode["pre_outcome_commitment"]["candidate_actions"]
    with pytest.raises(mod.GateError,match="forbidden_model_input_field|projection_outcome_or_candidate_leak"):
        mod.validate_training_projection(projection)

def mutate_commitment_action(episode, action_id):
    for action in episode["pre_outcome_commitment"]["candidate_actions"]:
        if action["action_id"]==action_id: action["role"]+=" tampered"

def mutation_cases():
    return [
      ("action_b",lambda e:mutate_commitment_action(e,"B"),"commitment_not_canonical"),
      ("action_f",lambda e:mutate_commitment_action(e,"F"),"commitment_not_canonical"),
      ("chosen_action",lambda e:e["chosen_action"].update(action_id="B"),"chosen_action_invalid"),
      ("event_action",lambda e:e["ordered_events"][3].update(action_id="B"),"ordered_events_binding_invalid"),
      ("event_patch",lambda e:e["ordered_events"][4].update(patch_sha256="0"*64),"ordered_events_binding_invalid"),
      ("patch_hash",lambda e:e["patch_trace"].update(production_patch_sha256="0"*64),"production_patch_binding_invalid"),
      ("patch_argv",lambda e:e["patch_trace"]["production_application"]["apply"]["argv"].__setitem__(-1,"other.patch"),"production_application_apply_patch_ref_invalid"),
      ("before_text",lambda e:e["observations"]["before"].update(stdout="tampered"),"before_stdout_bytes_invalid|before_stdout_hash_invalid"),
      ("after_hash",lambda e:e["observations"]["after"].update(stdout_sha256="0"*64),"after_stdout_hash_invalid"),
      ("after_bytes",lambda e:e["observations"]["after"].update(stdout_bytes=0),"after_stdout_bytes_invalid"),
      ("verifier",lambda e:e["verifier"].update(identity_digest="0"*64),"verifier_contract_invalid"),
      ("verifier_argv",lambda e:e["observations"]["before"]["argv"].__setitem__(-1,"tests/other.py"),"before_verifier_argv_invalid"),
      ("verifier_cwd",lambda e:e["observations"]["after"].update(cwd="/tmp/other"),"after_verifier_cwd_invalid"),
      ("state_before",lambda e:e["state_before"].update(working_diff_sha256="0"*64),"state_before_invalid"),
      ("state_final",lambda e:e["state_after"].update(working_diff_sha256="0"*64),"state_after_invalid"),
      ("state_delta",lambda e:e["state_delta"].update(no_unrelated_residue=False),"state_delta_invalid"),
    ]

@pytest.mark.parametrize(("name","mutator","error"),mutation_cases(),ids=[row[0] for row in mutation_cases()])
def test_causal_validation_rejects_bound_evidence_mutations(name,mutator,error):
    episode=copy.deepcopy(raw_episode());mutator(episode)
    with pytest.raises(mod.GateError,match=error):
        mod.validate_causal_evidence(episode)

def test_final_diff_signature_and_observation_references_are_bound():
    episode=raw_episode();validation=mod.validate_causal_evidence(episode)
    signature=validation["signature"]
    assert signature["final_diff_sha256"]==episode["state_after"]["working_diff_sha256"]
    assert signature["observation_refs"]["before"]["stdout_sha256"]==episode["observations"]["before"]["stdout_sha256"]
    required={"commitment_sha256","chosen_action_sha256","patch_binding_sha256","ordered_events_sha256",
      "state_before_identity_sha256","state_after_identity_sha256","verifier_identity_digest"}
    assert required.issubset(signature)

def test_verifier_identity_binds_environment_python_and_tests(tmp_path):
    worktree=tmp_path/"repo"
    for target in mod.VERIFIER_TARGETS:
        path=worktree/"studio/backend"/target;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(target)
    identity=mod.verifier_identity(tmp_path/"cache",worktree)["normalized"];env=identity["environment"]
    assert identity["python_executable_sha256"]==mod.sha(Path(mod.PYTHON).read_bytes())
    assert env["PYTHONPATH"]=="<worktree>:<worktree>/studio/backend"
    assert env["OPENAI_API_KEY"]=="<cleared>" and env["WANDB_DISABLED"]=="true"
    assert set(identity["selected_test_content_sha256"])==set(mod.VERIFIER_TARGETS)

def test_prior_loader_rejects_malformed_and_multiple(tmp_path):
    path=tmp_path/"rows.jsonl";path.write_text("{")
    with pytest.raises(mod.GateError,match="prior_artifact_malformed"):mod.load_single_jsonl(path)
    path.write_text("{}\n{}\n")
    with pytest.raises(mod.GateError,match="prior_artifact_row_count_invalid"):mod.load_single_jsonl(path)

def test_materialization_is_projection_only_with_validated_counters(tmp_path):
    episode=raw_episode();validation=mod.validate_causal_evidence(episode)
    result=mod.materialize_training_admission(episode,validation,tmp_path,tmp_path/"summary.json")
    assert result["status"]=="BLOCKED_PROJECTION_ONLY"
    assert result["training_allowed"] is False and result["support_scope"]=="projection-only"
    assert (tmp_path/"admitted_episodes.jsonl").read_text()==""
    assert (tmp_path/"admitted_training_projections.jsonl").read_text()==""
    candidate=json.loads((tmp_path/"model_training_projection_candidate.jsonl").read_text())
    mod.validate_training_projection(candidate)
    raw=json.loads((tmp_path/"raw_private_episode.jsonl").read_text())
    assert raw["trainer_visible"] is False and raw["artifact_scope"]=="private_non_trainer"
    assert result["counters"]=={"executed_replay_count":1,"materialized_level3_candidate_count":1,
      "observed_patch_trace_count":1,"observed_fail_to_pass_count":1,
      "training_admitted_projection_count":0,"training_admitted_level3_source_count":0}
