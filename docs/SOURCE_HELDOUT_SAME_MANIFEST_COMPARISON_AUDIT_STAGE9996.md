# Stage9996 Source-Heldout Same-Manifest Comparison Audit

Passed: `True`
Comparison rows: `38`
Macro exact 100M: `0.5055555555555555`
Macro exact Gemma: `0.19305555555555556`
Wins: `100M 2`, `Gemma 0`, `ties 2`

Recomputed the 100M-versus-Gemma comparison on the source-heldout subset that excludes eval rows whose source roots also appear in train.

Next: Treat this source-heldout comparison as the honest current baseline, then rebuild future eval manifests so Python and c_cpp have more independent heldout roots.
