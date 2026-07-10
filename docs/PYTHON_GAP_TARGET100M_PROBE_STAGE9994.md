# Stage9994 Python Gap Target100M Probe

Passed: `True`
Rows: `119`

Ran the direct target-100M probe on the minimal Python-gap successor manifest from Stage9993.

Outcome:
- Eval exact: `0.3181818181818182` on `44`
- Strict exact: `0.30303030303030304` on `33`
- Python exact: `0.2857142857142857` on `14`

Frontier assessment:
- This regressed versus Stage9987 on aggregate eval, aggregate strict, and web/rust per-language performance.
- The two remaining Python Gemma-advantage eval rows stayed wrong.

Next:
Do not promote this replay into the frontier. Preserve it as negative evidence and only rerun Gemma on this manifest if we explicitly need a same-manifest failure packet.
