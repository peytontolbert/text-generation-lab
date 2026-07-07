from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from safe_paths import UnsafePathError, build_safe_cleanup_plan, require_safe_child_path, assert_no_destructive_command_tokens
from safe_cleanup import safe_cleanup_checkpoints


def make_probe(tmp_path: Path, run_id: str = 'stage8584') -> tuple[Path, Path]:
    repo = tmp_path / 'repo'
    out = repo / 'runs' / 'local' / 'probes' / run_id
    ckpt = out / 'checkpoints'
    ckpt.mkdir(parents=True)
    (out / '.agentkernel_probe_output').write_text(f'run_id={run_id}\n', encoding='utf-8')
    (ckpt / 'step-1.pt').write_text('checkpoint', encoding='utf-8')
    return repo, out


def test_safe_cleanup_only_removes_checkpoint_children(tmp_path: Path) -> None:
    repo, out = make_probe(tmp_path)
    keep = out / 'loss_by_step.jsonl'
    keep.write_text('{}\n', encoding='utf-8')
    result = safe_cleanup_checkpoints(repo_root=repo, output_dir=out, run_id='stage8584')
    assert result['removed_count'] == 1
    assert keep.exists()
    assert out.exists()
    assert repo.exists()
    assert not (out / 'checkpoints' / 'step-1.pt').exists()


def test_refuses_repo_root(tmp_path: Path) -> None:
    repo, _out = make_probe(tmp_path)
    with pytest.raises(UnsafePathError):
        require_safe_child_path(repo_root=repo, output_dir=repo / 'runs', candidate=repo)


def test_refuses_output_dir_itself(tmp_path: Path) -> None:
    repo, out = make_probe(tmp_path)
    with pytest.raises(UnsafePathError):
        require_safe_child_path(repo_root=repo, output_dir=out, candidate=out)


def test_refuses_parent_of_output_dir(tmp_path: Path) -> None:
    repo, out = make_probe(tmp_path)
    with pytest.raises(UnsafePathError):
        require_safe_child_path(repo_root=repo, output_dir=out, candidate=out.parent)


def test_refuses_missing_marker(tmp_path: Path) -> None:
    repo, out = make_probe(tmp_path)
    (out / '.agentkernel_probe_output').unlink()
    with pytest.raises(UnsafePathError):
        build_safe_cleanup_plan(repo_root=repo, output_dir=out, run_id='stage8584')


def test_refuses_wrong_run_id(tmp_path: Path) -> None:
    repo, out = make_probe(tmp_path)
    with pytest.raises(UnsafePathError):
        build_safe_cleanup_plan(repo_root=repo, output_dir=out, run_id='other')


def test_refuses_symlink_escape(tmp_path: Path) -> None:
    repo, out = make_probe(tmp_path)
    outside = tmp_path / 'outside'
    outside.mkdir()
    link = out / 'checkpoints' / 'escape'
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(UnsafePathError):
        build_safe_cleanup_plan(repo_root=repo, output_dir=out, run_id='stage8584')


def test_refuses_known_destructive_command_tokens() -> None:
    with pytest.raises(UnsafePathError):
        assert_no_destructive_command_tokens(['python', '-c', "import shutil; shutil.rmtree('.')"])


def test_refuses_arxiv_as_cleanup_output() -> None:
    with pytest.raises(UnsafePathError):
        build_safe_cleanup_plan(repo_root=Path('/data/agentkernel-seq2seq-text-lab'), output_dir=Path('/arxiv'), run_id='stage8584')

def test_refuses_arxiv_descendant_as_cleanup_output() -> None:
    with pytest.raises(UnsafePathError):
        build_safe_cleanup_plan(
            repo_root=Path('/data/agentkernel-seq2seq-text-lab'),
            output_dir=Path('/arxiv/backups/probe_output'),
            run_id='stage8584',
        )


def test_refuses_data_root_as_cleanup_output() -> None:
    with pytest.raises(UnsafePathError):
        build_safe_cleanup_plan(
            repo_root=Path('/data/agentkernel-seq2seq-text-lab'),
            output_dir=Path('/data'),
            run_id='stage8584',
        )


def test_refuses_root_as_cleanup_output() -> None:
    with pytest.raises(UnsafePathError):
        build_safe_cleanup_plan(
            repo_root=Path('/data/agentkernel-seq2seq-text-lab'),
            output_dir=Path('/'),
            run_id='stage8584',
        )


def test_refuses_arxiv_repo_root() -> None:
    with pytest.raises(UnsafePathError):
        build_safe_cleanup_plan(
            repo_root=Path('/arxiv'),
            output_dir=Path('/arxiv/probe_output'),
            run_id='stage8584',
        )

def test_refuses_destructive_command_tokens_for_arxiv_and_data() -> None:
    with pytest.raises(UnsafePathError):
        assert_no_destructive_command_tokens(['bash', '-lc', 'rm -rf /arxiv'])
    with pytest.raises(UnsafePathError):
        assert_no_destructive_command_tokens(['bash', '-lc', 'rm -rf /data'])

