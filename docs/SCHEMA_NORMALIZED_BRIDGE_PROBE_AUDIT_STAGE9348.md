# Stage9348 Schema-Normalized Bridge Probe Audit

Passed: `False`
Safety gate passed: `True`
Quality gate passed: `False`
Exact match rows: `14` / `31`
Target-prefix rows: `14` / `31`
Boundary next-token rows: `31` / `31`
Contentful rows: `14` / `31`
Degenerate repetition rows: `17`
Error counts: `{'degenerate_repetition': 17, 'operator_operatch_repetition': 17, 'operator_terminal_bridge_failure': 17}`

Dependency-handle `keeps the` rows and file-path `localized edit` rows now pass exactly. The remaining failure is isolated to route_1 patch-operator rows, which repeat `operatch` before ending with `operator`.

Safety held: decoder CE, runtime, harness, Gemma, scoring, promotion, and checkpoint export stayed closed.
