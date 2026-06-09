#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fmt_float(value: Any, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return ""


def _fmt_sci(value: Any) -> str:
    try:
        return f"{float(value):.6g}"
    except Exception:
        return ""


def _run_table(runs: list[dict[str, Any]]) -> str:
    lines = [
        "| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for run in runs:
        lines.append(
            "| {label} | {params:,} | {steps:,} | {top1} | {mrr} | {bpt} | {bmp} |".format(
                label=str(run.get("label", "")),
                params=int(run.get("params") or 0),
                steps=int(run.get("completed_steps") or run.get("steps") or 0),
                top1=_fmt_float(run.get("top1"), 4),
                mrr=_fmt_float(run.get("mrr"), 4),
                bpt=_fmt_sci(run.get("verified_bits_per_training_token")),
                bmp=_fmt_float(run.get("verified_bits_per_million_params"), 1),
            )
        )
    return "\n".join(lines)


def _best_by(runs: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    valid = [run for run in runs if run.get(key) is not None]
    return max(valid, key=lambda run: float(run.get(key) or 0.0)) if valid else None


def _latest_result_note(result: dict[str, Any]) -> str:
    if not result:
        return "No latest compact-reverse scale result note was supplied."
    lines: list[str] = []
    label = str(result.get("label", "")).strip()
    if label:
        lines.append(f"Latest result: `{label}`.")
    finding = str(result.get("finding", "")).strip()
    if finding:
        lines.append(finding)
    for key, value in result.items():
        if key in {"label", "finding"}:
            continue
        if isinstance(value, float):
            rendered = _fmt_sci(value) if abs(value) < 0.1 else _fmt_float(value, 6)
        else:
            rendered = str(value)
        lines.append(f"- `{key}`: `{rendered}`")
    return "\n".join(lines)


def build_doc(args: argparse.Namespace) -> str:
    budget = _load_json(args.budget_summary)
    residual = _load_json(args.residual_summary)
    curve = _load_json(args.curve_summary) if str(args.curve_summary).strip() else {"runs": []}
    semantic_ops = _load_json(args.semantic_ops_summary) if str(args.semantic_ops_summary).strip() else {"runs": []}
    semantic_ops_v2 = _load_json(args.semantic_ops_v2_summary) if str(args.semantic_ops_v2_summary).strip() else {"runs": []}
    semantic_ops_op_tokens = _load_json(args.semantic_ops_op_tokens_summary) if str(args.semantic_ops_op_tokens_summary).strip() else {"runs": []}
    semantic_binding = _load_json(args.semantic_binding_summary) if str(args.semantic_binding_summary).strip() else {"runs": []}
    extended_set_ops = _load_json(args.extended_set_ops_summary) if str(args.extended_set_ops_summary).strip() else {"runs": []}
    derived_set_ops = _load_json(args.derived_set_ops_summary) if str(args.derived_set_ops_summary).strip() else {"runs": []}
    factorized_direct = _load_json(args.factorized_direct_summary) if str(args.factorized_direct_summary).strip() else {"runs": []}
    rule_case_sets = _load_json(args.rule_case_summary) if str(args.rule_case_summary).strip() else {"runs": []}
    compact_reverse_scale = _load_json(args.compact_reverse_scale_summary) if str(args.compact_reverse_scale_summary).strip() else {"runs": []}
    moe = _load_json(args.moe_summary) if str(args.moe_summary).strip() else {"runs": []}
    budget_runs = list(budget.get("runs", []))
    residual_runs = list(residual.get("runs", []))
    curve_runs = list(curve.get("runs", []))
    semantic_ops_runs = list(semantic_ops.get("runs", []))
    semantic_ops_v2_runs = list(semantic_ops_v2.get("runs", []))
    semantic_ops_op_token_runs = list(semantic_ops_op_tokens.get("runs", []))
    semantic_binding_runs = list(semantic_binding.get("runs", []))
    extended_set_ops_runs = list(extended_set_ops.get("runs", []))
    derived_set_ops_runs = list(derived_set_ops.get("runs", []))
    factorized_direct_runs = list(factorized_direct.get("runs", []))
    rule_case_runs = list(rule_case_sets.get("runs", []))
    compact_reverse_scale_runs = list(compact_reverse_scale.get("runs", []))
    moe_runs = list(moe.get("runs", []))

    best_token = _best_by(budget_runs, "verified_bits_per_training_token")
    best_param = _best_by(budget_runs, "verified_bits_per_million_params")
    best_top1 = _best_by(budget_runs, "top1")
    residual_run = residual_runs[0] if residual_runs else {}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = []
    lines.extend(
        [
            "# Active Research: Tiny Model Semantic Compression",
            "",
            f"Last updated: {now}",
            "",
            "This document is generated from local run artifacts. It tracks how different model sizes learn from the same compiled semantic curriculum, how quickly they convert training tokens into verified knowledge access, and where the next experiments should spend compute.",
            "",
            "## Current Thesis",
            "",
            "Tiny models should not be judged only by decoder perplexity. For semantic compression work, the more useful measurement is whether a model can recover verified knowledge from a compressed representation under a fixed token, parameter, and compute budget.",
            "",
            "The current answer-card curriculum isolates one narrow but important primitive:",
            "",
            "```text",
            "query: domain + entity + field",
            "target: retrieve the exact answer card",
            "metric: verified answer-card access",
            "```",
            "",
            "This is intentionally not open-ended generation. It measures whether training created a clean semantic access geometry.",
            "",
            "## Metric Definitions",
            "",
            "Verified bits are currently approximated as:",
            "",
            "```text",
            "verified_bits = correct_retrievals * log2(unique_eval_answer_cards)",
            "```",
            "",
            "Training-token efficiency is estimated as:",
            "",
            "```text",
            "verified_bits_per_training_token = verified_bits / estimated_retrieval_training_tokens",
            "```",
            "",
            "Parameter efficiency is estimated as:",
            "",
            "```text",
            "verified_bits_per_million_params = verified_bits / (parameters / 1_000_000)",
            "```",
            "",
            "These are proxy metrics, not final intelligence metrics. They are useful because they let us compare model size, training budget, and curriculum quality on the same semantic access task.",
            "",
            "## Stage429 Budget Ladder",
            "",
            _run_table(budget_runs),
            "",
            "## Current Read",
            "",
        ]
    )
    if best_token:
        lines.append(
            f"- Best measured token-efficiency point: `{best_token.get('label')}` with `{_fmt_sci(best_token.get('verified_bits_per_training_token'))}` verified bits/token."
        )
    if best_param:
        lines.append(
            f"- Best measured parameter-density point: `{best_param.get('label')}` with `{_fmt_float(best_param.get('verified_bits_per_million_params'), 1)}` verified bits/Mparam."
        )
    if best_top1:
        lines.append(
            f"- Best raw retrieval point in this table: `{best_top1.get('label')}` with `{_fmt_float(best_top1.get('top1'), 4)}` top1."
        )
    lines.extend(
        [
            "- The 100-step runs are much more token-efficient than the 400-step runs. Longer training improves raw top1 modestly, but spends many extra tokens after the model has already learned most of the answer-card geometry.",
            "- The useful scale band for this curriculum is currently `100k-1m` parameters. Below that, the model underfits; above that, this task saturates and parameter efficiency collapses.",
            "- The nominal `1k` rung is not a true 1k model with the current BPE vocabulary. Embeddings alone force the actual count above 12k. A true 1k experiment needs a tiny character or micro-symbol vocabulary.",
            "",
            "## Residual Replay Result",
            "",
            "| run | params | top1 | MRR | verified bits/token |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    if residual_run:
        lines.append(
            "| {label} | {params:,} | {top1} | {mrr} | {bpt} |".format(
                label=str(residual_run.get("label", "")),
                params=int(residual_run.get("params") or 0),
                top1=_fmt_float(residual_run.get("top1"), 4),
                mrr=_fmt_float(residual_run.get("mrr"), 4),
                bpt=_fmt_sci(residual_run.get("verified_bits_per_training_token")),
            )
        )
    lines.extend(
        [
            "",
            "Residual replay was built from train-side retrieval failures, not held-out eval failures. For the `100k` model, this raised held-out top1 from `0.8915` to `0.9674`, effectively matching the `1m-100` result with about one-fifth the parameters.",
            "",
            "This supports the recursive semantic compression loop:",
            "",
            "```text",
            "train -> probe -> identify residual failures -> replay residual -> probe again",
            "```",
            "",
            "## 100k Budget Curve",
            "",
            _run_table(curve_runs) if curve_runs else "_No 100k budget curve artifact supplied._",
            "",
            "The 100k curve shows a useful distinction between two objectives:",
            "",
            "- If optimizing verified bits per training token, the earliest budget point is best so far: `100k-50` reached `0.0109` verified bits/token.",
            "- If optimizing raw answer-card accuracy, longer training helps but with diminishing returns: `100k-400` reached `0.9715` top1.",
            "- If optimizing practical capability under a small compute budget, `100k-100` followed by residual replay is currently better than uniform continuation, because it reaches `0.9674` top1 after targeted replay instead of spending the same pressure everywhere.",
            "",
            "## Stage430 Semantic Operations",
            "",
            _run_table(semantic_ops_runs) if semantic_ops_runs else "_No Stage430 semantic-ops artifact supplied._",
            "",
            "Stage430 broadens the target beyond answer-card lookup. It includes direct facts, reverse lookup, false-claim rejection, default rules, exceptions, and two-hop owner-region composition. Retrieval-style semantic access remains strong, but direct free decoding is still weak:",
            "",
            "| model | direct pass@256 | mean recall | note |",
            "|---|---:|---:|---|",
            "| 100k Stage430 structured target | 0.0625 | 0.1536 | Decoder collapses to common entity-like strings. |",
            "| 1M Stage430 structured target | 0.1289 | 0.2114 | Better, but still far below retrieval access. |",
            "| 1M Stage431 content-only target | 0.1523 | 0.2249 | Removing the JSON envelope helps only slightly. |",
            "",
            "Interpretation: the encoder/retrieval geometry is learning semantic structure much faster than the autoregressive decoder learns reliable answer emission. For tiny models, the current evidence favors app-side structure plus a verified semantic access path, then a much cleaner constrained answer decoder later.",
            "",
            "## Stage432 Cleaned Reverse Lookup",
            "",
            _run_table(semantic_ops_v2_runs) if semantic_ops_v2_runs else "_No Stage432 cleaned semantic-ops artifact supplied._",
            "",
            "Stage432 fixes a Stage430 curriculum flaw: reverse lookup is now set-valued when multiple entities share the same field value. The old single-entity reverse lookup penalized semantically valid alternatives. After this cleanup, dense `100k` improves to `0.9702` top1, the routed residual adapter improves to `0.9796` top1, and residual replay reaches `0.9890` top1. The remaining misses are mostly direct field/card confusions and harder reverse-set confusions, not false negatives from ambiguous labels.",
            "",
            "## Stage433-Stage440 Operation Tokens And Residual Replay",
            "",
            _run_table(semantic_ops_op_token_runs) if semantic_ops_op_token_runs else "_No Stage433 operation-token artifact supplied._",
            "",
            "Stage433 prefixes retrieval queries and docs with explicit operation tokens such as `<AK_OP_DIRECT_FACT>` and `<AK_OP_REVERSE_LOOKUP_SET>`. The first version treated those markers as ordinary text and was not a compression win: first-stage top1 tied Stage432 at `0.9796`, replay reached `0.9874`, and average retrieval-pair length rose to `105.4` tokens. Stage434 moves the same operation markers into the AgentKernel special-token library, making them atomic tokenizer symbols. That turns the idea positive: first-stage top1 reaches `0.9922`, residual replay reaches `0.9937`, and average retrieval-pair length falls to about `87.9` tokens. Stage435-437 add explicit router-operation supervision and Stage438 adds a mutual-information router objective. All four router-shaping runs reduce first-stage top1 to `0.9906`, so the current default remains compact operation tokens without router CE or MI regularization. Stage439 then applies a second recursive residual replay pass from the Stage434 replay checkpoint, improving held-out top1 to `0.9953`; Stage440 applies a third smaller pass and plateaus at the same held-out score. The remaining misses are concentrated in set-valued reverse lookup, so the next curriculum change should target inverse-set representation directly rather than continue generic replay.",
            "",
            "## Stage441-Stage444 Binding Keys",
            "",
            _run_table(semantic_binding_runs) if semantic_binding_runs else "_No Stage441-444 binding-key artifact supplied._",
            "",
            "Stage441 adds a compact `lookup_key=domain|field|answer` only to reverse lookup rows. This increases average retrieval-pair length from about `87.9` to `96.1` tokens, so it is not free, but it directly attacks the remaining inverse-set ambiguity. From scratch, Stage441 matches the old Stage434 replay top1 and improves reverse-set behavior. Stage442 then applies one residual replay pass and becomes the new best checkpoint at `0.9969` top1 / `0.9982` MRR. Only two held-out pairs remain wrong: one direct field binding and one reverse-set domain jump.",
            "",
            "Stage443 tests a broader `semantic_key=...` prefix for every operation. It makes direct facts perfect from scratch, but it raises average retrieval-pair length to about `123.4` tokens and does not improve reverse-set accuracy. Stage444 replay does not improve held-out top1. The useful lesson is narrow keying: add composite binding keys only where the target is structurally ambiguous. Broad semantic keys spend too many tokens on already-solved operations.",
            "",
            "## Stage445-Stage447 Extended Set Operations",
            "",
            _run_table(extended_set_ops_runs) if extended_set_ops_runs else "_No Stage445-446 extended-set artifact supplied._",
            "",
            "Stage445 expands the curriculum from lookup to set use by adding `set_count` and `set_member` operations over the reverse lookup sets. This is a harder and more general semantic task because the model must retrieve cards that encode derived properties of a compressed set, not only direct facts. The 85k-parameter routed residual model reaches `0.9974` top1 / `0.9987` MRR on 1,163 held-out pairs. Direct facts, reverse lookup sets, rules, exceptions, false claims, and two-hop composition are perfect; the remaining errors are in the new set-count and set-member operations. Stage446 residual replay plateaus at the same held-out score, so the bottleneck is target design rather than exposure.",
            "",
            "Stage447 makes the count/member cards more compressed by removing the distracting full entity list from derived set-operation targets. That change reaches `1.0000` top1 / `1.0000` MRR across all eight operations while also lowering average retrieval-pair length from about `101.9` to `97.8` tokens. This is the cleanest current evidence for the core tiny-model rule: once the semantic operation is defined, remove target fields that do not directly supervise the intended reusable state.",
            "",
            "## Stage448-Stage452 Derived Set Intersections",
            "",
            _run_table(derived_set_ops_runs) if derived_set_ops_runs else "_No Stage448-450 derived-set artifact supplied._",
            "",
            "Stage448 adds `set_intersection_count` and `set_intersection_member`, requiring the model to bind two field constraints at once. The 87k-parameter routed residual model reaches `0.9986` top1 / `0.9993` MRR on 1,474 held-out pairs and is perfect on both new intersection operations. The remaining errors are direct field-binding errors where the same entity card is retrieved with the wrong answer field.",
            "",
            "Stage449 tests a narrow `fact_key=direct_fact|domain|entity|field` prefix for direct facts. It improves direct facts slightly but hurts `rule_default`, so it is not the default. Stage450 replays Stage448 train residuals and also fails to improve total held-out top1, trading errors across slices. Stage451 compacts direct fact cards to only the queried field and answer; this lowers local eval loss but is also not a top1 win, because it hurts reverse lookup while leaving direct facts at the same held-out accuracy as Stage448. Stage452 keeps the full direct card but prefixes `selected_field` and `selected_answer`; it ties Stage448 on verified access and has lower eval loss, but still does not remove the direct-field residual. The current lesson is that the intersection operation is learnable with clean compact cards, while direct fact access probably needs a separate value-selector/card-factorization path rather than more prefixes or shorter direct cards.",
            "",
            "## Stage453-Stage459 Factorized Direct Access",
            "",
            _run_table(factorized_direct_runs) if factorized_direct_runs else "_No Stage453-459 factorized-direct artifact supplied._",
            "",
            "Stage453 factorizes direct facts into compact value cards and separate `entity_context` cards. This makes direct facts and entity context perfect, while exposing a `rule_default` weakness. Stage454 compacts rule cards but shifts errors into entity/reverse/rule slices. Stage455 residual replay from Stage453 improves the factorized branch, but still leaves default-rule misses.",
            "",
            "Stage456 keeps factorized direct cards and adds a narrow `rule_key=op|domain|entity|field` prefix only for rule/default and exception rows. This is the best 87k-scale result so far on the 11-operation curriculum: `0.9993` top1 / `0.9997` MRR, with every slice perfect except one direct-field miss. Stage457 adds direct fact keys too and fixes direct facts, but shifts errors into false-claim and reverse lookup. Stage458 mild replay from Stage456 does not clear the final direct miss.",
            "",
            "Stage459 scales the Stage456 target design to the `1m` preset, which is 515,872 actual parameters with this vocabulary and configuration. It reaches `1.0000` top1 / `1.0000` MRR across all 11 operations. This is a useful scale-map point: the final 87k miss appears to be representation-resolution limited under this architecture, not primarily a target-design flaw.",
            "",
            "## Stage460-Stage464 Rule Case Sets And Composed Rule Intersections",
            "",
            _run_table(rule_case_runs) if rule_case_runs else "_No Stage460 rule-case artifact supplied._",
            "",
            "Stage460 adds rule-derived set operations over default and exception groups: `rule_case_count` and `rule_case_member`. This tests whether the model can treat rules as compressed set generators, then answer derived membership/count questions without storing every case as an unrelated fact. With factorized direct value cards, `entity_context`, compact set-operation cards, derived intersections, and narrow rule keys, the 88,896-parameter routed residual model reaches `1.0000` top1 / `1.0000` MRR across all 13 operations.",
            "",
            "Stage461 then composes rule cases with a second field constraint through `rule_case_intersection_count` and `rule_case_intersection_member`. The new composed operations are perfect even at about 90k parameters, but the extra curriculum pressure exposes older reverse-set and composition residuals. Scaling the same target to the 1m preset in Stage462 raises exact-card top1 to `0.9986` and answer-equivalent top1 to `0.9995`. The remaining exact-card set-intersection-member misses are all `member=false` proof-card swaps, so exact retrieval is over-penalizing a low-information negative detail that would not change the emitted answer.",
            "",
            "Stage463-Stage464 test a narrow `composition_key` for two-hop rows. At 523k parameters it fixes the two-hop slice but shifts one answer miss into `reverse_lookup_set`, so by itself it is not a clear default. Stage465 makes membership targets fully generic (`op + member=true/false`) and fails badly because duplicate answer cards make doc-level contrastive retrieval ill-conditioned. Stage466 keeps unique membership proof keys but removes repeated fields; it is also not a net win.",
            "",
            "Stage469-Stage470 instead compact bulky `reverse_lookup_set` cards by keeping the lookup key and count while omitting the raw entity list from retrieval text. Combined with the two-hop composition key, Stage470 reaches `1.0000` answer-equivalent top1 across 2,088 held-out examples at 522,784 parameters. Exact-card top1 remains `0.9986`, but the remaining exact misses are answer-equivalent `member=false` proof-card swaps. Interpretation: compact rule-case cards did not reintroduce rule/default ambiguity, rule-derived set composition works, and the best current target design separates answer access from bulky proof payloads for reverse sets while keeping unique proof keys for membership operations.",
            "",
            "## Stage469+ Compact Reverse, Direct-Key, False-Claim, And Rule-Card Scale Ladder",
            "",
            _run_table(compact_reverse_scale_runs) if compact_reverse_scale_runs else "_No Stage469-472 compact-reverse scale artifact supplied._",
            "",
            _latest_result_note(dict(compact_reverse_scale.get("latest_result", {}) or {})),
            "",
            "The compact-reverse scale ladder now maps a much sharper breakpoint for the current best composed target. The nominal `1k` preset is 7,604 actual parameters because the tokenizer and heads dominate; it reaches only `0.3755` exact top1, though it already learns some count/member geometry. The nominal `10k` preset is 16,280 parameters and can reach `0.9966` answer top1 after continuation. The 20,946-parameter and 23,369-parameter rungs both plateau at one semantic miss under replay, hard negatives, answer contrast, and operation routing. The 25,852-parameter `d_model=12` rung is the current smallest answer-perfect checkpoint.",
            "",
            "Stage540+ adds a stricter retrieval metric: full-corpus ranking within the structured operation namespace. This is harder than the earlier batch-local metric and exposes residual same-operation confusions that batch-local eval can miss. Model-mined same-operation negatives are positive under this stricter metric: Stage542 improves the 25,852-param rung from five strict answer misses to two, while preserving batch-local structured answer-perfect behavior. The remaining strict misses are rank-2 entity/two-hop confusions, so the next training target should mine fresh residual negatives from Stage542 or add a lightweight reranker rather than broad replay.",
            "",
            "Stages490-498 refine that breakpoint. Adding `fact_key=direct_fact|domain|entity|field` moves answer-perfect access from the 522,784-parameter rung down to 60,328 parameters after 600 total steps. A narrower `false_claim_card` that contains only `field`, `claimed`, and `correct` then moves answer-perfect access down again to 36,384 parameters after 900 total steps. The important lesson is not that larger models are unnecessary; it is that target entropy and operation-specific binding fields directly control how much parameter width is needed for verified semantic access.",
            "",
            "Interpretation: the curve is not a smooth facts-per-parameter line. There is a visible representation-width threshold for reliable key binding, but the threshold is movable. Once the model has enough width to represent composite keys, compact target design converts quickly into verified access; when an operation keeps irrelevant fields in its target, the model spends scarce width on the wrong binding problem.",
            "",
            "## Dense vs MoE Probe",
            "",
            _run_table(moe_runs) if moe_runs else "_No dense-vs-MoE artifact supplied._",
            "",
            "Current read: replacing the tiny encoder MLP with experts is the wrong MoE move, but dense plus a small routed residual adapter is promising. Stage442 remains the cleanest narrow semantic-ops result at `0.9969` top1. Stage447 is the best expanded-curriculum result: it reaches perfect held-out retrieval across direct access, inverse sets, set count/member, rules, exceptions, false claims, and two-hop composition. A fixed load-balance metric makes router usage much healthier without hurting first-stage top1, but Stage435-438 show that explicit router shaping, including mutual-information routing, is too blunt. The next MoE target is harder schema/curriculum design, not more router regularization.",
            "",
            "## Model Size Learning Map",
            "",
            "| scale band | observed behavior | current interpretation | next experiment |",
            "|---|---|---|---|",
            "| 10k-30k actual params | Learns some structure but not reliable access. `10k-100` reached 44.8%; `10k-400` reached 73.7%. | Useful as a lower-bound geometry probe. Too small for robust answer-card binding with this tokenizer. | Try smaller vocab/macro-token version to see whether embedding overhead is the bottleneck. |",
            "| 100k actual params | Learns fast. `100k-100` reached 89.1%; residual replay reached 96.7%. | Best current research scale for mapping token efficiency and residual compression. | Automate residual replay and test 50/75/125/150-step schedules. |",
            "| 1M actual params | Nearly saturates after 100 steps. | Good target when reliability matters more than parameter density. | Test harder compositional cards where 100k no longer saturates. |",
            "| 10M actual params | Same top1 as 1M on this task, much worse parameter efficiency. | Overcapacity for this curriculum. | Use only when the curriculum becomes multi-hop, schema/rule/program-heavy, or decoder-coupled. |",
            "| 100M production branches | Strong decoder app behavior, weak answer-card retrieval unless explicitly trained. | Existing 100M weights learned language/controller behavior, not this semantic-card access geometry. | Add sidecar retrieval or train protected retrieval heads without perturbing decoder. |",
            "",
            "## What This Means For Training",
            "",
            "The current evidence favors treating small-model training as a measurement-controlled compression process:",
            "",
            "1. Choose a semantic primitive, such as answer-card retrieval.",
            "2. Train a size ladder with a short budget.",
            "3. Compute verified bits/token and bits/parameter.",
            "4. Identify the best scale band.",
            "5. Probe failures and create residual replay.",
            "6. Stop or move up scale only when residual replay no longer gives cheap bits.",
            "",
            "This is different from ordinary large-model training. We are not asking every scale to consume the same huge stream. We are finding which scale extracts the most verified structure per token, then feeding it only the residual structure it failed to compress.",
            "",
            "## Next Experiments",
            "",
            "- Add 50/75/125/150-step budget points for the `100k` rung to locate the token-efficiency peak more accurately.",
            "- Replace the completed 50/75/125/150-step manual curve with automatic budget sweeps for every promising scale band.",
            "- Add automatic residual replay rounds and stop when marginal verified bits/token falls below a threshold.",
            "- Build a true micro-vocab or character-level `1k` experiment to remove BPE embedding overhead.",
            "- Build a harder Stage430 curriculum with schema, rule, exception, and two-hop answer cards so `1m` and `10m` have room to show useful capacity.",
            "- Redesign answer decoding as constrained class/value selection or pointer/copy from retrieved cards, because free autoregressive answer generation is currently the bottleneck.",
            "- Keep dense-vs-MoE in the sweep, but focus on routed residual adapters and compare them on Stage430 semantic operations instead of replacing the whole tiny MLP with experts.",
            "- Keep narrow reverse-lookup binding keys and avoid broad semantic keys unless token overhead is reduced by a tokenizer macro.",
            "- Move beyond solved compact set-count/member cards into harder derived operations: set intersection, grouped counts, exception-aware counts, and multi-field filters.",
            "- Stop adding router-operation pressure for this curriculum. Stage435-438 made routing cleaner but reduced retrieval accuracy; the next gain should come from target/schema design.",
            "- Transfer the access path back to the production model as a protected sidecar/retrieval head instead of forcing the free decoder to emit knowledge JSON.",
            "",
            "## Source Artifacts",
            "",
            f"- Budget summary: `{args.budget_summary}`",
            f"- 100k curve summary: `{args.curve_summary}`",
            f"- Stage430 semantic ops summary: `{args.semantic_ops_summary}`",
            f"- Stage432 cleaned semantic ops summary: `{args.semantic_ops_v2_summary}`",
            f"- Stage433/Stage434 operation-token summary: `{args.semantic_ops_op_tokens_summary}`",
            f"- Stage441-444 binding-key summary: `{args.semantic_binding_summary}`",
            f"- Stage445-447 extended-set summary: `{args.extended_set_ops_summary}`",
            f"- Stage448-452 derived-set summary: `{args.derived_set_ops_summary}`",
            f"- Stage453-459 factorized-direct summary: `{args.factorized_direct_summary}`",
            f"- Stage460-464 rule-case/intersection summary: `{args.rule_case_summary}`",
            f"- Stage469+ compact-reverse scale summary: `{args.compact_reverse_scale_summary}`",
            f"- Dense-vs-MoE summary: `{args.moe_summary}`",
            f"- Residual summary: `{args.residual_summary}`",
            "- Run ledger: `runs/ledgers/pocketpal_seq2seq_runs.jsonl`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-summary", required=True)
    parser.add_argument("--residual-summary", required=True)
    parser.add_argument("--curve-summary", default="")
    parser.add_argument("--semantic-ops-summary", default="")
    parser.add_argument("--semantic-ops-v2-summary", default="")
    parser.add_argument("--semantic-ops-op-tokens-summary", default="")
    parser.add_argument("--semantic-binding-summary", default="")
    parser.add_argument("--extended-set-ops-summary", default="")
    parser.add_argument("--derived-set-ops-summary", default="")
    parser.add_argument("--factorized-direct-summary", default="")
    parser.add_argument("--rule-case-summary", default="")
    parser.add_argument("--compact-reverse-scale-summary", default="")
    parser.add_argument("--moe-summary", default="")
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    output = Path(args.output_md)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_doc(args), encoding="utf-8")
    print(json.dumps({"output_md": str(output), "bytes": output.stat().st_size}, sort_keys=True))


if __name__ == "__main__":
    main()
