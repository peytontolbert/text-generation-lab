# Stage591 Anchored Membership Ablation

Dataset manifest: `runs/local/tmp/pocketpal_stage591_anchored_compact_membership_seed461/agentkernel_lite_encdec_dataset_manifest.json`

Analysis artifact: `runs/local/artifacts/stage591_anchored_membership_card_analysis.json`

## Purpose

Stage579 showed that compact membership cards were too compressed: `key + member + count` removed the entity and constraint anchors needed to separate near-neighbor proof cards. Stage591 adds an explicit `--anchored-compact-membership-cards` generator option to test the smallest safe membership-card format.

## Result

The analyzer compared:

- `stage461_full`
- `stage579_compact`
- `stage591_anchored`

Membership rows are identical in count across all three: `7840`.

Mean membership target length:

- Stage579 compact: `5.0` tokens
- Stage591 anchored: `10.56734693877551` tokens
- Stage461 full anchored: `10.56734693877551` tokens

Anchor completeness:

- Stage579 compact: `0.0`
- Stage591 anchored: `1.0`
- Stage461 full anchored: `1.0`

## Finding

There is no useful middle ground in the current membership proof-card text. The fields Stage579 removed are exactly the fields required for reliable binding. Restoring the anchors restores the original target length.

So the next route for membership KBPP is not shorter proof cards. It is one of:

- Keep anchored membership cards and improve the loss/evaluator around answer-equivalent proof swaps.
- Move deterministic operation/key filtering outside the neural parameter budget.
- Change membership supervision away from doc-level contrastive retrieval when the answer is only `member_true`/`member_false`.

This makes `anchored_compact_membership_v2` a design clarification rather than a new likely training win.
