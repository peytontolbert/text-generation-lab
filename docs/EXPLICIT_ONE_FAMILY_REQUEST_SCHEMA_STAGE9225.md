# Stage9225 Explicit One-Family Request Schema

Passed: `True`

Supported families:
- `structured_policy_probe`
- `bounded_decoder_ce_probe`
- `denoise_repair_probe`

Required request fields:
- `requested_family`
- `request_scope`
- `allowed_next_artifact`
- `same_stage_execution_allowed`
- `trainer_invocation_allowed`
- `model_forward_allowed`
- `cleanup_allowed`
- `arxiv_access_allowed`
- `runtime_allowed`
- `checkpoint_export_allowed`

Rejected request classes:
- `missing_requested_family`
- `unsupported_requested_family`
- `multiple_families_requested`
- `same_stage_execution_requested`
- `trainer_invocation_requested`
- `model_forward_or_generation_requested`
- `cleanup_requested`
- `arxiv_access_requested`
- `runtime_requested`
- `checkpoint_export_requested`
- `scope_not_design_only`

Template example:
```json
{
  "allowed_next_artifact": "family_specific_final_preexecution_audit_design",
  "arxiv_access_allowed": false,
  "checkpoint_export_allowed": false,
  "cleanup_allowed": false,
  "model_forward_allowed": false,
  "request_scope": "design_family_specific_final_preexecution_audit_only",
  "requested_family": "structured_policy_probe",
  "runtime_allowed": false,
  "same_stage_execution_allowed": false,
  "trainer_invocation_allowed": false
}
```

Next: Wait for a valid explicit one-family request, or continue no-execution central graph review.
