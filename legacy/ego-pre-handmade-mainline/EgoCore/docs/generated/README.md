# Generated Inventory Boundary

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
