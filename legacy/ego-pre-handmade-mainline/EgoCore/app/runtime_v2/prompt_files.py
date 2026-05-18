from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


PROMPT_FILENAMES = ["AGENT.md", "SOUL.md", "TOOLS.md"]


@dataclass
class PromptFilesBundle:
    root: str
    loaded: Dict[str, str]

    @property
    def loaded_names(self) -> List[str]:
        return list(self.loaded.keys())

    def render(self) -> str:
        sections: List[str] = []
        for name in PROMPT_FILENAMES:
            content = self.loaded.get(name)
            if not content:
                continue
            sections.append(f"## {name}\n{content.strip()}")
        return "\n\n".join(sections).strip()


class RuntimeV2PromptFiles:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or Path(__file__).resolve().parents[2] / "prompts")
        self.fallback_root = self.root / "tempsaved"
        self._cached_bundle: PromptFilesBundle | None = None

    def _read_prompt_text(self, name: str) -> Optional[str]:
        primary = self.root / name
        if primary.exists():
            content = primary.read_text(encoding="utf-8")
            if content.strip():
                return content
        fallback = self.fallback_root / name
        if fallback.exists():
            content = fallback.read_text(encoding="utf-8")
            if content.strip():
                return content
        return None

    def load(self, force_reload: bool = False) -> PromptFilesBundle:
        if self._cached_bundle is not None and not force_reload:
            return self._cached_bundle
        loaded: Dict[str, str] = {}
        for name in PROMPT_FILENAMES:
            content = self._read_prompt_text(name)
            if content is not None:
                loaded[name] = content
        self._cached_bundle = PromptFilesBundle(root=str(self.root), loaded=loaded)
        return self._cached_bundle

    def read_file(self, name: str) -> Optional[str]:
        normalized = name.strip()
        if normalized not in PROMPT_FILENAMES:
            return None
        return self._read_prompt_text(normalized)

    def reload(self) -> PromptFilesBundle:
        return self.load(force_reload=True)
