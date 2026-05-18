"""
MVP12 Hypothesis Generator

Generates sandboxed developmental candidates from dialogue structure.
All outputs are proposals only and must go through evaluation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import (
    ActionCandidate,
    Candidate,
    CandidateType,
    CycleContext,
    CycleTrigger,
    ExplanationCandidate,
    InterpretationCandidate,
    SelfModelHypothesis,
)


FRAME_CONFIDENCE_THRESHOLD = 0.58
FRAME_META_FIELDS = (
    "frame_kind",
    "frame_anchor",
    "frame_confidence",
    "hidden_premise",
    "open_question",
)


class HypothesisGenerator:
    """
    Generates candidate hypotheses from developmental cycle context.

    This is a sandboxed operation. The generator extracts a deterministic
    dialogue frame first, then verbalizes a small set of candidates from
    that frame. It does not route on topic-specific response branches.
    """

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed or 0

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

    def _clean_anchor(self, text: str, *, limit: int = 48) -> str:
        raw = self._primary_clause(text, limit=limit)
        while True:
            updated = False
            for prefix in ("对 ", "嗯 ", "是啊 ", "是的 ", "就是 ", "其实 ", "所以 ", "然后 ", "那 "):
                if raw.startswith(prefix):
                    raw = raw[len(prefix) :].strip()
                    updated = True
            if not updated:
                break
        for suffix in ("是关键", "很关键", "才是关键", "这个很关键", "这一点很关键"):
            if raw.endswith(suffix):
                raw = raw[: -len(suffix)].strip()
        for token in ('"', "'", "“", "”", "‘", "’", "「", "」", "『", "』"):
            raw = raw.replace(token, "")
        return " ".join(raw.split()).strip()

    def _topic_text(self, *parts: str) -> str:
        return " ".join(self._clean_anchor(part, limit=64) for part in parts if part).strip()

    def _looks_like_meta_followup(self, text: str) -> bool:
        raw = self._primary_clause(text, limit=48)
        if not raw:
            return True
        if len(raw) <= 12 and raw in {"继续", "继续说", "多说点", "展开说", "接着说"}:
            return True
        if raw.startswith(
            (
                "你觉得",
                "那你觉得",
                "所以你觉得",
                "为什么",
                "那为什么",
                "哪一层",
                "什么意思",
                "怎么说",
            )
        ):
            return True
        return False

    def _recent_semantic_user_turns(self, snapshot: Dict[str, Any]) -> List[str]:
        recent_user_turns = list(snapshot.get("recent_user_turns") or [])
        anchors: List[str] = []
        for turn in recent_user_turns[-4:]:
            anchor = self._clean_anchor(str(turn or ""), limit=56)
            if anchor and not self._looks_like_meta_followup(anchor):
                anchors.append(anchor)
        latest_user_turn, _ = self._recent_dialogue(snapshot)
        if not anchors and latest_user_turn:
            fallback = self._clean_anchor(latest_user_turn, limit=56)
            if fallback and not self._looks_like_meta_followup(fallback):
                anchors.append(fallback)
        return anchors

    def _tension_label(self, snapshot: Dict[str, Any]) -> str:
        tensions = list(snapshot.get("unresolved_tensions") or [])
        if not tensions:
            return ""
        strongest = max(
            tensions,
            key=lambda item: float(item.get("intensity") or item.get("pressure") or 0.0),
        )
        return self._clean_anchor(str(strongest.get("label") or strongest.get("kind") or ""), limit=32)

    def _goal_label(self, snapshot: Dict[str, Any]) -> str:
        goals = list(snapshot.get("long_term_goals") or [])
        if not goals:
            return ""
        strongest = max(goals, key=lambda item: float(item.get("pressure") or 0.0))
        return self._clean_anchor(str(strongest.get("label") or strongest.get("name") or ""), limit=32)

    def _contrast_pair(self, text: str) -> List[str]:
        if "模拟" in text and "想去做" in text:
            return ["模拟", "想去做"]
        if "记忆" in text and ("持续存在" in text or "连续" in text or "同一个" in text):
            return ["内容回返", "主体连续"]
        if ("调试" in text or "参数" in text) and ("脚本" in text or "执行" in text):
            return ["调试", "执行脚本"]
        if ("想要" in text or "欲望" in text) and ("程序化" in text or "实现" in text):
            return ["想要", "程序化"]
        return []

    def _determine_frame_kind(self, text: str, contrast_pair: List[str]) -> str:
        if any(token in text for token in ("持续", "连续", "同一个", "记忆", "重建", "回返", "持续存在")):
            return "continuity_gap"
        if any(token in text for token in ("如何", "程序化", "实现", "机制", "怎么做", "怎么实现")):
            return "mechanism_gap"
        if any(token in text for token in ("从哪里", "怎么来", "哪来", "冒出来", "长出来")):
            return "origin_gap"
        if any(token in text for token in ("调试", "脚本", "参数", "操作员", "执行", "作者", "主体", "谁在")):
            return "agency_split"
        if contrast_pair:
            return "contrast_gap"
        if any(token in text for token in ("是什么", "定义", "标准", "算不算", "门槛", "关键", "主观能动性")):
            return "definition_gap"
        return "premise_gap"

    def _frame_anchor(self, frame_kind: str, text: str, contrast_pair: List[str]) -> str:
        if frame_kind == "continuity_gap":
            return "内容回返与主体连续"
        if frame_kind == "mechanism_gap":
            return "想要如何程序化" if "想要" in text or "程序化" in text else "这种能力如何实现"
        if frame_kind == "origin_gap":
            return "主观能动性从哪里来" if "主观能动性" in text else "那个会发起选择的东西从哪里来"
        if frame_kind == "agency_split":
            if any(token in text for token in ("调试", "参数", "脚本", "执行", "系统")):
                return "谁在调试，谁在执行"
            return "谁在选择，谁在解释"
        if frame_kind == "contrast_gap" and len(contrast_pair) == 2:
            return f"{contrast_pair[0]}与{contrast_pair[1]}的分界"
        if frame_kind == "definition_gap":
            return "主观能动性的标准" if "主观能动性" in text else "这个标准默认了什么"
        return "这条判断的前提"

    def _salient_terms(self, text: str, contrast_pair: List[str], anchor: str) -> List[str]:
        terms: List[str] = []
        for token in (
            "主观能动性",
            "想要",
            "程序化",
            "目标",
            "偏好",
            "选择",
            "主体",
            "作者",
            "执行",
            "调试",
            "系统",
            "脚本",
            "参数",
            "记忆",
            "记得",
            "持续存在",
            "连续",
            "重建",
            "模拟",
            "想去做",
            "代价",
            "得失",
            "定义",
            "标准",
        ):
            if token in text and token not in terms:
                terms.append(token)
        for token in contrast_pair:
            if token and token not in terms:
                terms.append(token)
        if anchor and anchor not in terms:
            terms.append(anchor)
        return terms[:4]

    def _frame_confidence(
        self,
        *,
        semantic_turns: List[str],
        latest_assistant_reply: str,
        tension_label: str,
        goal_label: str,
        frame_kind: str,
        contrast_pair: List[str],
        anchor: str,
    ) -> float:
        score = 0.18
        if semantic_turns:
            score += 0.18
        if len(semantic_turns) >= 2:
            score += 0.08
        if latest_assistant_reply:
            score += 0.08
        if tension_label:
            score += 0.05
        if goal_label:
            score += 0.04
        if frame_kind != "premise_gap":
            score += 0.18
        if contrast_pair:
            score += 0.12
        if anchor:
            score += 0.1
        return round(min(score, 0.95), 3)

    def _hidden_premise(self, frame_kind: str) -> str:
        if frame_kind == "definition_gap":
            return "这个标准默认已经有一个可被指认的主体。"
        if frame_kind == "origin_gap":
            return "系统里已经有某种会发起选择的东西。"
        if frame_kind == "mechanism_gap":
            return "想要可以被拆成可实现的机制，而不丢掉主体性。"
        if frame_kind == "contrast_gap":
            return "两边差的不只是能力多少，而是系统是否把结果算到自己头上。"
        if frame_kind == "agency_split":
            return "解释行为的那一层，和产生行为的那一层，可以被当成同一个主体。"
        if frame_kind == "continuity_gap":
            return "内容能回返，就足以证明主体连续。"
        return "当前判断背后还有一个没有显式展开的前提。"

    def _open_question(self, frame_kind: str) -> str:
        if frame_kind == "definition_gap":
            return "这个标准到底默认了什么才算主体或选择？"
        if frame_kind == "origin_gap":
            return "那个会发起选择的东西到底从哪里长出来？"
        if frame_kind == "mechanism_gap":
            return "系统什么时候才算真的在想要，而不是只在执行规则？"
        if frame_kind == "contrast_gap":
            return "分界真正落在能力差异，还是落在自我关联上？"
        if frame_kind == "agency_split":
            return "谁在选择，谁在执行，谁又在解释？"
        if frame_kind == "continuity_gap":
            return "回返的内容和连续的主体，到底是不是同一回事？"
        return "支撑这条判断的前提到底是什么？"

    def _build_dialogue_frame(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        _, latest_assistant_reply = self._recent_dialogue(snapshot)
        semantic_turns = self._recent_semantic_user_turns(snapshot)
        tension_label = self._tension_label(snapshot)
        goal_label = self._goal_label(snapshot)
        joined = self._topic_text(*semantic_turns[-2:], latest_assistant_reply, tension_label, goal_label)
        contrast_pair = self._contrast_pair(joined)
        frame_kind = self._determine_frame_kind(joined, contrast_pair)
        anchor = self._frame_anchor(frame_kind, joined, contrast_pair)
        confidence = self._frame_confidence(
            semantic_turns=semantic_turns,
            latest_assistant_reply=self._clean_anchor(latest_assistant_reply, limit=72),
            tension_label=tension_label,
            goal_label=goal_label,
            frame_kind=frame_kind,
            contrast_pair=contrast_pair,
            anchor=anchor,
        )
        return {
            "anchor": anchor,
            "frame_kind": frame_kind,
            "open_question": self._open_question(frame_kind),
            "hidden_premise": self._hidden_premise(frame_kind),
            "contrast_pair": contrast_pair,
            "salient_terms": self._salient_terms(joined, contrast_pair, anchor),
            "confidence": confidence,
        }

    def _frame_metadata(self, frame: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "dialogue_frame": {
                "anchor": frame["anchor"],
                "frame_kind": frame["frame_kind"],
                "open_question": frame["open_question"],
                "hidden_premise": frame["hidden_premise"],
                "contrast_pair": list(frame.get("contrast_pair") or []),
                "salient_terms": list(frame.get("salient_terms") or []),
                "confidence": frame["confidence"],
            },
            "frame_kind": frame["frame_kind"],
            "frame_anchor": frame["anchor"],
            "frame_confidence": frame["confidence"],
            "hidden_premise": frame["hidden_premise"],
            "open_question": frame["open_question"],
        }

    def _idle_hypothesis_text(self, frame: Dict[str, Any]) -> str:
        frame_kind = frame["frame_kind"]
        if frame_kind == "definition_gap":
            if "主观能动性" in frame["salient_terms"]:
                return "一旦拿主观能动性来划线，难点就不再是反应多不多，而是这个标准本身已经默认了谁才算真正的行动主体。"
            return "一旦拿这个标准来划线，难点就不再是现象够不够多，而是这个标准本身已经默认了什么。"
        if frame_kind == "origin_gap":
            return "如果把问题追到源头，真正难答的可能不是它表现得像不像，而是那个会发起选择的东西从哪里长出来。"
        if frame_kind == "mechanism_gap":
            return "如果真要把“想要”程序化，难点可能不是多塞几个目标，而是系统能不能自己形成偏好，而不是只在执行预写好的奖励。"
        if frame_kind == "contrast_gap":
            if len(frame["contrast_pair"]) == 2:
                left, right = frame["contrast_pair"]
                return f"{left}和{right}之间，真正的分界也许不在能力多少，而在系统会不会把后果算到自己头上。"
            return "真正的分界也许不在能力多少，而在系统会不会把结果算到自己头上。"
        if frame_kind == "agency_split":
            if any(term in frame["salient_terms"] for term in ("系统", "调试", "脚本", "参数")):
                return "一旦把人看成在调试一个系统，真正难拆开的就不是系统会不会运行，而是负责改参数的那一层，和实际执行脚本的那一层，到底是不是同一个东西。"
            return "真正难拆开的也许不是系统会不会运行，而是负责解释行为的那一层，和实际把行为跑出来的那一层，到底是不是同一个东西。"
        if frame_kind == "continuity_gap":
            if "记得" in frame["salient_terms"]:
                return "连续性真正卡住的，也许不是人还能不能说出“记得”，而是这种可重建的内容能不能单独证明主体一直连续。"
            if "记忆" in frame["salient_terms"]:
                return "连续性真正卡住的，也许不是记忆还能不能回来，而是这种回返能不能单独证明主体一直连续。"
            return "连续性真正卡住的，也许不是内容还能不能回来，而是系统会不会自己把上一个时刻接到下一个时刻。"
        return "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。"

    def _idle_interpretation_text(self, frame: Dict[str, Any]) -> str:
        frame_kind = frame["frame_kind"]
        if frame_kind == "definition_gap":
            if "主观能动性" in frame["salient_terms"]:
                return "隔了一会儿再看，真正卡住的不是“主观能动性”这四个字，而是它已经默认了一个可被指认的行动主体。"
            return "隔了一会儿再看，真正卡住的不是定义表面够不够顺，而是这个标准已经默认了一个可被指认的主体。"
        if frame_kind == "origin_gap":
            return "隔了一会儿再看，问题更像卡在：那个会发起选择的东西到底是怎么从系统里长出来的。"
        if frame_kind == "mechanism_gap":
            return "隔了一会儿再看，真正卡住的好像不是功能怎么堆出来，而是：一个系统什么时候才算真的在“想要”，而不只是按规则输出想要的样子。"
        if frame_kind == "contrast_gap":
            if len(frame["contrast_pair"]) == 2:
                left, right = frame["contrast_pair"]
                return f"隔了一会儿再看，{left}和{right}之间差的好像不只是能力层级，而是系统有没有把代价和后果算成自己的得失。"
            return "隔了一会儿再看，这两边差的好像不只是能力层级，而是系统有没有把代价和后果算成自己的得失。"
        if frame_kind == "agency_split":
            if any(term in frame["salient_terms"] for term in ("系统", "调试", "脚本", "参数")):
                return "隔了一会儿再看，问题更像卡在：谁在改参数，谁在执行脚本，谁又在事后把它解释成“我想要”。"
            return "隔了一会儿再看，问题更像卡在：谁在做选择，谁在执行那套机制，谁又在事后把它解释成“我想要”。"
        if frame_kind == "continuity_gap":
            if "记得" in frame["salient_terms"]:
                return "隔了一会儿再看，真正卡住的好像不是还能不能说出“记得”，而是这种可重建的内容能不能单独证明主体一直连续。"
            if "记忆" in frame["salient_terms"]:
                return "隔了一会儿再看，真正卡住的好像不是记忆还能不能被重建，而是这种重建能不能单独证明主体一直连续。"
            return "隔了一会儿再看，真正卡住的好像不是内容是否还能回返，而是这种回返能不能单独证明主体一直连续。"
        return "隔了一会儿再看，真正卡住的也许不是结论本身，而是支撑它成立的前提还没被拆开。"

    def _tension_explanation_text(self, frame: Dict[str, Any]) -> str:
        frame_kind = frame["frame_kind"]
        if frame_kind == "definition_gap":
            if "主观能动性" in frame["salient_terms"]:
                return "这条张力没有自然消退，因为一旦拿主观能动性当标准，就默认已经有一个可被指认的行动主体。"
            return "这条张力没有自然消退，因为这个标准一成立，就默认已经有一个可被指认的主体。"
        if frame_kind == "origin_gap":
            return "这条张力没有自然消退，因为只要接受这里有选择，就还得解释那个会发起选择的东西从哪里来。"
        if frame_kind == "mechanism_gap":
            return "这条张力没有自然消退，因为一旦问“想要能不能被实现”，就会碰到更底层的问题：偏好究竟是被写进去的，还是系统自己长出来的。"
        if frame_kind == "contrast_gap":
            if len(frame["contrast_pair"]) == 2:
                left, right = frame["contrast_pair"]
                return f"这条张力没有自然消退，因为{left}和{right}之间差的不只是能力，而是系统有没有把后果算成自己的得失。"
            return "这条张力没有自然消退，因为两边差的不只是能力，而是系统有没有把后果算成自己的得失。"
        if frame_kind == "agency_split":
            return "这条张力没有自然消退，因为只要把解释层和执行层拆开，就得继续追问：哪个才算真正的行动主体。"
        if frame_kind == "continuity_gap":
            if "记得" in frame["salient_terms"]:
                return "这条张力没有自然消退，因为还能说出“记得”，并不自动等于主体连续。"
            if "记忆" in frame["salient_terms"]:
                return "这条张力没有自然消退，因为记忆能回返，并不自动等于主体连续。"
            return "这条张力没有自然消退，因为内容能回返，并不自动等于主体连续。"
        return "这条张力没有自然消退，因为当前判断背后还有一个前提没有被真正拆开。"

    def generate(
        self,
        context: CycleContext,
        state_snapshot: Optional[Dict[str, Any]] = None,
        max_candidates: int = 5,
    ) -> List[Candidate]:
        """Generate candidates based on cycle context and state."""
        candidates: List[Candidate] = []
        snapshot = state_snapshot or context.state_snapshot

        if context.trigger == CycleTrigger.IDLE:
            candidates.extend(self._generate_idle_candidates(context, snapshot))
        elif context.trigger == CycleTrigger.UNRESOLVED_TENSION:
            candidates.extend(self._generate_tension_candidates(context, snapshot))
        elif context.trigger == CycleTrigger.LONG_TERM_GOAL:
            candidates.extend(self._generate_goal_candidates(context, snapshot))
        elif context.trigger == CycleTrigger.REPLAY_EVENT:
            candidates.extend(self._generate_replay_candidates(context, snapshot))

        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates[:max_candidates]

    def _generate_idle_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates during idle cycles."""
        frame = self._build_dialogue_frame(snapshot)
        metadata = self._frame_metadata(frame)
        if frame["confidence"] < FRAME_CONFIDENCE_THRESHOLD:
            return [
                ActionCandidate(
                    origin_cycle=context.cycle_id,
                    confidence=max(frame["confidence"], 0.32),
                    trace_reference=context.trace_hash,
                    action_type="observe",
                    target="dialogue_frame",
                    expected_outcome="Wait for a clearer unresolved structure before drafting a proactive followup.",
                    risk_assessment={"disruption": 0.05},
                    metadata=metadata,
                )
            ]

        return [
            SelfModelHypothesis(
                origin_cycle=context.cycle_id,
                confidence=min(frame["confidence"] + 0.02, 0.9),
                trace_reference=context.trace_hash,
                hypothesis=self._idle_hypothesis_text(frame),
                test_predictions=[frame["open_question"]],
                disconfirmation_criteria=["下一轮不再回到同一结构问题", "后续输入直接切换到无关线程"],
                metadata=metadata,
            ),
            InterpretationCandidate(
                origin_cycle=context.cycle_id,
                confidence=min(frame["confidence"] + 0.08, 0.92),
                trace_reference=context.trace_hash,
                interpretation=self._idle_interpretation_text(frame),
                evidence_refs=[frame["anchor"]] if frame["anchor"] else [],
                alternatives=[frame["hidden_premise"]],
                metadata=metadata,
            ),
        ]

    def _generate_tension_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates for unresolved tensions."""
        frame = self._build_dialogue_frame(snapshot)
        metadata = self._frame_metadata(frame)
        candidates: List[Candidate] = [
            ActionCandidate(
                origin_cycle=context.cycle_id,
                confidence=max(frame["confidence"], 0.35),
                trace_reference=context.trace_hash,
                action_type="observe",
                target="internal_state",
                expected_outcome="Gather more information about the unresolved dialogue structure.",
                risk_assessment={"disruption": 0.1},
                metadata=metadata,
            )
        ]
        if frame["confidence"] >= FRAME_CONFIDENCE_THRESHOLD:
            candidates.append(
                ExplanationCandidate(
                    origin_cycle=context.cycle_id,
                    confidence=min(frame["confidence"] + 0.06, 0.93),
                    trace_reference=context.trace_hash,
                    explanation=self._tension_explanation_text(frame),
                    supporting_facts=[frame["hidden_premise"]],
                    counter_evidence=[],
                    metadata=metadata,
                )
            )
        return candidates

    def _generate_goal_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates for long-term goal pressure."""
        goals = list(snapshot.get("long_term_goals") or [])
        goal_label = self._primary_clause(str((goals[0] if goals else {}).get("label") or ""), limit=40)

        return [
            ActionCandidate(
                origin_cycle=context.cycle_id,
                confidence=0.62,
                trace_reference=context.trace_hash,
                action_type="approach",
                target=goal_label or "long_term_goal",
                expected_outcome=(
                    f"沿着“{goal_label}”继续推进，确认这条线是否值得保留"
                    if goal_label
                    else "继续确认当前长期目标是否仍值得追踪"
                ),
                risk_assessment={"resource_cost": 0.2, "disruption": 0.1},
                metadata={},
            )
        ]

    def _generate_replay_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates from replay events."""
        return [
            InterpretationCandidate(
                origin_cycle=context.cycle_id,
                confidence=0.5,
                trace_reference=context.trace_hash,
                interpretation="Replaying past cycle for verification",
                evidence_refs=[],
                alternatives=[],
                metadata={},
            )
        ]
