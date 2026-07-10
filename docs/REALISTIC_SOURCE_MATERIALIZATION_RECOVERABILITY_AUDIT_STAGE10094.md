# Stage10094 Realistic Source Materialization Recoverability Audit

Passed: `True`
Request rows: `55`
Locked eval source rows: `18`
Unique normalized stage8765 roots: `32`

The requested realistic successor cannot honestly be called fully source-backed yet. Only 18 of the 55 compare-subset rows are already locked eval sources, and the shared repo-graph node/span lineage points to external `/arxiv/TOLBERT_BRAIN` files rather than a local materialized cache in this workspace.

Next: either materialize those repo-graph sources locally for the underlying 32 stage8765 roots, or narrow the next maintainer-grade successor to the 18 already locked-source rows until more real heldout roots are available.
