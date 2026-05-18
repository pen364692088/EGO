from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_doc_system_inventory_builder_generates_key_outputs():
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'build_doc_system_inventory.py')], check=True, cwd=ROOT)
    generated = ROOT / 'docs' / 'generated'
    assert (generated / 'README.md').exists()
    assert (generated / 'repo_inventory.md').exists()
    assert (generated / 'file_inventory.csv').exists()
    assert (generated / 'module_map.md').exists()
    assert (generated / 'import_or_reference_map.csv').exists()
    assert (generated / 'orphan_candidates.md').exists()
    assert (generated / 'recent_hotspots.md').exists()


def test_generated_inventory_readme_marks_rebuild_only_boundary():
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'build_doc_system_inventory.py')], check=True, cwd=ROOT)
    generated = ROOT / 'docs' / 'generated' / 'README.md'
    text = generated.read_text(encoding='utf-8')
    assert 'Rebuild-only generated inventory boundary.' in text
    assert 'Do not treat generated inventory as an authority source.' in text
