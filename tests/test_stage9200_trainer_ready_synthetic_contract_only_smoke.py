from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9200_trainer_ready_synthetic_contract_only_smoke import main  # noqa: E402


def test_stage9200_smoke_runs(tmp_path: Path, monkeypatch) -> None:
    # Use a repo-local temp area because the trainer contract requires output-dir under repo_root.
    import scripts.build_stage9200_trainer_ready_synthetic_contract_only_smoke as mod

    repo_tmp = Path('/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/test_stage9200_pytest_tmp')
    repo_tmp.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mod, "OUT_DIR", repo_tmp / "artifacts")
    monkeypatch.setattr(mod, "SUMMARY", repo_tmp / "summary.json")
    monkeypatch.setattr(mod, "DOC", repo_tmp / "doc.md")
    monkeypatch.setattr(mod, "REGISTRY", repo_tmp / "registry.json")
    monkeypatch.setattr(mod, "SOURCE_9199", Path("runs/summaries/stage9199_trainer_contract_ready_recovery_audit.json"))
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    assert (repo_tmp / 'summary.json').is_file()
    assert (repo_tmp / 'artifacts' / 'trainer_ready_synthetic_contract_only_smoke.json').is_file()
