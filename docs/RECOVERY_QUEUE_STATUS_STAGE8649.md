# Stage8649 Recovery Queue Status

## Restored Objectives
- `intent_to_build_strategy`: restored_local_and_shortcut_audited via stage8630_intent_to_build_neutral_manifest.json, stage8631_intent_to_build_shortcut_baseline.json
- `edit_localization`: restored_local_and_shortcut_audited via stage8636_edit_localization_neutral_manifest.json, stage8637_edit_localization_shortcut_baseline.json
- `patch_operator`: restored_local_and_shortcut_audited via stage8638_patch_operator_neutral_manifest.json, stage8639_patch_operator_shortcut_baseline.json
- `verifier_repair`: restored_local_and_shortcut_audited via stage8643_verifier_repair_neutral_manifest.json, stage8644_verifier_repair_shortcut_baseline.json
- `bounded_decoder_arguments`: restored_local_and_shortcut_audited via stage8645_bounded_decoder_arguments_neutral_manifest.json, stage8646_bounded_decoder_arguments_shortcut_baseline.json
- `output_repair_denoise`: restored_local_and_shortcut_audited via stage8647_output_repair_denoise_neutral_manifest.json, stage8648_output_repair_denoise_shortcut_baseline.json

## Still Partial
- `repo_state_graph_v1_enrichment`: Seed graph was restored/patched at 8536-8539, but enrichment is still synthetic-small and needs source-backed graph expansion plus aggregate curriculum gates.
- `symbol_binding`: Known partial: symbol-binding objective needs imbalance repair, source-backed rows, and direct route-card coverage before any training candidate.

## Authority Boundary
- Model/native execution: closed
- Decoder CE: closed
- Denoise CE: closed
- Runtime/source/body/Gemma/harness/scoring/promotion: closed

## Next Gate
Build an aggregate structured-curriculum gate across the restored objectives, then repair graph enrichment and symbol binding before any training candidate.
