# Stage10097 Locked Source Graph Materialization Bridge Request

Passed: `True`
Rows: `18`
Languages: `{'c_cpp': 12, 'python': 6}`

This stage does not materialize maintainer evidence yet. It enumerates the opaque query-node and candidate-family handles that must be resolved from the external repo graph before the locked-source subset can become a real failure/trace/snippet packet.

Next: Implement a bridge that joins these opaque query and candidate handles against the external repo graph, emits concrete candidate paths and snippet spans, and then rebuilds the realistic maintainer packet from those outputs.
