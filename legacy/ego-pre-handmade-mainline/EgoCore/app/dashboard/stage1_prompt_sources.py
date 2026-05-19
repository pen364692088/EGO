from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import html
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_USER_AGENT = "EgoCodexStage1PromptBuilder/1.0"
_HTML_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_DISALLOWED_PROMPT_PATTERNS = (
    re.compile(r"^/"),
    re.compile(r"```"),
    re.compile(r"\b(?:curl|wget|pip|python|bash|git)\b", re.IGNORECASE),
    re.compile(r"(?:帮我|替我|请你).{0,8}(?:执行|运行|调用|打开|搜索)"),
)


@dataclass(frozen=True)
class DashboardStage1PromptProvenance:
    source_kind: str
    source_label: str
    derivation: str
    source_ref: str | None = None
    normalization_applied: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_label": self.source_label,
            "derivation": self.derivation,
            "source_ref": self.source_ref,
            "normalization_applied": self.normalization_applied,
        }


@dataclass(frozen=True)
class DashboardStage1Prompt:
    prompt_id: str
    label: str
    text: str
    input_provenance: DashboardStage1PromptProvenance


@dataclass(frozen=True)
class DashboardStage1PromptPack:
    pack_id: str
    strategy: str
    prompts: tuple[DashboardStage1Prompt, ...]
    prompt_source_counts: dict[str, int]
    prompt_pack_degraded: bool
    prompt_pack_summary: dict[str, Any]


@dataclass(frozen=True)
class _PublicWebSeed:
    url: str
    label: str


_REPO_AUTHORED_CONTROL_PROMPTS = (
    ("greeting", "greeting", "你好啊"),
    ("ordinary_ask", "ordinary ask", "你现在想继续聊什么？"),
)

_GENERATED_ORDINARY_CHAT_CANDIDATES = (
    "如果今天只留一个轻松的话题，你会想先聊什么？",
    "最近要是有点分心，你通常会怎么把自己拉回来？",
    "如果刚结束一个话题，你一般会怎么自然接下一个？",
    "有时候不想太严肃聊天时，你会想聊哪种小话题？",
    "如果现在想换个不费劲的话题，你会往哪个方向拐？",
    "你觉得日常聊天里，什么问题最容易让人放松下来？",
)

_LOCAL_CHATLOG_CURATED_SEEDS = (
    (
        "chatlog_seed_topic_shift",
        "repo seed: topic shift",
        "如果一个话题聊到一半想换个方向，你一般会怎么接？",
    ),
    (
        "chatlog_seed_light_reconnect",
        "repo seed: light reconnect",
        "要是隔了一会儿再继续聊天，你通常会从哪里重新接上？",
    ),
)

