# Stage9257 Repo-State Compiler Cache Metadata Fixture Audit

Stage9257 validates the Stage9256 cache manifest with synthetic metadata-only rows.

It does not read repository bodies, source files, `/arxiv`, runtime outputs, hidden evals, decoder targets, or training manifests.

The audit checks opaque IDs, cache-key uniqueness, invalidation fields, authority closure, and forbidden text leakage.

Rows: 10
Passed: True

Next: design a real extraction preflight that inventories metadata paths only before any source-body extraction is considered.
