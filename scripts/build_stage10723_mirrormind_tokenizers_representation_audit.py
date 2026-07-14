#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import (  # noqa: E402
    AgentKernelLiteTransformerConfig,
    AgentKernelLiteTransformerSeq2Seq,
)
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch  # noqa: E402
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle  # noqa: E402

STAGE = 10723
NAME = "stage10723_mirrormind_tokenizers_representation_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "mirrormind_tokenizers_representation_audit.json"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"
STRICT_ROWS = ROOT / "runs/local/artifacts/stage10420_reviewed_multilingual_v27_manifest_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
RUNTIME_BUNDLE = (
    ROOT / "runs/local/artifacts/stage10721_frontloaded_python_verifier_probe/runtime_model/runtime_model_bundle.json"
)
PYTHON_ROW_ID = (
    "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_"
    "models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::"
    "verifier_outcome::reviewed_v27_compact"
)
RUST_ROW_ID = "stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    model_config = load_json(Path(str(metadata["model_config"])))
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(model_config)
    model = AgentKernelLiteTransformerSeq2Seq(config)
    _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(
        Path(str(metadata["tokenizer_json"])),
        Path(str(metadata["tokenizer_config"])),
    )
    model.eval()
    return model, tokenizer


def _encode_option_texts(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    texts: list[str],
    device: torch.device,
) -> torch.Tensor:
    encoded_rows = []
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    bos_id = int(getattr(tokenizer, "bos_id", 1))
    eos_id = int(getattr(tokenizer, "eos_id", 2))
    for text in texts:
        token_ids = [idx for idx in tokenizer.encode(text, max_length=768) if idx not in {bos_id, eos_id}]
        if not token_ids:
            token_ids = [pad_id]
        encoded_rows.append(token_ids)
    width = max(len(ids) for ids in encoded_rows)
    input_ids = torch.full((len(encoded_rows), width), pad_id, dtype=torch.long, device=device)
    attention_mask = torch.zeros((len(encoded_rows), width), dtype=torch.bool, device=device)
    for row_idx, token_ids in enumerate(encoded_rows):
        input_ids[row_idx, : len(token_ids)] = torch.tensor(token_ids, dtype=torch.long, device=device)
        attention_mask[row_idx, : len(token_ids)] = True
    return model.encode_pooled(input_ids, attention_mask)


def _option_pairs(row: dict[str, Any]) -> list[tuple[str, str]]:
    options = (((row.get("standalone_projection_source") or {}).get("opaque_options")) or [])
    return [(str(option["label"]), str(option["value"])) for option in options]


def _basename(path_value: str) -> str:
    return Path(path_value).name


def _stem(path_value: str) -> str:
    return Path(path_value).stem


def _parent_basename(path_value: str) -> str:
    parts = Path(path_value).parts
    return "/".join(parts[-2:]) if len(parts) >= 2 else path_value


def _moduleish(path_value: str) -> str:
    parts = list(Path(path_value).parts)
    return "/".join(parts[-3:]) if len(parts) >= 3 else path_value


def _drop_extension(path_value: str) -> str:
    p = Path(path_value)
    return str(p.with_suffix(""))


def _naturalize_key(key: str) -> str:
    return key.replace("_", " ")


def _option_text(value: str, variant: str) -> str:
    if variant == "raw_value":
        return value
    if variant == "basename":
        return _basename(value)
    if variant == "stem":
        return _stem(value)
    if variant == "parent_basename":
        return _parent_basename(value)
    if variant == "moduleish":
        return _moduleish(value)
    if variant == "drop_extension":
        return _drop_extension(value)
    if variant == "test_focus":
        return f"Selected test under review: {_basename(value)}"
    if variant == "module_focus":
        return f"Selected test under review: {_parent_basename(value)}"
    if variant == "repo_focus":
        return f"Selected verifier target under review: {_moduleish(value)}"
    if variant == "verifier_target_templated":
        return f"Verifier target under review: {value}"
    if variant == "evidence_key_raw":
        return value
    if variant == "evidence_key_natural":
        return _naturalize_key(value)
    if variant == "evidence_key_templated":
        return f"Visible fact under review: {value}"
    if variant == "evidence_key_natural_templated":
        return f"Visible fact under review: {_naturalize_key(value)}"
    if variant == "evidence_support_templated":
        return f"Supporting evidence category: {_naturalize_key(value)}"
    raise ValueError(f"unsupported option variant: {variant}")


