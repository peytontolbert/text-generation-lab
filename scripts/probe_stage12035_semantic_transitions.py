#!/usr/bin/env python3
"""Run temporary real-source semantic transition probes for Stage12035."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path("/data/tmp/stage12035_semantic_transition_probes")
OUT = Path("runs/local/artifacts/stage12035_semantic_transition_expansion_rows/semantic_transition_probe_results.json")


def run(cmd: list[str], cwd: Path, timeout: int = 180, env: dict[str, str] | None = None) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, env=env)
    combined = (proc.stdout + "\n" + proc.stderr).strip()
    tail = "\n".join(combined.splitlines()[-20:])
    return {"command": " ".join(cmd), "cwd": str(cwd), "returncode": proc.returncode, "stdout_tail": tail}


def copy_repo(src: Path, dst: Path, ignore: tuple[str, ...]) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*ignore))


def mutate_file(path: Path, old: str, new: str) -> str:
    original = path.read_text()
    if old not in original:
        raise RuntimeError(f"mutation target not found in {path}: {old!r}")
    path.write_text(original.replace(old, new, 1))
    return original


def rust_probe(repo: Path, relative_file: str, old: str, new: str, test_filter: str, selected: str) -> dict[str, Any]:
    manifest = repo / "tokenizers" / "Cargo.toml"
    cmd = [
        "conda",
        "run",
        "-n",
        "trellis",
        "cargo",
        "test",
        "--manifest-path",
        str(manifest),
        "--features",
        "fancy-regex",
        test_filter,
        "--quiet",
    ]
    baseline = run(cmd, repo, timeout=240)
    target_file = repo / relative_file
    original = mutate_file(target_file, old, new)
    mutant = run(cmd, repo, timeout=240)
    target_file.write_text(original)
    restored = run(cmd, repo, timeout=240)
    return {
        "language_family": "rust",
        "repo_family": "tokenizers",
        "selected_verifier_path": selected,
        "mutation_file": str(target_file),
        "mutation_kind": "semantic_behavior_change",
        "baseline": baseline,
        "mutant": mutant,
        "restored": restored,
    }


def cpp_probe(repo: Path, build: Path, relative_file: str, old: str, new: str, ctest_regex: str, selected: str) -> dict[str, Any]:
    configure = run(["cmake", "-S", str(repo), "-B", str(build), "-DBENCHMARK_ENABLE_TESTING=ON", "-DBENCHMARK_ENABLE_GTEST_TESTS=OFF"], repo, timeout=180)
    build_base = run(["cmake", "--build", str(build), "--target", "filter_test", "-j2"], repo, timeout=180)
    test_cmd = ["ctest", "--test-dir", str(build), "-R", ctest_regex, "--output-on-failure"]
    baseline = run(test_cmd, repo, timeout=120)
    target_file = repo / relative_file
    original = mutate_file(target_file, old, new)
    build_mutant = run(["cmake", "--build", str(build), "--target", "filter_test", "-j2"], repo, timeout=180)
    mutant = run(test_cmd, repo, timeout=120)
    target_file.write_text(original)
    build_restored = run(["cmake", "--build", str(build), "--target", "filter_test", "-j2"], repo, timeout=180)
    restored = run(test_cmd, repo, timeout=120)
    return {
        "language_family": "c_cpp",
        "repo_family": "benchmark",
        "selected_verifier_path": selected,
        "mutation_file": str(target_file),
        "mutation_kind": "semantic_filter_logic_change",
        "configure": configure,
        "build_base": build_base,
        "build_mutant": build_mutant,
        "build_restored": build_restored,
        "baseline": baseline,
        "mutant": mutant,
        "restored": restored,
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    tokenizers = ROOT / "tokenizers"
    copy_repo(Path("/data/repositories/tokenizers"), tokenizers, (".git", "target"))
    benchmark = ROOT / "benchmark"
    copy_repo(Path("/data/repositories/benchmark"), benchmark, (".git",))

    probes: list[dict[str, Any]] = []
    probes.append(
        rust_probe(
            tokenizers,
            "tokenizers/src/decoders/fuse.rs",
            'let new_string = tokens.join("");',
            'let new_string = tokens.join(" ");',
            "decoders::fuse::tests::decode",
            "tokenizers::decoders::fuse::tests::decode",
        )
    )
    probes.append(
        rust_probe(
            tokenizers,
            "tokenizers/src/decoders/sequence.rs",
            "for decoder in &self.decoders {",
            "for decoder in self.decoders.iter().rev() {",
            "decoders::sequence::tests::sequence_basic",
            "tokenizers::decoders::sequence::tests::sequence_basic",
        )
    )
    probes.append(
        rust_probe(
            tokenizers,
            "tokenizers/src/decoders/ctc.rs",
            ".into_iter()\n            .dedup()\n",
            ".into_iter()\n",
            "decoders::ctc::tests::handmade_sample",
            "tokenizers::decoders::ctc::tests::handmade_sample",
        )
    )
    probes.append(
        cpp_probe(
            benchmark,
            ROOT / "benchmark_build",
            "src/benchmark_register.cc",
            "(!re.Match(full_name) && is_negative_filter)",
            "(re.Match(full_name) && is_negative_filter)",
            "^(filter_simple_negative|filter_suffix_negative|filter_regex_all_negative)$",
            "CTest::filter_simple_negative_filter_suffix_negative_filter_regex_all_negative",
        )
    )
    probes.append(
        cpp_probe(
            benchmark,
            ROOT / "benchmark_build",
            "src/benchmark_register.cc",
            "spec.replace(0, 1, \"\");\n    is_negative_filter = true;",
            "spec.replace(0, 1, \"\");\n    is_negative_filter = false;",
            "^(filter_regex_none|filter_regex_begin2|filter_regex_blank_negative)$",
            "CTest::filter_regex_none_filter_regex_begin2_filter_regex_blank_negative",
        )
    )

    OUT.write_text(json.dumps({"stage": "stage12035_semantic_transition_probes", "probes": probes}, indent=2, sort_keys=True) + "\n")
    admitted = [
        p
        for p in probes
        if p["baseline"]["returncode"] == 0
        and p["mutant"]["returncode"] != 0
        and p["restored"]["returncode"] == 0
        and all(p.get(k, {"returncode": 0})["returncode"] == 0 for k in ("configure", "build_base", "build_mutant", "build_restored"))
    ]
    print(json.dumps({"probes": len(probes), "admissible_fail_to_pass": len(admitted), "out": str(OUT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
