# Stage9287 Generation Audit Split Selector Patch

Stage9287 adds `--generation-audit-splits` for diagnostic generation audits.

Passed: True
Default remains `eval,strict_eval`; train generation is only included when explicitly requested.
No execution or training authority is opened by this patch.
