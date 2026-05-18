#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EGOCORE = REPO_ROOT / 'EgoCore'
OPENEMOTION = REPO_ROOT / 'OpenEmotion'
OUT = EGOCORE / 'docs' / 'generated'
OUT.mkdir(parents=True, exist_ok=True)

REPOS = {'EgoCore': EGOCORE, 'OpenEmotion': OPENEMOTION}
EXCLUDE_PARTS = {'.git', '.pytest_cache', '__pycache__', '.mypy_cache', 'venv', '.venv', 'venv2', 'venv_new', 'build'}
EXCLUDE_PREFIXES = ('artifacts/', 'logs/', 'data/', 'reports/', 'test_output/', 'tmp/')
HOTSPOT_TIMEOUT_SECONDS = 3
HOTSPOT_MAX_COMMITS = 500


def keep(rel: Path) -> bool:
    s = rel.as_posix()
    if any(part in EXCLUDE_PARTS for part in rel.parts):
        return False
    if s.startswith(EXCLUDE_PREFIXES):
        return False
    return True


def scan_files(repo: Path):
    try:
        cp = subprocess.run(
            ['git', '-C', str(repo), '-c', 'core.quotepath=false', 'ls-files', '-z'],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if cp.returncode == 0:
            for raw_path in cp.stdout.split(b'\0'):
                if not raw_path:
                    continue
                rel = Path(raw_path.decode('utf-8', errors='surrogateescape'))
                if keep(rel) and (repo / rel).exists():
                    yield rel
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    for root, dirnames, filenames in os.walk(repo, topdown=True):
        root_path = Path(root)
        rel_root = root_path.relative_to(repo)
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_PARTS]

        for filename in filenames:
            rel = (rel_root / filename) if rel_root != Path('.') else Path(filename)
            if keep(rel):
                yield rel


def build_recent_hotspots(repo_name: str, repo: Path) -> list[str]:
    lines = [f'## {repo_name}']
    try:
        cp = subprocess.run(
            [
                'git',
                '-C',
                str(repo),
                'log',
                '--since=30 days ago',
                f'--max-count={HOTSPOT_MAX_COMMITS}',
                '--name-only',
                '--pretty=format:',
            ],
            capture_output=True,
            text=True,
            timeout=HOTSPOT_TIMEOUT_SECONDS,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        lines.append(f'- skipped: git hotspot scan unavailable within {HOTSPOT_TIMEOUT_SECONDS}s')
        lines.append('')
        return lines

    cnt = Counter([l.strip() for l in cp.stdout.splitlines() if l.strip()])
    for path, n in cnt.most_common(30):
        lines.append(f'- `{path}`: {n}')
    if len(lines) == 1:
        lines.append('- no recent hotspot data')
    lines.append('')
    return lines


def build():
    rows = []
    imports = []
    module_lines = []
    orphans = []

    for repo_name, repo in REPOS.items():
        files = list(scan_files(repo))
        top = defaultdict(list)
        for rel in files:
            rows.append([repo_name, rel.as_posix(), rel.suffix, (repo / rel).stat().st_size])
            top[(rel.parts[0] if len(rel.parts) > 1 else '.')].append(rel.as_posix())

        module_lines.append(f'## {repo_name}\n')
        for key in sorted(top):
            sample = '; '.join(top[key][:8])
            module_lines.append(f'- `{key}`: {len(top[key])} files\n  - sample: {sample}')

        for rel in files:
            if rel.suffix == '.py':
                text = (repo / rel).read_text(encoding='utf-8', errors='ignore')
                for m in re.finditer(r'^(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))', text, re.M):
                    tgt = m.group(1) or m.group(2)
                    imports.append([repo_name, rel.as_posix(), tgt])

        py_refs = '\n'.join(i[2] for i in imports if i[0] == repo_name)
        for rel in files:
            if rel.suffix == '.py' and rel.parts[0] in {'app', 'emotiond', 'openemotion', 'egocore'}:
                mod = rel.with_suffix('').as_posix().replace('/', '.')
                base = rel.stem
                if base not in py_refs and mod not in py_refs and '__init__' not in rel.name:
                    orphans.append([repo_name, rel.as_posix(), 'python-no-obvious-import-hit'])

    with open(OUT / 'file_inventory.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['repo', 'path', 'suffix', 'size_bytes'])
        w.writerows(rows)

    with open(OUT / 'import_or_reference_map.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['repo', 'source', 'target'])
        w.writerows(imports)

    (OUT / 'module_map.md').write_text('# Module Map\n\n' + '\n'.join(module_lines) + '\n', encoding='utf-8')

    with open(OUT / 'orphan_candidates.md', 'w', encoding='utf-8') as f:
        f.write('# Orphan Candidates\n\n')
        for repo, path, reason in orphans[:400]:
            f.write(f'- `{repo}:{path}` — {reason}\n')

    lines = ['# Repo Inventory\n']
    for repo_name, repo in REPOS.items():
        dirs = Counter()
        files = 0
        for rel in scan_files(repo):
            files += 1
            dirs[rel.parts[0] if len(rel.parts) > 1 else '.'] += 1
        lines.append(f'## {repo_name}')
        lines.append(f'- root: `{repo}`')
        lines.append(f'- filtered file count: `{files}`')
        lines.append('- top areas:')
        for k, v in dirs.most_common(12):
            lines.append(f'  - `{k}`: {v} files')
        lines.append('')
    (OUT / 'repo_inventory.md').write_text('\n'.join(lines), encoding='utf-8')

    hot = ['# Recent Hotspots\n']
    for repo_name, repo in REPOS.items():
        hot.extend(build_recent_hotspots(repo_name, repo))
    (OUT / 'recent_hotspots.md').write_text('\n'.join(hot), encoding='utf-8')

    generated_readme = '''# Generated Inventory Boundary

Rebuild-only generated inventory boundary.

Rules:
- This directory is derived from `EgoCore/tools/build_doc_system_inventory.py`.
- Do not treat generated inventory as an authority source.
- The clean-clone / CI final closeout proof must rebuild this directory, not trust dirty worktree residue.

Current generated outputs:
- `README.md`
- `file_inventory.csv`
- `import_or_reference_map.csv`
- `module_map.md`
- `orphan_candidates.md`
- `recent_hotspots.md`
- `repo_inventory.md`
'''
    (OUT / 'README.md').write_text(generated_readme, encoding='utf-8')

    print('Generated doc inventory under', OUT)


if __name__ == '__main__':
    build()
