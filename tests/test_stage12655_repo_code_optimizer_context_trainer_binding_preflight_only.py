import hashlib, importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/build_stage12655_repo_code_optimizer_context_trainer_binding_preflight_only.py"
SPEC=importlib.util.spec_from_file_location("stage12655",SCRIPT); assert SPEC and SPEC.loader
stage=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(stage)
def read_json(p: Path): return json.loads(p.read_text())
def stable(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")).hexdigest()
def assert_false(r):
 for f in stage.FALSE_FIELDS: assert r[f] is False
EXPECTED=["contract.json","digest_pointer.json","private/repo_code_optimizer_context_trainer_binding_packet.json","summary.json"]
def test_load_inputs_pins_stage12654():
 loaded=stage.load_inputs(); assert loaded["summary"]==read_json(stage.S12654_SUMMARY)
def test_optimizer_binding_is_no_execution_and_trainer_bound():
 b=stage.build_optimizer_binding(); assert b["trainer_sha256"]==stage.EXPECTED_HASHES["trainer_bytes"]; assert b["optimizer_and_context"]["learning_rate"]==5e-5; assert b["trainer_invocation_allowed"] is False; assert b["device_policy_if_later_authorized"]["CUDA_VISIBLE_DEVICES"]=="2"
def test_packet_resolves_optimizer_blocker_only():
 s,c,p,ptr=stage.build_packet(stage.load_inputs()); assert s["decision"]=="OPTIMIZER_CONTEXT_BOUND_TO_TRAINER_IMPLEMENTATION_NO_TRAINING"; assert s["optimizer_context_bound_to_trainer_implementation"] is True; assert s["remaining_authorization_blocker_count"]==4; assert "optimizer_context_not_bound_to_trainer_implementation" not in s["remaining_authorization_blockers"]; assert s["training_allowed"] is False; assert ptr["contract_sha256"]==stable(c); [assert_false(r) for r in (s,c,p,ptr)]
def test_build_writes_artifacts(tmp_path):
 out=tmp_path/"artifacts"/stage.STAGE; sp=tmp_path/"summaries"/f"{stage.STAGE}.json"; s=stage.build(out,sp); assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())==EXPECTED; assert s==read_json(sp)
def test_generated_artifacts_match_current():
 assert sorted(p.relative_to(stage.OUT).as_posix() for p in stage.OUT.rglob("*") if p.is_file())==EXPECTED
 s=read_json(stage.OUT/"summary.json"); c=read_json(stage.OUT/"contract.json"); ptr=read_json(stage.OUT/"digest_pointer.json"); p=read_json(stage.OUT/"private/repo_code_optimizer_context_trainer_binding_packet.json"); assert s==read_json(stage.SUMMARY); assert ptr["private_packet_sha256"]==stable(p); [assert_false(r) for r in (s,c,ptr,p)]
def test_public_artifacts_sanitized():
 for path in [stage.OUT/"summary.json",stage.SUMMARY,stage.OUT/"contract.json",stage.OUT/"digest_pointer.json"]:
  encoded=json.dumps(read_json(path),sort_keys=True); assert not [n for n in stage.FORBIDDEN if n in encoded]