def _score_row(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, Any],
    *,
    option_variant: str,
) -> dict[str, Any]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    query = out["pooled"][0:1]
    retrieval_query_head = getattr(model, "retrieval_query_head", None)
    retrieval_doc_head = getattr(model, "retrieval_doc_head", None)
    if retrieval_query_head is not None:
        query = retrieval_query_head(query)
    option_pairs = _option_pairs(row)
    texts = [_option_text(value, option_variant) for _, value in option_pairs]
    option_vectors = _encode_option_texts(model, tokenizer, texts, query.device)
    if retrieval_doc_head is not None:
        option_vectors = retrieval_doc_head(option_vectors)
    query = F.normalize(query.float(), dim=-1)
    option_vectors = F.normalize(option_vectors.float(), dim=-1)
    logits = torch.matmul(query, option_vectors.transpose(0, 1)).squeeze(0)
    scored = [
        {
            "label": label,
            "value": value,
            "text": texts[idx],
            "logit": float(logits[idx].item()),
        }
        for idx, (label, value) in enumerate(option_pairs)
    ]
    scored.sort(key=lambda item: item["logit"], reverse=True)
    target = str(row["decoder_text"])
    target_entry = next(item for item in scored if item["label"] == target)
    return {
        "option_variant": option_variant,
        "target": target,
        "pred": scored[0]["label"],
        "correct": scored[0]["label"] == target,
        "target_rank": next(i for i, item in enumerate(scored, start=1) if item["label"] == target),
        "target_logit": target_entry["logit"],
        "top3": scored[:3],
    }


def _audit_family(
    model: AgentKernelLiteTransformerSeq2Seq,
    tokenizer: AgentKernelBPETokenizer,
    row: dict[str, Any],
    option_variants: list[str],
) -> dict[str, Any]:
    results = [_score_row(model, tokenizer, row, option_variant=variant) for variant in option_variants]
    correct_variants = [item["option_variant"] for item in results if item["correct"]]
    best_target_rank = min(item["target_rank"] for item in results)
    strongest_target = max(results, key=lambda item: item["target_logit"])
    return {
        "row_id": str(row["row_id"]),
        "target": str(row["decoder_text"]),
        "gold_value": str((row.get("standalone_projection_source") or {}).get("gold_value") or ""),
        "results": results,
        "correct_variants": correct_variants,
        "best_target_rank": best_target_rank,
        "strongest_target_variant": strongest_target["option_variant"],
        "strongest_target_logit": strongest_target["target_logit"],
    }


def main() -> None:
    rows = load_jsonl(STRICT_ROWS)
    by_id = {str(row["row_id"]): row for row in rows}
    python_row = by_id[PYTHON_ROW_ID]
    rust_row = by_id[RUST_ROW_ID]
    model, tokenizer = _load_runtime()

    python_variants = [
        "raw_value",
        "basename",
        "stem",
        "parent_basename",
        "moduleish",
        "drop_extension",
        "verifier_target_templated",
        "test_focus",
        "module_focus",
        "repo_focus",
    ]
    rust_variants = [
        "evidence_key_raw",
        "evidence_key_natural",
        "evidence_key_templated",
        "evidence_key_natural_templated",
        "evidence_support_templated",
    ]

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "runtime_bundle": str(RUNTIME_BUNDLE.relative_to(ROOT)),
        "strict_rows_source": str(STRICT_ROWS.relative_to(ROOT)),
        "families": {
            "python_mirrormind_verifier": _audit_family(model, tokenizer, python_row, python_variants),
            "rust_tokenizers_citation": _audit_family(model, tokenizer, rust_row, rust_variants),
        },
    }

    audit["conclusions"] = {
        "python_has_any_correct_variant": bool(audit["families"]["python_mirrormind_verifier"]["correct_variants"]),
        "rust_has_any_correct_variant": bool(audit["families"]["rust_tokenizers_citation"]["correct_variants"]),
        "python_best_target_rank": audit["families"]["python_mirrormind_verifier"]["best_target_rank"],
        "rust_best_target_rank": audit["families"]["rust_tokenizers_citation"]["best_target_rank"],
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY_JSON,
        {
            "stage": STAGE,
            "python_has_any_correct_variant": audit["conclusions"]["python_has_any_correct_variant"],
            "rust_has_any_correct_variant": audit["conclusions"]["rust_has_any_correct_variant"],
            "python_best_target_rank": audit["conclusions"]["python_best_target_rank"],
            "rust_best_target_rank": audit["conclusions"]["rust_best_target_rank"],
            "artifact": str(AUDIT_JSON.relative_to(ROOT)),
        },
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
