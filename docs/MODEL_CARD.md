# AgentKernel Lite 100M Software Maintainer Model Card

Updated: 2026-07-10

## Summary

AgentKernel Lite 100M is a recovered research-stage software-maintenance student model and control stack. The intended role is not open-ended code generation. The model is meant to operate as a structured transition kernel over visible repository evidence, retrieval results, graph/context packets, verifier observations, and bounded edit or repair actions.

The project is now past 10,000 reconstructed/rebuilt stages. The current frontier is stage10136. At this point, the strongest useful work is evaluation validity, signoff completion, evidence packaging, and long-context dataset quality, not claiming a broadly capable coding model.

## Current Status

The current pushed repository state is:

- GitHub branch: `recovery/100m-maintainer-rebuild-20260704`
- Git commit: `dc251613ca02f171a3648fba6832af90ff63e3de`
- Latest model/eval frontier recorded here: stage10136
- Large train-ready dataset upload: `PeytonT/100m_swe_research_timeline`
- Uploaded dataset path: `strict_long_context_train_ready_v1/`
- Hugging Face commit: `a453c26909bcd9423eed9a79ce6b245cce14db56`

## Intended Use

This model stack is intended for research on software-maintenance subskills:

- evidence-grounded edit localization
- symbol, scope, import, and test relation grounding
- bounded patch/operator selection
- verifier failure diagnosis
- abstention when evidence is insufficient
- maintainer-style reasoning over retrieved long-context evidence

It should be used with deterministic gates, retrieval, static analysis, tests, and explicit authority checks. The learned model may propose an action; contracts and verifiers decide whether that action is allowed.

## Out-of-Scope Use

Do not treat the current 100M artifact as:

- a general-purpose replacement for Gemma-12B or other large coding models
- a validated autonomous coding agent
- a safe full-file generator
- a model with confirmed broad software-engineering intelligence
- a checkpoint whose benchmark wins can be claimed without the attached evidence cards

## Architecture Role

The target system is a multi-component maintainer stack:

```text
repo/user intent/logs/tests
-> structure extraction
-> retrieval and graph/context packaging
-> structured policy heads
-> bounded edit/operator prediction
-> bounded decode or denoise repair
-> verifier and safety gates
```

The 100M student should focus on semantic state transitions, structured decisions, bounded decoder arguments, and repair transforms after verifier feedback. It should not be forced to memorize repositories or infer repo-wide structure without context.

## Training And Data

The current long-context work separates dataset building from the 100M model-training task. The latest train-ready export was kept out of GitHub and uploaded to Hugging Face:

```text
PeytonT/100m_swe_research_timeline/strict_long_context_train_ready_v1/
```

That export includes JSONL rows, parquet exports, and dataset cards for strict long-context training. The largest local/generated artifacts remain intentionally untracked in Git because they are dataset payloads, not source code.

## Evaluation Status At Stage10136

Current comparison state:

- Stage10134 joined the standalone maintainer frontier and full-product harness frontier into one comparison spine.
- The standalone first wave has 8 true source-backed maintainer bundles.
- Stage10134 reports `standalone_first_wave_scoreable_now: 0`.
- The full-product harness side has 13 aligned cells and 4 canonical handoff cells, but harness claims remain separate until real runtime/writeback evidence exists.
- Stage10135 identified 4 high-risk rows for first review priority.
- Stage10136 tracks 8 bundles, all still pending rubric, anti-cheat, and gold-adjudication completion.

The most honest current statement is:

> The 100M system has shown narrow, provisional structured-surface wins in earlier edit-localization experiments, but the current true source-backed maintainer comparison is not scoreable yet. Stage10136 says all eight first-wave bundles still need human rubric, anti-cheat, and gold-adjudication completion before a credible 100M-vs-Gemma maintainer claim can be made.

## Known Limitations

- Current validated scope is narrow and structured.
- Earlier high edit-localization scores may include extraction, shortcut, or surface-alignment effects unless challenged by counterfactuals and blind review.
- Patch-operator and verifier-repair surfaces require executable candidate-action evidence and abstention handling before they should be used as intelligence claims.
- Same-manifest Gemma comparisons are useful only when the exact comparator, prompt surface, output parser, and scoring contract are frozen.
- Stage10136 still blocks the true source-backed first-wave comparison on missing human signoff fields.

## Required Evidence Before Strong Claims

Before claiming the 100M model beats Gemma-12B as a competent software maintainer, each claimed cell needs:

- frozen checkpoint/export/tokenizer/prompt/evaluator hashes
- exact Gemma comparator identity and runner configuration
- same-surface raw outputs
- expert-maintainer rubric review
- anti-cheat review
- perspective-gold adjudication
- shallow-baseline and metadata-only controls
- counterfactual and nuisance-transform audits
- root-clustered statistics on independent heldout cases

## Recommended Next Step

Work the stage10136 tracker, not another generic training sweep:

1. Fill rubric reviewer IDs and decision rationales.
2. Fill anti-cheat reviewer IDs and decision rationales.
3. Fill all perspective-gold answer fields for the 8 bundles.
4. Rerun stage10129 and stage10130.
5. Only then run the frozen standalone first-wave 100M-vs-Gemma comparison.
