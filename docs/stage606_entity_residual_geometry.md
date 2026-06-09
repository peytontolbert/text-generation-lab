# Stage606 Entity Residual Geometry

Artifact: `runs/local/artifacts/stage606_entity_residual_geometry.json`

## Result

Stage606 analyzes Stage602's remaining `entity_context` failures on the Stage601 field-level eval surface.

- Entity rows: `288`
- Exact misses: `142`
- Answer misses: `135`
- Answer misses with same predicted field: `40`
- Answer misses with same predicted entity: `48`
- Answer misses with same predicted domain: `103`
- Answer miss median score margin: `-0.023318469524383545`

## Decision

`entity_residual_geometry_mapped`

## Finding

The remaining entity_context failures are mostly cross-field and cross-entity binding errors, not just exposure deficits. Among answer misses, same-field predictions are a minority, and the model often predicts high-frequency tool/capital/owner fields for priority/status/currency targets. The next schema should strengthen field role binding or add a deterministic field selector before neural entity-value resolution.
