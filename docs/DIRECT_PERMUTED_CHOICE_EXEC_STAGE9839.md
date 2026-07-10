# Stage9839 Direct Permuted Choice Exec

Passed: `True`
Runtime executed: `True`
Row artifacts present: `True`

This stage bypasses the outer trainer wrapper and runs the recovered structured training loop directly so the permuted-choice 100M run emits usable row-level artifacts.

Next: Use the Stage9839 row-level outputs as the 100M side of the permuted-choice multilingual comparison so the stronger anti-cheat packet can be judged per language rather than only by split.
