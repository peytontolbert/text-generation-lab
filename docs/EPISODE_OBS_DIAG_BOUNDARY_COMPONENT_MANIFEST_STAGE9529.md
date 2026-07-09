# Stage9529 Episode Observation Diagnosis Boundary-Component Manifest

Passed: `True`
Rows: `58`
Split counts: `{'train': 46, 'eval': 6, 'strict_eval': 6}`
Component family counts: `{'prefix_only_components': 16, 'no_failure_components': 29, 'prefix_and_boundary_components': 13}`
Loss counts: `{'episode_failure_type_ce': 58}`

This patch targets the remaining Stage9528 eval failure-type miss by exposing observation-derived boundary-component salience while training only the failure-type head.
