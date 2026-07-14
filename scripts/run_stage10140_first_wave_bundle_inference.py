#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
import urllib.request
from functools import partial
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAYLOAD = ROOT / "runs/local/artifacts/stage10139_first_wave_bundle_runtime_payload/first_wave_bundle_runtime_payload.json"
DEFAULT_HANDOFF = ROOT / "runs/local/artifacts/stage10081_canonical_harness_backend_handoff_bundle/canonical_harness_backend_handoff_bundle.json"
DEFAULT_OUT = ROOT / "runs/local/artifacts/stage10140_first_wave_bundle_inference"

try:
    from safetensors.torch import load_file as load_safetensors_file  # type: ignore
except Exception:  # pragma: no cover
    load_safetensors_file = None

try:
    import torch  # type: ignore
except Exception:  # pragma: no cover
    torch = None


def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, symbol)


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ADAPTER_VALIDATE_AND_WRITE = _load_symbol(
    "stage10140_stage10081_adapter",
    ROOT / "scripts" / "run_stage10081_canonical_harness_backend_adapter.py",
    "validate_and_write",
)


AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stable_hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def safe_cell_dir_name(cell_key: str) -> str:
    normalized = cell_key.replace("::", "__")
    if len(normalized) <= 120:
        return normalized
    return normalized[:96] + "__" + stable_hash(cell_key)[:16]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one admitted first-wave maintainer bundle per language for 100M and Gemma, then write machine artifacts through the Stage10081 adapter.")
    parser.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cell-key", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-writeback", action="store_true")
    parser.add_argument("--skip-gemma", action="store_true")
    parser.add_argument("--device", default=None, help="Optional override device for preserved 100M inference, e.g. cuda or cpu.")
    parser.add_argument("--progress", action="store_true", help="Emit per-stage and per-row progress logs to stderr.")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional cap on rows executed per bundle for smoke runs.")
    return parser.parse_args()


def ollama_generate(
    *,
    model: str,
    prompt: str,
    seed: int = 0,
    temperature: float = 0.0,
    num_predict: int = 48,
    timeout_seconds: int = 300,
    stop: list[str] | None = None,
) -> str:
    options: dict[str, Any] = {
        "seed": seed,
        "temperature": temperature,
        "num_predict": num_predict,
    }
    if stop:
        options["stop"] = stop
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "options": options}).encode("utf-8")
    request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = json.loads(response.read().decode("utf-8"))
    return str(body.get("response") or "").strip()


def normalize_answer(answer_kind: str, value: str) -> str:
    text = " ".join(str(value).strip().split())
    if answer_kind in {"candidate_path", "selected_test", "visible_evidence_key", "abstain"}:
        return text
    return "".join(ch.lower() for ch in text if ch.isalnum() or ch.isspace()).strip()


def answer_correct(answer_kind: str, predicted: str, expected: str) -> bool:
    return normalize_answer(answer_kind, predicted) == normalize_answer(answer_kind, expected)


def row_answer_kind(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("expected_answer_kind") or "").strip()
    if explicit:
        return explicit
    if row.get("opaque_options") or ((row.get("standalone_projection_source") or {}).get("opaque_options")):
        return "opaque_choice"
    return ""


def row_expected_label(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("expected_label") or "").strip()
    if explicit:
        return explicit
    return str(row.get("target_text") or "").strip()


def row_perspective(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("perspective") or "").strip()
    if explicit:
        return explicit
    return str(row.get("task_type") or "").strip()


def row_prompt_text(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("prompt") or "")
    if explicit:
        return explicit
    explicit = str(row.get("prompt_text") or "")
    if explicit:
        return explicit
    return str(row.get("input_text") or "")


