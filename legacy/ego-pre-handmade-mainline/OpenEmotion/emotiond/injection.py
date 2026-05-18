"""MVP-6.2 D1: Priority injection + prompt budget allocator.

Deterministic assembly rules:
- Sort by priority (ascending) with stable tie handling so higher priority appears
  closer to prompt tail.
- Hard 3KB (default) UTF-8 byte cap.
- Degrade order: drop low-priority -> summarize -> pointer-only.
- Emit audit trail with source/priority/truncation reason/bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from emotiond import config as emotiond_config


@dataclass(frozen=True)
class Injection:
    text: str
    priority: float
    token_budget: int
    ttl: Optional[int]
    source: str
    safety_level: str


@dataclass(frozen=True)
class InjectionAllocatorConfig:
    max_bytes: int = 3072
    summary_max_chars: int = 180
    summary_suffix: str = " ... [summary]"
    pointer_template: str = "[PTR source={source} idx={idx}]"

    @classmethod
    def from_auto_tune(cls) -> "InjectionAllocatorConfig":
        return cls(
            max_bytes=max(256, int(emotiond_config.get_auto_tune_param("inj_max_bytes", 3072))),
            summary_max_chars=max(24, int(emotiond_config.get_auto_tune_param("inj_summary_max_chars", 180))),
        )


@dataclass(frozen=True)
class InjectionAuditEntry:
    source: str
    priority: float
    safety_level: str
    token_budget: int
    ttl: Optional[int]
    original_bytes: int
    final_bytes: int
    truncation_reason: str


@dataclass(frozen=True)
class PromptAssembly:
    prompt_block: str
    total_bytes: int
    items: List[InjectionAuditEntry]


def _utf8_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def _truncate_utf8_to_bytes(text: str, byte_limit: int) -> str:
    if byte_limit <= 0:
        return ""
    buf = text.encode("utf-8")
    if len(buf) <= byte_limit:
        return text
    return buf[:byte_limit].decode("utf-8", errors="ignore")


def _summarize(text: str, max_chars: int, suffix: str) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + suffix


def assemble_injections(
    injections: List[Injection],
    cfg: Optional[InjectionAllocatorConfig] = None,
) -> PromptAssembly:
    """Assemble injection block deterministically under a strict byte budget."""
    cfg = cfg or InjectionAllocatorConfig.from_auto_tune()

    indexed = list(enumerate(injections))
    # Stable sort: Python sort is stable; index keeps deterministic tie behavior.
    indexed.sort(key=lambda x: (x[1].priority, x[0]))

    records = []
    for idx, inj in indexed:
        text = inj.text or ""
        records.append(
            {
                "idx": idx,
                "inj": inj,
                "current": text,
                "reason": "kept",
                "original_bytes": _utf8_bytes(text),
            }
        )

    def build_prompt_bytes(items: List[dict]) -> tuple[str, int]:
        kept = [r["current"] for r in items if r["reason"] != "dropped_low_priority"]
        block = "\n\n".join(kept)
        return block, _utf8_bytes(block)

    block, total_bytes = build_prompt_bytes(records)

    # Stage 1: drop low-priority items first.
    i = 0
    while total_bytes > cfg.max_bytes and i < len(records):
        if records[i]["reason"] != "dropped_low_priority":
            records[i]["current"] = ""
            records[i]["reason"] = "dropped_low_priority"
            block, total_bytes = build_prompt_bytes(records)
        i += 1

    # Stage 2: summarize remaining long items, low priority first.
    if total_bytes > cfg.max_bytes:
        for rec in records:
            if rec["reason"] == "dropped_low_priority":
                continue
            summarized = _summarize(rec["current"], cfg.summary_max_chars, cfg.summary_suffix)
            if summarized != rec["current"]:
                rec["current"] = summarized
                rec["reason"] = "summarized"
                block, total_bytes = build_prompt_bytes(records)
                if total_bytes <= cfg.max_bytes:
                    break

    # Stage 3: pointer-only fallback, low priority first.
    if total_bytes > cfg.max_bytes:
        for rec in records:
            if rec["reason"] == "dropped_low_priority":
                continue
            ptr = cfg.pointer_template.format(source=rec["inj"].source, idx=rec["idx"])
            if rec["current"] != ptr:
                rec["current"] = ptr
                rec["reason"] = "pointer_only"
                block, total_bytes = build_prompt_bytes(records)
                if total_bytes <= cfg.max_bytes:
                    break

    # Final hard-guard: never exceed budget.
    if total_bytes > cfg.max_bytes:
        block = _truncate_utf8_to_bytes(block, cfg.max_bytes)
        total_bytes = _utf8_bytes(block)

    audits: List[InjectionAuditEntry] = []
    for rec in records:
        inj = rec["inj"]
        final_text = rec["current"]
        final_reason = rec["reason"]
        final_bytes = 0 if final_reason == "dropped_low_priority" else _utf8_bytes(final_text)
        audits.append(
            InjectionAuditEntry(
                source=inj.source,
                priority=inj.priority,
                safety_level=inj.safety_level,
                token_budget=inj.token_budget,
                ttl=inj.ttl,
                original_bytes=rec["original_bytes"],
                final_bytes=final_bytes,
                truncation_reason=final_reason,
            )
        )

    return PromptAssembly(prompt_block=block, total_bytes=total_bytes, items=audits)
