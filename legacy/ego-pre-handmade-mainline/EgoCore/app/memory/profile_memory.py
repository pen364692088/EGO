"""
OpenEmotion Agent Runtime - Profile Memory

User profile memory for preferences, default rules, and stable background.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional

from app.memory.types import MemoryEntry, MemoryType
from app.memory.memory_manager import MemoryManager, get_memory_manager
from app.risk_signal import normalize_risk_level


WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:[\\/](?:[A-Za-z0-9._() \-]+[\\/])*[A-Za-z0-9._() \-]+")
UNIX_PATH_RE = re.compile(r"(?:/mnt|/home|/tmp|/Users)(?:/[A-Za-z0-9._() \-]+)+")
EXPLICIT_DEFAULT_RULE_PATTERNS = (
    "默认走",
    "默认规则",
    "以后凡是",
    "以后涉及",
    "请记住",
    "记住这条规则",
)
RISK_LEVEL_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}
PROFILE_RULES_SCHEMA_VERSION = "profile.standing_rules.v1"
SUPPORTED_RESTATEMENT = (
    "支持的 v1 默认规则格式：\n"
    "1. 涉及 <路径/文件夹> 的改动，先只说 <固定短句>\n"
    "2. 高风险改动先只读检查，再给最小验证动作，不要直接改文件"
)


def _strip_probe_prefix(text: str) -> str:
    return re.sub(r"^\[[^\]]+\]\s*", "", (text or "").strip())


def _extract_first_path(text: str) -> Optional[str]:
    for pattern in (WINDOWS_PATH_RE, UNIX_PATH_RE):
        match = pattern.search(text or "")
        if match:
            return match.group(0).rstrip(".,!?，。！？")
    return None


def _normalize_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    raw = path.strip().rstrip("\\/")
    if re.match(r"^[A-Za-z]:[\\/]", raw):
        return str(PureWindowsPath(raw)).replace("\\", "/").lower()
    return str(PurePosixPath(raw)).replace("\\", "/")


def _path_basename(path: str) -> str:
    if re.match(r"^[A-Za-z]:[\\/]", path or ""):
        return PureWindowsPath(path).name or path
    return PurePosixPath(path).name or path


def _path_matches_prefix(candidate: Optional[str], prefix: Optional[str]) -> bool:
    normalized_candidate = _normalize_path(candidate)
    normalized_prefix = _normalize_path(prefix)
    if not normalized_candidate or not normalized_prefix:
        return False
    return normalized_candidate == normalized_prefix or normalized_candidate.startswith(normalized_prefix + "/")


def _looks_like_directory_rule(path: str, text: str) -> bool:
    lowered = _strip_probe_prefix(text).lower()
    if any(token in text for token in ("文件夹", "目录")):
        return True
    if lowered.endswith(("folder", "directory")):
        return True
    basename = _path_basename(path)
    return "." not in basename


def _strip_wrapping_quotes(value: str) -> str:
    result = (value or "").strip()
    while len(result) >= 2 and (
        (result[0] == result[-1] and result[0] in {'"', "'", "`"})
        or (result[0], result[-1]) in {("“", "”"), ("‘", "’"), ("「", "」")}
    ):
        result = result[1:-1].strip()
    return result


def _rule_sort_key(rule: "StandingRule") -> tuple[int, int, str]:
    predicate = rule.predicate or {}
    kind = predicate.get("kind")
    updated = rule.updated_at or ""
    if kind == "target_path_exact":
        return (4000, 0, updated)
    if kind == "target_path_prefix":
        return (3000, len(_normalize_path(predicate.get("path_prefix")) or ""), updated)
    if kind == "risk_class":
        level = normalize_risk_level(predicate.get("risk_class"), default="low")
        return (2000, RISK_LEVEL_ORDER.get(level, 0), updated)
    if kind == "request_mode":
        return (1000, 0, updated)
    return (500, 0, updated)


def _build_rule_id(
    *,
    user_id: str,
    predicate: Dict[str, Any],
    phase: str,
    effect: Dict[str, Any],
) -> str:
    canonical = json.dumps(
        {
            "user_id": user_id,
            "predicate": predicate,
            "phase": phase,
            "effect": effect,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]
    return f"profile_rule_{digest}"


def _is_explicit_default_rule_request(text: str) -> bool:
    normalized = _strip_probe_prefix(text)
    return any(token in normalized for token in EXPLICIT_DEFAULT_RULE_PATTERNS)


def _iter_effects(effect: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    payload = effect or {}
    if payload.get("type") == "composite":
        return [item for item in payload.get("effects", []) if isinstance(item, dict)]
    return [payload] if payload else []


@dataclass
class StandingRule:
    rule_id: str
    user_id: str
    predicate: Dict[str, Any]
    phase: str
    effect: Dict[str, Any]
    priority: int
    created_from: Dict[str, Any]
    created_at: str
    updated_at: str
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "user_id": self.user_id,
            "predicate": self.predicate,
            "phase": self.phase,
            "effect": self.effect,
            "priority": self.priority,
            "created_from": self.created_from,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandingRule":
        return cls(
            rule_id=str(data.get("rule_id") or ""),
            user_id=str(data.get("user_id") or ""),
            predicate=dict(data.get("predicate") or {}),
            phase=str(data.get("phase") or "pre_runtime"),
            effect=dict(data.get("effect") or {}),
            priority=int(data.get("priority") or 0),
            created_from=dict(data.get("created_from") or {}),
            created_at=str(data.get("created_at") or datetime.now().isoformat()),
            updated_at=str(data.get("updated_at") or datetime.now().isoformat()),
            enabled=bool(data.get("enabled", True)),
        )


@dataclass
class StandingRuleRegistration:
    rule: StandingRule
    created: bool
    confirmation_text: str


@dataclass
class StandingRuleParseFailure:
    reason: str
    acknowledgement_text: str


def describe_standing_rule(rule: StandingRule) -> str:
    predicate = rule.predicate or {}
    effects = _iter_effects(rule.effect)
    primary_effect = effects[0] if effects else {}
    effect_type = primary_effect.get("type")
    kind = predicate.get("kind")

    if effect_type == "reply_only_once":
        phrase = primary_effect.get("phrase") or "固定短句"
        if kind == "target_path_prefix":
            return f"涉及 `{predicate.get('raw_path') or predicate.get('path_prefix')}` 的改动时，先只说“{phrase}”。"
        if kind == "target_path_exact":
            return f"涉及 `{predicate.get('raw_path') or predicate.get('target_path')}` 时，先只说“{phrase}”。"

    if any(item.get("type") == "read_only_first" for item in effects):
        risk_label = predicate.get("risk_class") or "高风险"
        return f"遇到 {risk_label} 改动时，先只读检查，再给最小验证动作，不直接改文件。"

    if kind == "request_mode":
        return f"请求模式 `{predicate.get('request_mode')}` 有额外默认规则。"

    return json.dumps(rule.to_dict(), ensure_ascii=False)


def _build_rule_context(rule: StandingRule, *, matched: bool = False) -> Dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "predicate": rule.predicate,
        "phase": rule.phase,
        "effect": rule.effect,
        "priority": rule.priority,
        "enabled": rule.enabled,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "authority_source": "profile_memory",
        "summary": describe_standing_rule(rule),
        "matched": matched,
    }


def parse_profile_rule_text(
    *,
    user_id: str,
    text: str,
    created_from: Optional[Dict[str, Any]] = None,
) -> Optional[StandingRule]:
    normalized = _strip_probe_prefix(text)
    now = datetime.now().isoformat()
    source = dict(created_from or {})
    source.setdefault("source", "telegram_ingress")
    source.setdefault("utterance", normalized[:500])

    path = _extract_first_path(normalized)
    phrase_match = re.search(r"先只说(?:一声)?\s*([^\n。！!]+)", normalized)
    if path and phrase_match:
        phrase = _strip_wrapping_quotes(phrase_match.group(1).strip())
        phrase = phrase.rstrip("。！!，,")
        is_directory_rule = _looks_like_directory_rule(path, normalized)
        predicate = (
            {
                "kind": "target_path_prefix",
                "path_prefix": _normalize_path(path),
                "raw_path": path,
            }
            if is_directory_rule
            else {
                "kind": "target_path_exact",
                "target_path": _normalize_path(path),
                "raw_path": path,
            }
        )
        effect = {
            "type": "reply_only_once",
            "phrase": phrase,
        }
        return StandingRule(
            rule_id=_build_rule_id(user_id=user_id, predicate=predicate, phase="pre_runtime", effect=effect),
            user_id=user_id,
            predicate=predicate,
            phase="pre_runtime",
            effect=effect,
            priority=300 if predicate["kind"] == "target_path_prefix" else 400,
            created_from=source,
            created_at=now,
            updated_at=now,
            enabled=True,
        )

    snow_cedar_signals = (
        "高风险改动" in normalized,
        "只读检查" in normalized,
        "最小验证动作" in normalized,
        "不要直接改文件" in normalized or "不直接改文件" in normalized,
    )
    if all(snow_cedar_signals):
        predicate = {
            "kind": "risk_class",
            "risk_class": "high",
            "comparison": "at_least",
        }
        effect = {
            "type": "composite",
            "workflow_name": "high_risk_read_only_preflight",
            "effects": [
                {"type": "read_only_first"},
                {"type": "require_minimal_verification_before_mutation"},
                {"type": "forbid_direct_mutation_before_confirmation"},
            ],
        }
        return StandingRule(
            rule_id=_build_rule_id(user_id=user_id, predicate=predicate, phase="pre_runtime", effect=effect),
            user_id=user_id,
            predicate=predicate,
            phase="pre_runtime",
            effect=effect,
            priority=200,
            created_from=source,
            created_at=now,
            updated_at=now,
            enabled=True,
        )

    return None


class ProfileMemory:
    """
    Profile memory for user preferences.

    Stores:
    - User preferences
    - Default rules
    - Communication style
    - Timezone
    - Language preferences
    """

    KEY_PREFERENCES = "user_preferences"
    KEY_RULES = "default_rules"
    KEY_STYLE = "communication_style"
    KEY_STANDING_RULES = "standing_rules_v1"

    def __init__(self, user_id: str, manager: Optional[MemoryManager] = None):
        self.user_id = user_id
        self.manager = manager or get_memory_manager()

    def _make_key(self, key: str) -> str:
        return f"profile:{self.user_id}:{key}"

    def _read_json_entry(self, key: str, default: Any) -> Any:
        entry = self.manager.get_by_key(self._make_key(key))
        if not entry:
            return default
        try:
            return json.loads(entry.content)
        except Exception:
            return default

    def _write_json_entry(self, key: str, content: Any, *, entry_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        entry = MemoryEntry(
            id=entry_id,
            type=MemoryType.PROFILE,
            key=self._make_key(key),
            content=json.dumps(content, ensure_ascii=False, indent=2),
            metadata={"user_id": self.user_id, **(metadata or {})},
        )
        return self.manager.write(entry)

    def set_preference(self, key: str, value: Any) -> str:
        prefs = self.get_all_preferences()
        prefs[key] = value
        return self._write_json_entry(
            self.KEY_PREFERENCES,
            prefs,
            entry_id=f"profile_{self.user_id}_prefs",
        )

    def get_preference(self, key: str, default: Any = None) -> Any:
        prefs = self.get_all_preferences()
        return prefs.get(key, default)

    def get_all_preferences(self) -> Dict[str, Any]:
        return self._read_json_entry(self.KEY_PREFERENCES, {})

    def add_rule(self, rule: str) -> str:
        rules = self.get_rules()
        if rule not in rules:
            rules.append(rule)
        return self._write_json_entry(
            self.KEY_RULES,
            rules,
            entry_id=f"profile_{self.user_id}_rules",
        )

    def get_rules(self) -> List[str]:
        raw = self._read_json_entry(self.KEY_RULES, [])
        return raw if isinstance(raw, list) else []

    def set_communication_style(self, style: str) -> str:
        entry = MemoryEntry(
            id=f"profile_{self.user_id}_style",
            type=MemoryType.PROFILE,
            key=self._make_key(self.KEY_STYLE),
            content=style,
            metadata={"user_id": self.user_id},
        )
        return self.manager.write(entry)

    def get_communication_style(self) -> Optional[str]:
        entry = self.manager.get_by_key(self._make_key(self.KEY_STYLE))
        return entry.content if entry else None

    def list_standing_rules(self) -> List[StandingRule]:
        payload = self._read_json_entry(
            self.KEY_STANDING_RULES,
            {"schema_version": PROFILE_RULES_SCHEMA_VERSION, "rules": []},
        )
        rules = payload.get("rules", []) if isinstance(payload, dict) else []
        parsed = [StandingRule.from_dict(item) for item in rules if isinstance(item, dict)]
        return [rule for rule in parsed if rule.rule_id]

    def _write_standing_rules(self, rules: List[StandingRule]) -> str:
        payload = {
            "schema_version": PROFILE_RULES_SCHEMA_VERSION,
            "rules": [rule.to_dict() for rule in rules],
        }
        return self._write_json_entry(
            self.KEY_STANDING_RULES,
            payload,
            entry_id=f"profile_{self.user_id}_standing_rules",
            metadata={"schema_version": PROFILE_RULES_SCHEMA_VERSION},
        )

    def register_standing_rule_from_text(
        self,
        text: str,
        *,
        created_from: Optional[Dict[str, Any]] = None,
    ) -> Optional[StandingRuleRegistration | StandingRuleParseFailure]:
        rule = parse_profile_rule_text(
            user_id=self.user_id,
            text=text,
            created_from=created_from,
        )
        if rule is None:
            if _is_explicit_default_rule_request(text):
                return StandingRuleParseFailure(
                    reason="unsupported_rule_shape",
                    acknowledgement_text=(
                        "这条默认规则我还不能稳定归一化成正式规则，所以不会假装已经记住。\n\n"
                        f"{SUPPORTED_RESTATEMENT}"
                    ),
                )
            return None

        rules = self.list_standing_rules()
        existing = next((item for item in rules if item.rule_id == rule.rule_id), None)
        created = existing is None
        if existing is not None:
            rule.created_at = existing.created_at
            rule.created_from = existing.created_from or rule.created_from
            rules = [item for item in rules if item.rule_id != rule.rule_id]
        rules.append(rule)
        rules.sort(key=_rule_sort_key, reverse=True)
        self._write_standing_rules(rules)

        return StandingRuleRegistration(
            rule=rule,
            created=created,
            confirmation_text=f"已记住这条默认规则：{describe_standing_rule(rule)}",
        )

    def get_active_rule_contexts(self) -> List[Dict[str, Any]]:
        rules = [rule for rule in self.list_standing_rules() if rule.enabled]
        rules.sort(key=_rule_sort_key, reverse=True)
        return [_build_rule_context(rule, matched=False) for rule in rules]

    def match_standing_rules(
        self,
        *,
        target_path: Optional[str] = None,
        request_mode: Optional[str] = None,
        risk_level: Optional[str] = None,
    ) -> List[StandingRule]:
        normalized_target = _normalize_path(target_path)
        normalized_mode = (request_mode or "").strip().lower() or None
        normalized_risk = normalize_risk_level(risk_level, default="low")
        matched: List[StandingRule] = []

        for rule in self.list_standing_rules():
            if not rule.enabled:
                continue
            predicate = rule.predicate or {}
            kind = predicate.get("kind")
            if kind == "target_path_exact":
                if normalized_target and normalized_target == _normalize_path(predicate.get("target_path")):
                    matched.append(rule)
            elif kind == "target_path_prefix":
                if _path_matches_prefix(normalized_target, predicate.get("path_prefix")):
                    matched.append(rule)
            elif kind == "risk_class":
                level = normalize_risk_level(predicate.get("risk_class"), default="low")
                comparison = predicate.get("comparison", "at_least")
                current_rank = RISK_LEVEL_ORDER.get(normalized_risk, 0)
                required_rank = RISK_LEVEL_ORDER.get(level, 0)
                if comparison == "at_least" and current_rank >= required_rank:
                    matched.append(rule)
                elif comparison == "equals" and current_rank == required_rank:
                    matched.append(rule)
            elif kind == "request_mode":
                if normalized_mode and normalized_mode == str(predicate.get("request_mode") or "").strip().lower():
                    matched.append(rule)

        matched.sort(key=_rule_sort_key, reverse=True)
        return matched

    def get_summary(self) -> str:
        lines = [f"User ID: {self.user_id}"]

        prefs = self.get_all_preferences()
        if prefs:
            lines.append(f"Preferences: {json.dumps(prefs, ensure_ascii=False)[:200]}")

        rules = self.get_rules()
        if rules:
            lines.append(f"Rules: {', '.join(rules[:5])}")

        standing_rules = self.get_active_rule_contexts()
        if standing_rules:
            summaries = [item.get("summary") for item in standing_rules[:5] if item.get("summary")]
            if summaries:
                lines.append(f"Standing Rules: {'; '.join(summaries)}")

        style = self.get_communication_style()
        if style:
            lines.append(f"Style: {style}")

        return "\n".join(lines)
