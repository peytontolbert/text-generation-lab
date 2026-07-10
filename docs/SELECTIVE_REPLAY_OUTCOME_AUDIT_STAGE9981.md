# Stage9981 Selective Replay Outcome Audit

Passed: `True`
Decision: Selective replay recovered part of the broad-replay regression without restoring the original stage9965 baseline, and none of the 11 Gemma-advantage review rows became correct under the replayed stage9980 run.

Next: Stop treating the 11 Gemma-advantage rows as ordinary positive replay data; route them into expert-maintainer and anti-cheat review, keep the web and rust anchors intact, and only consider new training after the review packet decides whether the python and c_cpp rows are identifiable expert-maintainer tasks or invalid/eval-hack candidates.
