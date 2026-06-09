# Stage659 Balanced Generalized 8 KBPP Surface

Artifact: `runs/local/artifacts/stage659_balanced_generalized_8kbpp_surface.json`

Manifest: `runs/local/tmp/stage659_balanced_generalized_8kbpp_surface/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Train units: `65882`
- Eval units: `37558`
- Hidden eval bits: `231560.4531036051`
- Perfect ceiling: `14.223615055503998` KBPP
- Target margin: `101320.4531036051` bits (`1.7779518819379998`x)

## Change

Stage659 corrects the Stage653/655 split. It no longer holds out whole field families such as `risk` or `tool`. Every schema family appears in train; eval holds out bindings, entities, relations, set counts, compositions, parameters, and API names.

The retrieval rows keep Stage655-style compact `gsel=` selectors. Acceptance still requires no-filter generalized answer KBPP `>= 8.0`.
