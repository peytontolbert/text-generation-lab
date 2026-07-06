# Stage9046 Domain/Twin Manifest Schema Design

Passed: `True`

This stage defines metadata-only schemas for future DomainGraph, RepoTwin, PaperTwin, and alignment manifests.
It materializes no real manifests, scans no corpus, reads no bodies, writes no `/arxiv`, uploads nothing, runs no model, and trains nothing.

Manifest families:

- `domain_concept_manifest`
- `repo_twin_manifest`
- `paper_twin_manifest`
- `domain_twin_alignment_manifest`

Required anti-cheat fields:

- `id_is_opaque`
- `label_coded_id_absent`
- `target_label_absent_from_input`
- `raw_body_absent`
- `shortcut_baseline_required_before_training`
- `split_overlap_check_required`

Next: Audit this schema against existing compiler/gate-status contracts, then design a synthetic fixture-only validator before any real DomainGraph/Twin manifest materialization.

