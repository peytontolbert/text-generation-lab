# Training Tiny Details Contract

These are small implementation details that materially affect whether a 100M probe is meaningful.

## Input Serialization

The model input must not include:

- `row_id`
- query/node/graph IDs
- target labels
- decoder targets
- raw source paths as label proxies

The model input may include structured evidence:

- objective family
- route
- language family
- input state fields
- model input fields
- query kind
- query shape features
- graph node type counts
- graph edge type counts
- graph node feature counts

Reason: row IDs and opaque IDs can become perfect memorization channels, while graph features are the intended evidence surface.

## Target Fallback

Decoder targets must come from explicit decoder target fields:

- `target.decoder_text`
- `decoder_text`
- `target.target_ref`
- `target_ref`
- `target.label`

They must never fall back to `row_id`.

Empty decoder targets must fail the bounded decoder contract before training.

## Loss Routing

Every row must carry a `loss_mask`.

Allowed examples:

- `symbol_binding_probe`: only `symbol_binding_ce`
- `edit_localization_probe`: only `edit_localization_ce`
- `patch_operator_probe`: only `patch_operator_ce`
- `verifier_repair_probe`: only `verifier_repair_ce`
- `bounded_decoder_ce_probe`: only `decoder_ce`
- `denoise_repair_probe`: only `denoise_ce`

Forbidden unless explicitly authorized:

- decoder CE in structured probes
- denoise CE outside denoise probes
- runtime reward in all recovered probes

## Counterfactual Obligations

Structured manifests need sibling groups before training.

Default required obligations:

- `POSITIVE_ORIGINAL`
- `EVIDENCE_REMOVED_OR_RETRIEVE`
- `CONTRASTIVE_BOUNDARY_SIBLING`

Guard-style manifests use the stricter legacy set:

- `POSITIVE_ORIGINAL`
- `EVIDENCE_REMOVED`
- `CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN`
- `MIXED_REPLAY`

The trainer now has `--require-counterfactual-obligation-audit` for contract-only validation. Real compiler manifests still need materialized sibling rows.

## Manifest Locking

Trainer contract cards must record:

- `manifest_sha256`
- row IDs loaded
- split counts
- loss counts
- authority row counts
- unsafe loss row examples

Remaining missing piece:

- schema hash / registry lock tying a manifest to the exact row schema and objective registry version.

## Decoder CE Contract

Bounded decoder CE rows must satisfy:

- non-empty decoder target
- target length within cap
- only `decoder_ce` loss enabled
- no authority flags
- no final checkpoint export
- cleanup policy declared
- telemetry artifacts declared

Current recovered loop still has placeholder sample generation audit, so it cannot support a decoder capability claim yet.

## Telemetry Still Missing

Before any real structured training claim, add:

- row-field logits
- row-field losses
- field exact by split
- field exact by cell
- confusion matrices
- margin/confidence/entropy
- high-confidence wrong rows
- per-row gradient norms

These determine whether an error is caused by bad rows, weak features, bad representation, bad head, loss weighting, or gradient routing.

