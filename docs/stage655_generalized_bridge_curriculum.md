# Stage655 Generalized Bridge Curriculum

Artifact: `runs/local/artifacts/stage655_generalized_bridge_curriculum.json`

Manifest: `runs/local/tmp/stage655_generalized_bridge_curriculum/agentkernel_lite_encdec_dataset_manifest.json`

## Purpose

Stage654 showed that Stage653 has enough entropy but is not learnable by direct continuation. Stage655 keeps the same verified unit set and bit accounting, then adds compact `gsel=` selectors by family:

- facts: `fact|domain|field|entity`
- relations: `rel|domain|relation|entity`
- two-hop: `compose2|domain|relation|field|entity`
- set counts: `setcount|domain|field|value`
- counterfactuals: `neg|domain|field|entity|claimed`
- exceptions: `exception|domain|field|entity`

## Stats

- Train rows: `55029`
- Eval rows: `48411`
- Train distinct selectors: `55029`
- Eval distinct selectors: `48411`
- Train avg query+doc whitespace tokens: `22.006378454996458`
- Eval avg query+doc whitespace tokens: `23.966185371093346`

## Next Gate

Run staged training or a full selectorized initialized probe. Acceptance is unchanged: no-filter generalized answer KBPP must clear `8.0`; hard-filter-only gains do not count.
