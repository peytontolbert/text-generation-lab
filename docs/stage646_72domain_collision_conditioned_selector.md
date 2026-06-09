# Stage646 72-Domain Collision-Conditioned Selector

Artifact: `runs/local/artifacts/stage646_72domain_collision_conditioned_selector_dataset.json`

Dataset manifest: `runs/local/tmp/stage646_72domain_collision_conditioned_selector/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Rewritten rows: train `22855`, eval `3209`
- Eval target rows: `3209`
- Eval collision rows: `1423`
- Eval mean/max candidate count: `1.3415551839464883` / `6`

## Eval By Operation

```json
{
  "direct_fact": {
    "collision_rows": 494,
    "groups": 401,
    "groups_with_collisions": 209,
    "max_candidate_count": 6,
    "mean_candidate_count": 1.7107231920199502,
    "rows": 686
  },
  "entity_context": {
    "collision_rows": 568,
    "groups": 408,
    "groups_with_collisions": 224,
    "max_candidate_count": 4,
    "mean_candidate_count": 1.8431372549019607,
    "rows": 752
  },
  "rule_case_intersection_count": {
    "collision_rows": 137,
    "groups": 335,
    "groups_with_collisions": 64,
    "max_candidate_count": 4,
    "mean_candidate_count": 1.217910447761194,
    "rows": 408
  },
  "rule_case_intersection_member": {
    "collision_rows": 100,
    "groups": 755,
    "groups_with_collisions": 50,
    "max_candidate_count": 2,
    "mean_candidate_count": 1.0662251655629138,
    "rows": 805
  },
  "set_intersection_member": {
    "collision_rows": 60,
    "groups": 439,
    "groups_with_collisions": 30,
    "max_candidate_count": 2,
    "mean_candidate_count": 1.0683371298405466,
    "rows": 469
  },
  "two_hop_owner_region": {
    "collision_rows": 64,
    "groups": 54,
    "groups_with_collisions": 29,
    "max_candidate_count": 4,
    "mean_candidate_count": 1.6481481481481481,
    "rows": 89
  }
}
```

## Decision

`stage646_collision_conditioned_selector_ready_for_16k_probe`

## Finding

Stage646 coarsens exact structured keys on the Stage645 entropy-expanded selector surface. This preserves domain|field|entity as neural binding evidence while making hard-filter candidate sets non-singleton.
