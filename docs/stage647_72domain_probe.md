# Stage647 72-Domain Probe

Artifact: `runs/local/artifacts/stage647_72domain_probe_summary.json`

Bundle: `runs/local/artifacts/knowledge_compression_moe_residual_10k_stage647_stage646_72domain_probe_lr1e6_steps80`

## Result

Stage647 is the first run in this branch to clear the 2x answer-KBPP gate on an entropy-expanded, collision-conditioned surface.

- Source Stage643 answer bits/param: `1.595657962063062`
- 2x target: `3.191315924126124`
- Stage647 no-filter answer bits/param: `3.7877684148748996`
- Multiple vs Stage643: `2.373797207753477`
- No-filter exact/answer: `0.9059350503919373` / `0.9290780141843972`
- Hard-filter exact/answer: `0.9977603583426652` / `0.9983202687569989`
- Hard-filter corrections/damage: `492` / `0`
- Multiple-candidate hard-filter queries: `1423`

## Decision

`accepted_first_2x_answer_kbpp_on_entropy_expanded_collision_surface`

## Finding

A short 80-step 16k continuation from Stage636 on the Stage646 72-domain collision-conditioned selector surface reaches 3.7877684148748997 no-filter answer bits/param, clearing the 2x Stage643 target of 3.191315924126124. The gain comes from adding verified entropy and preserving compact binding selectors, not from agentic behavior or parameter growth. Hard filtering remains an access-layer ceiling and corrects 492 rows with zero damage, but the pure neural no-filter result already clears the doubling gate.

## Next Steps

1. Run a matched from-scratch or Stage525-init control to separate checkpoint transfer from surface design.
2. Continue to 150-300 steps only if entity_context and two-hop improve without direct_fact regression.
3. Run the 1k/10k/100k sweep on Stage646 to map the new KBPP density knee.