_PUBLIC_WEB_SEEDS = (
    _PublicWebSeed(url="https://news.ycombinator.com/", label="Hacker News front page"),
    _PublicWebSeed(url="https://www.wikipedia.org/", label="Wikipedia home page"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_user_turn(text: str) -> str | None:
    normalized = _WHITESPACE_RE.sub(" ", str(text or "").strip())
    if not normalized:
        return None
    if len(normalized) > 120:
        normalized = normalized[:117].rstrip(" ,，。！？?!.") + "？"
    if len(normalized) < 2:
        return None
    if any(pattern.search(normalized) for pattern in _DISALLOWED_PROMPT_PATTERNS):
        return None
    return normalized


def _build_prompt(
    *,
    prompt_id: str,
    label: str,
    text: str,
    source_kind: str,
    source_label: str,
    derivation: str,
    source_ref: str | None,
    normalization_applied: bool,
) -> DashboardStage1Prompt | None:
    normalized = _normalize_user_turn(text)
    if not normalized:
        return None
    return DashboardStage1Prompt(
        prompt_id=prompt_id,
        label=label,
        text=normalized,
        input_provenance=DashboardStage1PromptProvenance(
            source_kind=source_kind,
            source_label=source_label,
            derivation=derivation,
            source_ref=source_ref,
            normalization_applied=normalization_applied or normalized != text,
        ),
    )


def _repo_authored_control_prompts() -> list[DashboardStage1Prompt]:
    prompts: list[DashboardStage1Prompt] = []
    for prompt_id, label, text in _REPO_AUTHORED_CONTROL_PROMPTS:
        prompt = _build_prompt(
            prompt_id=prompt_id,
            label=label,
            text=text,
            source_kind="repo_authored_control",
            source_label=f"repo control:{label}",
            derivation="native",
            source_ref=f"internal:repo_authored_control:{prompt_id}",
            normalization_applied=False,
        )
        if prompt is not None:
            prompts.append(prompt)
    return prompts


def _generated_prompt_candidates(*, now: datetime) -> list[DashboardStage1Prompt]:
    start_index = now.toordinal() % len(_GENERATED_ORDINARY_CHAT_CANDIDATES)
    prompts: list[DashboardStage1Prompt] = []
    for offset, text in enumerate(_GENERATED_ORDINARY_CHAT_CANDIDATES, start=0):
        candidate_text = _GENERATED_ORDINARY_CHAT_CANDIDATES[(start_index + offset) % len(_GENERATED_ORDINARY_CHAT_CANDIDATES)]
        prompt = _build_prompt(
            prompt_id=f"generated_{offset + 1}",
            label=f"generated {offset + 1}",
            text=candidate_text,
            source_kind="generated",
            source_label="local generated ordinary-chat template",
            derivation="generated",
            source_ref=f"internal:generated_ordinary_chat_v1:{(start_index + offset) % len(_GENERATED_ORDINARY_CHAT_CANDIDATES)}",
            normalization_applied=False,
        )
        if prompt is not None:
            prompts.append(prompt)
    return prompts


def _select_generated_prompts(*, now: datetime, count: int, start_offset: int = 0) -> list[DashboardStage1Prompt]:
    candidates = _generated_prompt_candidates(now=now)
    selected: list[DashboardStage1Prompt] = []
    for prompt in candidates[start_offset:]:
        if prompt.text in {item.text for item in selected}:
            continue
        selected.append(prompt)
        if len(selected) >= count:
            break
    for prompt in candidates:
        if len(selected) >= count:
            break
        if prompt.text in {item.text for item in selected}:
            continue
        selected.append(prompt)
    if len(selected) < count:
        raise RuntimeError("insufficient generated prompt candidates for Stage 1 prompt pack")
    return selected


def _select_local_chatlog_prompt(*, now: datetime) -> DashboardStage1Prompt | None:
    if not _LOCAL_CHATLOG_CURATED_SEEDS:
        return None
    seed_index = now.toordinal() % len(_LOCAL_CHATLOG_CURATED_SEEDS)
    seed_id, label, text = _LOCAL_CHATLOG_CURATED_SEEDS[seed_index]
    return _build_prompt(
        prompt_id="curated_chatlog",
        label="curated chatlog",
        text=text,
        source_kind="chatlog_curated",
        source_label=label,
        derivation="rewritten",
        source_ref=f"internal:chatlog_curated_v1:{seed_id}",
        normalization_applied=True,
    )


def _fetch_public_web_text(url: str, *, timeout: float) -> str | None:
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError):
        return None


def _extract_public_topic(html_text: str) -> str | None:
    title_match = _HTML_TITLE_RE.search(html_text)
    if title_match is None:
        return None
    title = html.unescape(_HTML_TAG_RE.sub(" ", title_match.group(1)))
    title = _WHITESPACE_RE.sub(" ", title).strip(" -|_")
    if not title:
        return None
    topic = re.split(r"\s+[|\-–—]\s+|[|·•]", title, maxsplit=1)[0].strip()
    topic = topic[:48].strip()
    return topic or None


def _select_external_curated_prompt(*, timeout: float) -> DashboardStage1Prompt | None:
    for seed in _PUBLIC_WEB_SEEDS:
        html_text = _fetch_public_web_text(seed.url, timeout=timeout)
        if not html_text:
            continue
        topic = _extract_public_topic(html_text)
        if not topic:
            continue
        prompt_text = f"刚看到一个和“{topic}”有关的话题，你会先从哪个角度聊起？"
        prompt = _build_prompt(
            prompt_id="curated_external",
            label="curated external",
            text=prompt_text,
            source_kind="external_curated",
            source_label=seed.label,
            derivation="rewritten",
            source_ref=seed.url,
            normalization_applied=True,
        )
        if prompt is not None:
            return prompt
    return None


def build_dashboard_stage1_prompt_pack(
    *,
    strategy: str = "hybrid",
    allow_public_web: bool = True,
    public_web_timeout: float = 5.0,
    now: datetime | None = None,
) -> DashboardStage1PromptPack:
    if strategy != "hybrid":
        raise ValueError(f"unsupported dashboard Stage 1 prompt source strategy: {strategy}")

    resolved_now = now or _utc_now()
    prompts: list[DashboardStage1Prompt] = []
    prompts.extend(_repo_authored_control_prompts())
    prompts.extend(_select_generated_prompts(now=resolved_now, count=2))

    prompt_pack_degraded = False
    curated_prompt = _select_local_chatlog_prompt(now=resolved_now)
    if curated_prompt is None and allow_public_web:
        curated_prompt = _select_external_curated_prompt(timeout=public_web_timeout)
    if curated_prompt is None:
        prompt_pack_degraded = True
        curated_prompt = _select_generated_prompts(now=resolved_now, count=1, start_offset=2)[0]
    prompts.append(curated_prompt)

    source_counts = dict(Counter(prompt.input_provenance.source_kind for prompt in prompts))
    prompt_pack_summary = {
        "strategy": strategy,
        "prompt_count": len(prompts),
        "source_sequence": [prompt.input_provenance.source_kind for prompt in prompts],
        "curated_slot_source": prompts[-1].input_provenance.source_kind,
        "allow_public_web": allow_public_web,
    }
    return DashboardStage1PromptPack(
        pack_id="stage1_dashboard_ordinary_chat_hybrid_v1",
        strategy=strategy,
        prompts=tuple(prompts),
        prompt_source_counts=source_counts,
        prompt_pack_degraded=prompt_pack_degraded,
        prompt_pack_summary=prompt_pack_summary,
    )


__all__ = [
    "DashboardStage1Prompt",
    "DashboardStage1PromptPack",
    "DashboardStage1PromptProvenance",
    "build_dashboard_stage1_prompt_pack",
]