def row_opaque_options(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    direct = row.get("opaque_options")
    if isinstance(direct, list):
        return [item for item in direct if isinstance(item, dict)]
    nested = (row.get("standalone_projection_source") or {}).get("opaque_options")
    if isinstance(nested, list):
        return [item for item in nested if isinstance(item, dict)]
    return []


def normalize_opaque_choice_label(raw: str, options: list[dict[str, Any]]) -> str:
    text = str(raw).strip()
    if not text:
        return ""
    option_labels = [str(item.get("label") or "").strip() for item in options if str(item.get("label") or "").strip()]
    option_pairs = [(str(item.get("label") or "").strip(), str(item.get("value") or "").strip()) for item in options if str(item.get("label") or "").strip()]
    first_line = text.splitlines()[0].strip()
    if first_line in option_labels:
        return first_line
    patterns = [
        r"\*\*([A-Z])\*\*",
        r"([A-Z])(?=\s*[:.])",
        r"answer\s+is\s+([A-Z])",
        r"therefore[, ]+the answer is\s+([A-Z])",
        r"option\s+([A-Z])",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            candidate = match.group(1).upper()
            if candidate in option_labels:
                return candidate
    lowered = text.lower()
    for label, value in option_pairs:
        if value and value.lower() in lowered:
            return label
    for line in text.splitlines():
        line = line.strip()
        for label in option_labels:
            if line == label:
                return label
            if line.startswith(f"{label}.") or line.startswith(f"{label}:") or line.startswith(f"{label} "):
                return label
    return first_line


def trace_span(trace: list[dict[str, Any]], *, name: str, span_type: str, attrs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    span = {
        "span_id": f"{span_type}_{len(trace) + 1}",
        "span_type": span_type,
        "name": name,
        "start_time_utc": now_utc(),
        "_started": time.time(),
        "attrs": dict(attrs or {}),
    }
    trace.append(span)
    return span


def finish_span(span: dict[str, Any], *, failed: bool = False, error: str | None = None, metrics: Mapping[str, Any] | None = None) -> None:
    ended = time.time()
    span["end_time_utc"] = now_utc()
    span["duration_ms"] = round((ended - float(span.pop("_started", ended))) * 1000.0, 3)
    span["failed"] = failed
    if error:
        span["error"] = error
    if metrics:
        span["metrics"] = dict(metrics)


def log_progress(enabled: bool, message: str) -> None:
    if not enabled:
        return
    print(f"[{now_utc()}] {message}", file=sys.stderr, flush=True)


def _load_state_dict(weights: Path) -> dict[str, Any]:
    with weights.open("rb") as handle:
        magic = handle.read(4)
    if magic.startswith(b"PK"):
        loaded = torch.load(str(weights), map_location="cpu")
        if isinstance(loaded, dict) and "model_state_dict" in loaded and isinstance(loaded["model_state_dict"], dict):
            return dict(loaded["model_state_dict"])
        if isinstance(loaded, dict):
            return dict(loaded)
        raise RuntimeError("torch_archive_did_not_contain_state_dict")
    if load_safetensors_file is None:
        raise RuntimeError("safetensors_runtime_not_available")
    return dict(load_safetensors_file(str(weights), device="cpu"))


def resolve_device(backend: Mapping[str, Any], override_device: str | None = None) -> str:
    if torch is None:
        return "cpu"
    requested = str(override_device or backend.get("device") or "").strip().lower()
    if requested:
        if requested.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("cuda_requested_but_unavailable")
        return requested
    return "cuda" if torch.cuda.is_available() else "cpu"


def load_preserved_model(backend: Mapping[str, Any], *, override_device: str | None = None, progress: bool = False):
    if torch is None or not hasattr(torch, "Tensor") or not hasattr(torch, "softmax"):
        raise RuntimeError("usable_torch_runtime_not_available")
    log_progress(progress, "100M runtime: preparing preserved model load")
    runtime_bundle_value = str(backend.get("runtime_model_bundle") or "").strip()
    manifest_value = str(backend.get("model_bundle_manifest") or "").strip()
    weights_value = str(backend.get("model_weights") or "").strip()
    runtime_bundle = Path(runtime_bundle_value) if runtime_bundle_value else None
    manifest = Path(manifest_value) if manifest_value else None
    weights = Path(weights_value) if weights_value else None
    runtime_bundle_data: dict[str, Any] = {}
    if runtime_bundle is not None:
        runtime_bundle_data = load_json(runtime_bundle)
    runtime_metadata = runtime_bundle_data.get("metadata") if isinstance(runtime_bundle_data.get("metadata"), Mapping) else {}
    modeling_transformer = _load_module(
        "stage10140_modeling_transformer",
        ROOT / "legacy_src/agentkernel_lite/modeling_transformer.py",
    )
    training_data = _load_module(
        "stage10140_training_data",
        ROOT / "legacy_src/agentkernel_lite/training_data.py",
    )
    if runtime_bundle_data:
        model_config_path = Path(str(runtime_metadata.get("model_config") or backend.get("model_config") or ""))
        if not model_config_path.exists():
            raise RuntimeError("runtime_model_bundle_missing_model_config")
        config = modeling_transformer.AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(model_config_path))
        if not weights:
            weights = Path(str(runtime_bundle_data.get("weights_path") or ""))
        tokenizer_json = Path(str(runtime_metadata.get("tokenizer_json") or backend.get("tokenizer_json") or ""))
        tokenizer_config = Path(str(runtime_metadata.get("tokenizer_config") or backend.get("tokenizer_config") or ""))
    else:
        if manifest is None:
            raise RuntimeError("missing_model_bundle_manifest")
        manifest_data = load_json(manifest)
        config = modeling_transformer.AgentKernelLiteTransformerConfig.from_recovered_target_json(manifest_data)
        tokenizer_json = ROOT / str(backend.get("tokenizer_json") or "")
        tokenizer_config = ROOT / str(backend.get("tokenizer_config") or "")
    log_progress(progress, f"100M runtime: tokenizer={tokenizer_json} config={tokenizer_config}")
    tokenizer = training_data.AgentKernelBPETokenizer(tokenizer_json, tokenizer_config)
    model = modeling_transformer.AgentKernelLiteTransformerSeq2Seq(config)
    if weights is None:
        raise RuntimeError("missing_model_weights")
    log_progress(progress, f"100M runtime: loading weights from {weights}")
    state = _load_state_dict(weights)
    model.load_state_dict(state, strict=False)
    device = resolve_device(backend, override_device=override_device)
    model.to(device)
    model.eval()
    log_progress(progress, f"100M runtime: model ready on {device}")
    return model, tokenizer, device


def generate_100m(model: Any, tokenizer: Any, prompt: str, *, device: str, max_encoder_tokens: int, max_new_tokens: int) -> str:
    bos_id = int(getattr(tokenizer, "bos_id", 1))
    eos_id = int(getattr(tokenizer, "eos_id", 2))
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    enc_ids = tokenizer.encode(prompt, max_length=max_encoder_tokens)
    input_ids = torch.tensor([enc_ids], dtype=torch.long, device=device)
    decoder_ids = torch.tensor([[bos_id]], dtype=torch.long, device=device)
    generated: list[int] = []
    with torch.inference_mode():
        for _ in range(max_new_tokens):
            out = model(input_ids, decoder_ids)
            next_logits = out["decoder_logits"][0, -1].detach().float()
            next_id = int(torch.argmax(next_logits).item())
            if next_id == eos_id:
                break
            generated.append(next_id)
            next_token = torch.tensor([[next_id]], dtype=torch.long, device=device)
            decoder_ids = torch.cat([decoder_ids, next_token], dim=1)
    clean = [idx for idx in generated if idx not in {pad_id, bos_id, eos_id}]
    return tokenizer.decode(clean).strip()


def _encode_option_values(*, model: Any, tokenizer: Any, option_values: list[str], device: str, max_option_tokens: int = 96):
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    encoded_rows: list[list[int]] = []
    for text in option_values:
        token_ids = [int(idx) for idx in tokenizer.encode(str(text), max_length=max_option_tokens)[:max_option_tokens]]
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


def predict_bounded_choice_100m(
    model: Any,
    tokenizer: Any,
    row: Mapping[str, Any],
    *,
    device: str,
    max_encoder_tokens: int,
    source: str,
) -> str:
    if not hasattr(model, "encode_pooled"):
        raise RuntimeError("model_missing_encode_pooled_for_bounded_choice")
    options = [item for item in row_opaque_options(row) if isinstance(item, dict) and item.get("label")]
    if not options:
        raise RuntimeError("bounded_choice_row_missing_opaque_options")
    prompt = row_prompt_text(row)
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    enc_ids = [int(idx) for idx in tokenizer.encode(prompt, max_length=max_encoder_tokens)]
    if not enc_ids:
        enc_ids = [pad_id]
    input_ids = torch.tensor([enc_ids], dtype=torch.long, device=device)
    attention_mask = input_ids.ne(pad_id)
    with torch.inference_mode():
        pooled = model.encode_pooled(input_ids, attention_mask)[0]
        option_values = [str(item.get("value") or item.get("label") or "") for item in options]
        active_source = source
        task_type = str(row.get("task_type") or row_perspective(row) or "")
        if source == "encoder_option_retrieval_evidence_judgment_head" and task_type != "evidence_candidate_judgment":
            active_source = "encoder_option_retrieval_verifier_conditioned"
        if active_source == "encoder_option_retrieval_verifier_conditioned" and task_type == "verifier_outcome_semantic_transition":
            base_prompt = prompt.split("\nOptions:\n", 1)[0].strip() if "\nOptions:\n" in prompt else prompt.strip()
            option_values = [f"{base_prompt}\nCandidate under review: {value}" if base_prompt else f"Candidate under review: {value}" for value in option_values]
        option_vectors = _encode_option_values(model=model, tokenizer=tokenizer, option_values=option_values, device=device)
        if active_source in {"encoder_option_retrieval", "encoder_option_retrieval_verifier_conditioned"}:
            import torch.nn.functional as F
            query = pooled.unsqueeze(0)
            retrieval_query_head = getattr(model, "retrieval_query_head", None)
            retrieval_doc_head = getattr(model, "retrieval_doc_head", None)
            if retrieval_query_head is not None:
                query = retrieval_query_head(query)
            if retrieval_doc_head is not None:
                option_vectors = retrieval_doc_head(option_vectors)
            query = F.normalize(query.float(), dim=-1)
            option_vectors = F.normalize(option_vectors.float(), dim=-1)
            logits = torch.matmul(query, option_vectors.transpose(0, 1)).squeeze(0)
        elif active_source == "encoder_option_retrieval_evidence_judgment_head":
            head = getattr(model, "bounded_choice_evidence_judgment_head", None)
            if head is None:
                raise RuntimeError("model_missing_evidence_judgment_head")
            bucket_map = {
                "DECISIVE_VERIFIER_TEST_CONSTRAINT": 0,
                "SUPPORTING_CANDIDATE_CHANGE_SURFACE": 1,
                "SUPPORTING_SYMPTOM_OR_CALL_PATH": 2,
                "DISTRACTOR_BACKGROUND_CONTEXT": 3,
            }
            bucket_ids = []
            for value in option_values:
                bucket = bucket_map.get(str(value).strip())
                if bucket is None:
                    raise RuntimeError(f"unsupported_evidence_judgment_option_value::{value}")
                bucket_ids.append(bucket)
            role_logits = head(pooled.unsqueeze(0).float()).squeeze(0)
            logits = role_logits[torch.tensor(bucket_ids, dtype=torch.long, device=role_logits.device)]
        elif source == "encoder_pooled":
            if not hasattr(model, "lm_head"):
                raise RuntimeError("model_missing_lm_head_for_encoder_pooled")
            logits = []
            vocab_logits = model.lm_head(pooled.unsqueeze(0)).squeeze(0)
            bos_id = int(getattr(tokenizer, "bos_id", 1))
            eos_id = int(getattr(tokenizer, "eos_id", 2))
            for item in options:
                label = str(item.get("label") or "")
                label_ids = [idx for idx in tokenizer.encode(label, max_length=4) if idx not in {pad_id, bos_id, eos_id}]
                if len(label_ids) != 1:
                    raise RuntimeError(f"opaque_choice_label_not_single_token::{label}")
                logits.append(vocab_logits[int(label_ids[0])])
            logits = torch.stack(logits)
        else:
            raise RuntimeError(f"unsupported_bounded_choice_source::{source}")
    best_idx = int(torch.argmax(logits).item())
    return str(options[best_idx].get("label") or "")


def run_rows_100m(rows: list[dict[str, Any]], backend: Mapping[str, Any], *, dry_run: bool, override_device: str | None = None, progress: bool = False) -> dict[str, Any]:
    if dry_run:
        outputs = [
            {
                "row_id": row["row_id"],
                "perspective": row_perspective(row),
                "answer_kind": row_answer_kind(row),
                "predicted": None,
                "expected": row_expected_label(row),
                "correct": None,
            }
            for row in rows
        ]
        return {"status": "dry_run_ready", "rows": outputs}
    kind = str(backend.get("kind") or "preserved_bundle_prompt_generation")
    outputs = []
    if kind == "frozen_bounded_choice_audit":
        audit_path = Path(str(backend.get("bounded_choice_audit_path") or ""))
        audit = load_json(audit_path)
        row_cards = [row for row in (audit.get("row_cards") or []) if isinstance(row, dict)]
        by_row_id = {str(row.get("row_id") or ""): row for row in row_cards}
        for row in rows:
            card = by_row_id.get(str(row.get("row_id") or ""), {})
            predicted = str(card.get("constrained_choice_top1_label") or "") or None
            correct = None if not predicted else answer_correct(row_answer_kind(row), predicted, row_expected_label(row))
            outputs.append(
                {
                    "row_id": row["row_id"],
                    "perspective": row_perspective(row),
                    "answer_kind": row_answer_kind(row),
                    "predicted": predicted,
                    "expected": row_expected_label(row),
                    "correct": correct,
                }
            )
        return {"status": "completed", "rows": outputs, "backend_kind": kind, "audit_path": str(audit_path)}
    log_progress(progress, f"100M runtime: starting bundle with {len(rows)} rows")
    model, tokenizer, device = load_preserved_model(backend, override_device=override_device, progress=progress)
    max_encoder_tokens = int(backend.get("max_encoder_tokens") or 1024)
    if kind == "preserved_bounded_choice_scoring":
        source = str(backend.get("bounded_choice_aux_source") or "encoder_option_retrieval")
        for idx, row in enumerate(rows, start=1):
            log_progress(progress, f"100M bounded-choice row {idx}/{len(rows)} :: {row.get('row_id')}")
            predicted = predict_bounded_choice_100m(model, tokenizer, row, device=device, max_encoder_tokens=max_encoder_tokens, source=source)
            correct = answer_correct(row_answer_kind(row), predicted, row_expected_label(row))
            outputs.append(
                {
                    "row_id": row["row_id"],
                    "perspective": row_perspective(row),
                    "answer_kind": row_answer_kind(row),
                    "predicted": predicted,
                    "expected": row_expected_label(row),
                    "correct": correct,
                }
            )
        return {"status": "completed", "rows": outputs, "device": device, "backend_kind": kind, "bounded_choice_aux_source": source}
    max_new_tokens = int(backend.get("max_new_tokens") or 80)
    for idx, row in enumerate(rows, start=1):
        log_progress(progress, f"100M generative row {idx}/{len(rows)} :: {row.get('row_id')}")
        predicted = generate_100m(model, tokenizer, row_prompt_text(row), device=device, max_encoder_tokens=max_encoder_tokens, max_new_tokens=max_new_tokens)
        correct = answer_correct(row_answer_kind(row), predicted, row_expected_label(row))
        outputs.append(
            {
                "row_id": row["row_id"],
                "perspective": row_perspective(row),
                "answer_kind": row_answer_kind(row),
                "predicted": predicted,
                "expected": row_expected_label(row),
                "correct": correct,
            }
        )
    return {"status": "completed", "rows": outputs, "device": device, "backend_kind": kind}


def run_rows_gemma(rows: list[dict[str, Any]], backend: Mapping[str, Any], *, dry_run: bool, progress: bool = False) -> dict[str, Any]:
    model = str(backend.get("model") or "gemma3:12b")
    seed = int(backend.get("seed") or 0)
    temperature = float(backend.get("temperature") or 0.0)
    timeout_seconds = int(backend.get("timeout_seconds") or 180)
    default_num_predict = int(backend.get("num_predict") or 48)
    outputs = []
    log_progress(progress, f"Gemma runtime: starting bundle with {len(rows)} rows using {model}")
    for idx, row in enumerate(rows, start=1):
        log_progress(progress, f"Gemma row {idx}/{len(rows)} :: {row.get('row_id')}")
        answer_kind = row_answer_kind(row)
        num_predict = default_num_predict
        stop = ["\n"]
        if answer_kind in {"freeform_explanation", "freeform_risk"}:
            num_predict = max(default_num_predict, 80)
            stop = None
        raw_predicted = None if dry_run else ollama_generate(
            model=model,
            prompt=row_prompt_text(row),
            seed=seed,
            temperature=temperature,
            num_predict=num_predict,
            timeout_seconds=timeout_seconds,
            stop=stop,
        )
        if dry_run:
            predicted = None
        elif answer_kind == "opaque_choice":
            predicted = normalize_opaque_choice_label(str(raw_predicted or ""), row_opaque_options(row))
        else:
            predicted = str(raw_predicted or "").splitlines()[0].strip()
        correct = None if dry_run else answer_correct(answer_kind, str(predicted or ""), row_expected_label(row))
        outputs.append(
            {
                "row_id": row["row_id"],
                "perspective": row_perspective(row),
                "answer_kind": answer_kind,
                "predicted": predicted,
                "expected": row_expected_label(row),
                "correct": correct,
            }
        )
    return {"status": "dry_run_ready" if dry_run else "completed", "rows": outputs, "model": model}


def summarize_predictions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    scored = sum(1 for row in rows if isinstance(row.get("correct"), bool))
    correct = sum(1 for row in rows if row.get("correct") is True)
    by_perspective: dict[str, dict[str, Any]] = {}
    for row in rows:
        perspective = row_perspective(row)
        slot = by_perspective.setdefault(perspective, {"rows": 0, "scored_rows": 0, "correct": 0})
        slot["rows"] += 1
        slot["scored_rows"] += int(isinstance(row.get("correct"), bool))
        slot["correct"] += int(row.get("correct") is True)
    for slot in by_perspective.values():
        slot["accuracy"] = (slot["correct"] / slot["scored_rows"]) if slot["scored_rows"] else None
    return {
        "rows": total,
        "scored_rows": scored,
        "correct": correct,
        "accuracy": (correct / scored) if scored else None,
        "by_perspective": by_perspective,
    }


def verifier_results(*, cell_key: str, rows_100m: list[dict[str, Any]], rows_gemma: list[dict[str, Any]]) -> dict[str, Any]:
    focus = {"verifier_outcome", "evidence_citation"}
    selected = []
    for source, label in ((rows_100m, "100m"), (rows_gemma, "gemma12b")):
        for row in source:
            if str(row.get("perspective") or "") in focus:
                selected.append(
                    {
                        "row_id": row.get("row_id"),
                        "system": label,
                        "perspective": row.get("perspective"),
                        "answer_kind": row.get("answer_kind"),
                        "predicted": row.get("predicted"),
                        "expected": row.get("expected"),
                        "passed": row.get("correct"),
                    }
                )
    return {
        "cell_key": cell_key,
        "status": "completed_bundle_prediction_verifier",
        "passed": all(item.get("passed") is True for item in selected if item.get("system") == "100m"),
        "verifier_runs": selected,
        "summary": {"rows": len(selected), "focus_perspectives": sorted(focus)},
        "authority": dict(AUTHORITY_CLOSED),
    }


def patch_scores(*, cell_key: str, rows_100m: list[dict[str, Any]], rows_gemma: list[dict[str, Any]]) -> dict[str, Any]:
    focus = {"patch_impact", "minimal_fix_selection", "abstention_insufficient_evidence", "regression_risk"}
    scores = []
    for source, label in ((rows_100m, "100m"), (rows_gemma, "gemma12b")):
        for row in source:
            if str(row.get("perspective") or "") in focus:
                scores.append(
                    {
                        "row_id": row.get("row_id"),
                        "system": label,
                        "perspective": row.get("perspective"),
                        "answer_kind": row.get("answer_kind"),
                        "predicted": row.get("predicted"),
                        "expected": row.get("expected"),
                        "correct": row.get("correct"),
                        "minimality_score": 1.0 if row.get("correct") is True else 0.0 if row.get("correct") is False else None,
                    }
                )
    return {
        "cell_key": cell_key,
        "status": "completed_bundle_patch_scoring",
        "passed": all(item.get("correct") is True for item in scores if item.get("system") == "100m"),
        "scores": scores,
        "summary": {"rows": len(scores), "focus_perspectives": sorted(focus)},
        "authority": dict(AUTHORITY_CLOSED),
    }


def tool_trace_rows(harness_run_id: str, trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "trace_id": harness_run_id,
            "spans": [
                {
                    "span_id": span["span_id"],
                    "span_type": span["span_type"],
                    "name": span["name"],
                    "start_time_utc": span.get("start_time_utc"),
                    "end_time_utc": span.get("end_time_utc"),
                    "duration_ms": span.get("duration_ms"),
                    "failed": span.get("failed", False),
                    "attrs": {**dict(span.get("attrs") or {}), **({"metrics": span["metrics"]} if span.get("metrics") else {})},
                }
                for span in trace
            ],
        }
    ]


def run_one(run: Mapping[str, Any], out_dir: Path, *, dry_run: bool, handoff: Path, skip_writeback: bool, skip_gemma: bool, device_override: str | None = None, progress: bool = False, max_rows: int | None = None) -> dict[str, Any]:
    cell_key = str(run.get("cell_key") or "")
    bundle_id = str(((run.get("task_pack") or {}).get("bundle_id")) or "")
    bundle_hash = stable_hash(bundle_id)[:12]
    harness_run_id = f"{safe_cell_dir_name(cell_key)}__{bundle_hash}"
    cell_dir = out_dir / safe_cell_dir_name(cell_key)
    cell_dir.mkdir(parents=True, exist_ok=True)
    trace: list[dict[str, Any]] = []
    rows = [row for row in ((run.get("task_pack") or {}).get("rows") or []) if isinstance(row, dict)]
    if max_rows is not None:
        rows = rows[: max(0, max_rows)]
    log_progress(progress, f"Bundle start :: {cell_key} :: bundle={bundle_id} :: rows={len(rows)} :: dry_run={dry_run} :: skip_gemma={skip_gemma}")

    span = trace_span(trace, name="hundred_m_bundle_inference", span_type="model_execution", attrs={"cell_key": cell_key})
    hundred_m = run_rows_100m(rows, run.get("hundred_m_backend") if isinstance(run.get("hundred_m_backend"), Mapping) else {}, dry_run=dry_run, override_device=device_override, progress=progress)
    finish_span(span, failed=hundred_m.get("status") not in {"completed", "dry_run_ready"}, metrics={"rows": len(rows), "status": hundred_m.get("status")})

    if skip_gemma:
        gemma = {"status": "skipped", "rows": []}
    else:
        span = trace_span(trace, name="gemma_bundle_inference", span_type="model_execution", attrs={"cell_key": cell_key})
        gemma = run_rows_gemma(rows, run.get("gemma_backend") if isinstance(run.get("gemma_backend"), Mapping) else {}, dry_run=dry_run, progress=progress)
        finish_span(span, failed=gemma.get("status") not in {"completed", "dry_run_ready"}, metrics={"rows": len(rows), "status": gemma.get("status")})

    hundred_rows = list(hundred_m.get("rows") or [])
    gemma_rows = list(gemma.get("rows") or [])
    write_path = cell_dir / "bundle_predictions.json"
    write_path.write_text(json.dumps({"hundred_m": hundred_rows, "gemma12b": gemma_rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    same_task_pack = {
        "cell_key": cell_key,
        "bundle_id": bundle_id,
        "status": "completed_bundle_same_task_pack_comparison",
        "same_task_pack_verified": True,
        "same_task_pack_hash": stable_hash(rows),
        "row_count": len(rows),
        "hundred_m_summary": summarize_predictions(hundred_rows),
        "gemma12b_summary": summarize_predictions(gemma_rows),
        "bundle_predictions_path": display(write_path),
        "authority": dict(AUTHORITY_CLOSED),
    }
    verifier = verifier_results(cell_key=cell_key, rows_100m=hundred_rows, rows_gemma=gemma_rows)
    patch = patch_scores(cell_key=cell_key, rows_100m=hundred_rows, rows_gemma=gemma_rows)
    payload = {
        "runs": [
            {
                "cell_key": cell_key,
                "harness_run_id": harness_run_id,
                "same_task_pack_as_gemma12b": same_task_pack,
                "tool_trace_spans": tool_trace_rows(harness_run_id, trace),
                "verifier_results": verifier,
                "patch_minimality_or_abstain_scores": patch,
            }
        ]
    }
    adapter_payload = cell_dir / "adapter_payload.json"
    adapter_payload.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    writeback = None
    if not skip_writeback:
        log_progress(progress, f"Writeback start :: {cell_key} :: payload={display(adapter_payload)}")
        writeback = ADAPTER_VALIDATE_AND_WRITE(handoff_path=handoff, payload_path=adapter_payload, cell_key=cell_key, dry_run=dry_run)
        (cell_dir / "writeback_result.json").write_text(json.dumps(writeback, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log_progress(progress, f"Bundle complete :: {cell_key} :: rows={len(rows)}")
    return {
        "cell_key": cell_key,
        "bundle_id": bundle_id,
        "harness_run_id": harness_run_id,
        "rows": len(rows),
        "hundred_m": summarize_predictions(hundred_rows),
        "gemma12b": summarize_predictions(gemma_rows),
        "adapter_payload": display(adapter_payload),
        "writeback": writeback,
    }


def main() -> None:
    args = parse_args()
    payload = load_json(args.payload)
    runs = [row for row in payload.get("runs") or [] if isinstance(row, dict)]
    if args.cell_key:
        runs = [row for row in runs if str(row.get("cell_key") or "") == args.cell_key]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for run in runs:
        try:
            results.append(run_one(run, args.out_dir, dry_run=args.dry_run, handoff=args.handoff, skip_writeback=args.skip_writeback, skip_gemma=args.skip_gemma, device_override=args.device, progress=args.progress, max_rows=args.max_rows))
        except Exception as exc:  # pragma: no cover
            failures.append(f"{run.get('cell_key')}::{type(exc).__name__}::{exc}")
    summary = {
        "stage": 10140,
        "stage_name": "stage10140_first_wave_bundle_inference",
        "passed": not failures and bool(results),
        "dry_run": args.dry_run,
        "skip_writeback": args.skip_writeback,
        "skip_gemma": args.skip_gemma,
        "payload": display(args.payload),
        "handoff": display(args.handoff),
        "metrics": {"selected_runs": len(runs), "completed_runs": len(results), "failed_runs": len(failures)},
        "results": results,
        "failures": failures,
        "authority": dict(AUTHORITY_CLOSED),
        "created_at_utc": now_utc(),
    }
    summary_path = args.out_dir / "first_wave_bundle_inference_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
