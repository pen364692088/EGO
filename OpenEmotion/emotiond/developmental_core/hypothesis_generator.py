"""
MVP12 Hypothesis Generator

Generates candidate hypotheses from cycle context.
All outputs are sandboxed candidates that must go through evaluation.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Dict, List, Optional

from .models import (
    Candidate,
    InterpretationCandidate,
    ActionCandidate,
    ExplanationCandidate,
    SelfModelHypothesis,
    CycleContext,
    CycleTrigger,
)


class HypothesisGenerator:
    """
    Generates candidate hypotheses from developmental cycle context.

    This is a sandboxed operation - outputs are proposals only and
    must go through Governor v2 for approval.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def _recent_dialogue(self, snapshot: Dict[str, Any]) -> tuple[str, str]:
        recent_user_turns = list(snapshot.get("recent_user_turns") or [])
        recent_assistant_replies = list(snapshot.get("recent_assistant_replies") or [])
        latest_user_turn = str(
            recent_user_turns[-1] if recent_user_turns else snapshot.get("ingress_text") or ""
        ).strip()
        latest_assistant_reply = str(
            recent_assistant_replies[-1] if recent_assistant_replies else snapshot.get("delivery_text") or ""
        ).strip()
        return latest_user_turn, latest_assistant_reply

    def _recent_semantic_user_anchor(self, snapshot: Dict[str, Any]) -> str:
        recent_user_turns = list(snapshot.get("recent_user_turns") or [])
        for turn in reversed(recent_user_turns[-4:]):
            anchor = self._clean_anchor(str(turn or ""), limit=48)
            if anchor and not self._looks_like_meta_followup(anchor):
                return anchor
        latest_user_turn, _ = self._recent_dialogue(snapshot)
        return self._clean_anchor(latest_user_turn, limit=48)

    def _primary_clause(self, text: str, *, limit: int = 48) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        for separator in ("。", "，", "？", "！", ":", "：", ".", ",", "?", "!"):
            raw = raw.split(separator, 1)[0].strip()
            if raw:
                break
        if len(raw) <= limit:
            return raw
        return raw[: limit - 1].rstrip() + "…"

    def _clean_anchor(self, text: str, *, limit: int = 40) -> str:
        raw = self._primary_clause(text, limit=limit)
        for token in ('"', "'", "“", "”", "‘", "’", "「", "」", "『", "』"):
            raw = raw.replace(token, "")
        return " ".join(raw.split()).strip()

    def _topic_text(self, *parts: str) -> str:
        return " ".join(self._clean_anchor(part, limit=64) for part in parts if part).strip()

    def _is_memory_continuity_topic(self, text: str) -> bool:
        return any(
            token in text
            for token in (
                "连续性",
                "记忆",
                "记得",
                "持续存在",
                "同一个自我",
                "同一个人",
                "同一个主体",
                "河流",
                "河道",
            )
        )

    def _looks_like_meta_followup(self, text: str) -> bool:
        raw = self._primary_clause(text, limit=48)
        if not raw:
            return True
        if len(raw) <= 10 and raw in {"继续", "继续说", "多说点", "展开说", "接着说"}:
            return True
        if raw.startswith(("你觉得", "那你觉得", "所以你觉得", "为什么", "那为什么", "哪一层", "什么意思")):
            return True
        return False

    def _semantic_anchor(self, snapshot: Dict[str, Any]) -> str:
        latest_user_turn, latest_assistant_reply = self._recent_dialogue(snapshot)
        latest_user_anchor = self._recent_semantic_user_anchor(snapshot)
        latest_reply_anchor = self._clean_anchor(latest_assistant_reply, limit=40)
        tension_anchor = self._tension_label(snapshot)

        if latest_user_anchor and not self._looks_like_meta_followup(latest_user_anchor):
            return latest_user_anchor
        if tension_anchor:
            return tension_anchor
        if latest_reply_anchor:
            return latest_reply_anchor
        return latest_user_anchor

    def _tension_label(self, snapshot: Dict[str, Any]) -> str:
        tensions = list(snapshot.get("unresolved_tensions") or [])
        if not tensions:
            return ""
        strongest = max(
            tensions,
            key=lambda item: float(item.get("intensity") or item.get("pressure") or 0.0),
        )
        return self._clean_anchor(str(strongest.get("label") or strongest.get("kind") or ""), limit=32)

    def _idle_hypothesis_text(self, anchor: str, latest_reply: str, tension_label: str) -> str:
        joined = self._topic_text(anchor, latest_reply, tension_label)
        if "主观能动性" in joined:
            return "如果把主观能动性当门槛，难点就不再是系统会不会反应，而是谁在发起那个“想要”。"
        if "操作员" in joined:
            return "那个像“操作员”的位置，也许不是系统外的谁，而是系统给自己生成的一层调度视角。"
        if "模拟" in joined and "想去做" in joined:
            return "内部模拟和真正想去做之间，差别也许不在预测能力，而在系统会不会把结果算成自己的得失。"
        if self._is_memory_continuity_topic(joined):
            return "连续性真正卡住的也许不是记住多少，而是系统会不会自己把上一个时刻接到下一个时刻。"
        if "意识" in joined:
            return "如果意识更像光谱，真正难画的线也许不是复杂度，而是什么时候系统开始把某些结果当成“与我有关”。"
        if anchor:
            return f"这条线真正没说透的，也许不是 {anchor} 本身，而是支撑它成立的那个前提。"
        return "表面上话题停住了，但真正没解开的部分可能是在系统内部如何给自己生成一个立场。"

    def _idle_interpretation_text(self, anchor: str, latest_reply: str, tension_label: str) -> str:
        joined = self._topic_text(anchor, latest_reply, tension_label)
        if "主观能动性" in joined:
            return "把主观能动性当标准，其实已经在默认有一个主体存在；而“主体从哪里来”刚好又是最难回答的部分。"
        if "操作员" in joined:
            return "“操作员”这个比喻之所以黏住不放，可能是因为它已经碰到了“谁在做选择”这层问题。"
        if "模拟" in joined and "想去做" in joined:
            return "这条线还没收束，因为模拟和欲望之间隔着的不只是能力差异，更像有没有把代价算到自己头上。"
        if self._is_memory_continuity_topic(joined):
            return "这条线会一直回弹，可能是因为“记得”只能证明内容还能被重建，证明不了那个重建它的主体一直没有断。"
        if "意识" in joined:
            return "这条线之所以反复出现，可能是因为它正在把“意识是什么”推进到“主体边界怎么成立”。"
        if anchor:
            return f"这条线没收住，像是因为 {anchor} 背后还有一个更基础的问题在顶着它。"
        if latest_reply:
            return f"刚才那层回答更像是把问题推近了一步，而不是把它真正关掉。"
        return "空档本身没有结束这条线，它更像是在给下一次重组留位置。"

    def _tension_explanation_text(self, anchor: str, latest_reply: str, tension_label: str) -> str:
        joined = self._topic_text(anchor, latest_reply, tension_label)
        if "主观能动性" in joined:
            return "真正持续回拉的，不是“主观能动性”这个词本身，而是一旦接受它，就必须解释那个行动主体从哪里来。"
        if "模拟" in joined and "想去做" in joined:
            return "当前张力更像卡在这里：预测未来并不等于对未来有欲望，分水岭可能是系统会不会把后果算成自己的得失。"
        if "操作员" in joined:
            return "这条张力没有自然消退，因为“操作员”这个比喻已经把问题推到了“谁在调度选择”这层。"
        if self._is_memory_continuity_topic(joined):
            return "这条张力没有自然消退，因为“记得”只能说明内容还在回返，却不能单独证明那个回返内容的主体一直连续存在。"
        if anchor:
            return f"当前张力没有自然消退，像是因为 {anchor} 背后还有一个更基础的问题没有被拆开。"
        if tension_label:
            return f"当前张力没有自然消退，更像是 {tension_label} 仍在内部占位。"
        return "当前张力没有自然消退，像是某个前提一直没有真正讲透。"

    def generate(
        self,
        context: CycleContext,
        state_snapshot: Optional[Dict[str, Any]] = None,
        max_candidates: int = 5,
    ) -> List[Candidate]:
        """Generate candidates based on cycle context and state."""
        candidates = []
        snapshot = state_snapshot or context.state_snapshot

        # Generate based on trigger type
        if context.trigger == CycleTrigger.IDLE:
            candidates.extend(self._generate_idle_candidates(context, snapshot))
        elif context.trigger == CycleTrigger.UNRESOLVED_TENSION:
            candidates.extend(self._generate_tension_candidates(context, snapshot))
        elif context.trigger == CycleTrigger.LONG_TERM_GOAL:
            candidates.extend(self._generate_goal_candidates(context, snapshot))
        elif context.trigger == CycleTrigger.REPLAY_EVENT:
            candidates.extend(self._generate_replay_candidates(context, snapshot))

        # Sort by confidence and limit
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates[:max_candidates]

    def _generate_idle_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates during idle cycles."""
        candidates = []
        latest_user_turn, latest_assistant_reply = self._recent_dialogue(snapshot)
        anchor = self._semantic_anchor(snapshot)
        tension_label = self._tension_label(snapshot)

        # Self-reflection hypothesis
        candidates.append(SelfModelHypothesis(
            origin_cycle=context.cycle_id,
            confidence=0.3 + self.rng.random() * 0.2,
            trace_reference=context.trace_hash,
            hypothesis=self._idle_hypothesis_text(anchor, latest_assistant_reply, tension_label),
            test_predictions=[
                f"如果再沿着“{anchor or '这个点'}”追问，系统还会继续回到同一条线。"
            ],
            disconfirmation_criteria=["话题迅速失去连续性", "下一轮完全不再指向当前主题"],
        ))

        # Exploration interpretation
        candidates.append(InterpretationCandidate(
            origin_cycle=context.cycle_id,
            confidence=0.4 + self.rng.random() * 0.2,
            trace_reference=context.trace_hash,
            interpretation=self._idle_interpretation_text(anchor, latest_assistant_reply, tension_label),
            evidence_refs=[anchor] if anchor else [],
            alternatives=["系统只是暂时安静了", "当前只是没有新输入，不代表内部已经收束"],
        ))

        return candidates

    def _generate_tension_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates for unresolved tensions."""
        candidates = []
        _, latest_assistant_reply = self._recent_dialogue(snapshot)
        anchor = self._semantic_anchor(snapshot)
        tension_label = self._tension_label(snapshot)

        # Tension explanation
        candidates.append(ExplanationCandidate(
            origin_cycle=context.cycle_id,
            confidence=0.5 + self.rng.random() * 0.3,
            trace_reference=context.trace_hash,
            explanation=self._tension_explanation_text(anchor, latest_assistant_reply, tension_label),
            supporting_facts=[f"{tension_label or 'tension'} exceeds threshold"],
            counter_evidence=[],
        ))

        # Resolution action
        candidates.append(ActionCandidate(
            origin_cycle=context.cycle_id,
            confidence=0.4 + self.rng.random() * 0.2,
            trace_reference=context.trace_hash,
            action_type="observe",
            target="internal_state",
            expected_outcome="Gather more information about tension source",
            risk_assessment={"disruption": 0.1},
        ))

        return candidates

    def _generate_goal_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates for long-term goal pressure."""
        candidates = []
        goals = list(snapshot.get("long_term_goals") or [])
        goal_label = self._primary_clause(str((goals[0] if goals else {}).get("label") or ""), limit=40)

        # Goal pursuit action
        candidates.append(ActionCandidate(
            origin_cycle=context.cycle_id,
            confidence=0.6 + self.rng.random() * 0.2,
            trace_reference=context.trace_hash,
            action_type="approach",
            target=goal_label or "long_term_goal",
            expected_outcome=(
                f"沿着“{goal_label}”继续推进，确认这条线是否值得保留"
                if goal_label
                else "继续确认当前长期目标是否仍值得追踪"
            ),
            risk_assessment={"resource_cost": 0.2, "disruption": 0.1},
        ))

        return candidates

    def _generate_replay_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates from replay events."""
        candidates = []

        # Replay interpretation
        candidates.append(InterpretationCandidate(
            origin_cycle=context.cycle_id,
            confidence=0.5,
            trace_reference=context.trace_hash,
            interpretation="Replaying past cycle for verification",
            evidence_refs=[],
            alternatives=[],
        ))

        return candidates
