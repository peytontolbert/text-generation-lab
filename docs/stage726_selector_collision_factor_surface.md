# Stage726 Selector-Collision Factor Surface

Artifact: `runs/local/artifacts/stage726_selector_collision_factor_surface.json`

Manifest: `runs/local/tmp/stage726_selector_collision_factor_surface/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Train rows: `65882`
- Eval rows: `37558`
- Eval collision selectors: `1674`
- Eval rows in collision selectors: `37282`
- Mean/max eval candidate count per selector: `19.26051282051282` / `421`
- Perfect ceiling: `14.223615055503998` KBPP

## Change

Stage726 rewrites `gsel` from singleton row selectors to coarse collision selectors. The natural query/doc text still contains entity and value evidence, but the allowed key factor no longer uniquely isolates the row.

Acceptance requires factorized scoring to improve KBPP under these collisions. Full selector identity does not count.
