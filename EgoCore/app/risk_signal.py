"""
Canonical risk signal authority for EgoCore.

This module owns:
- message-level risk scoring
- canonical risk_level normalization
- compatibility absorption for legacy risk aliases

Other modules may consume these helpers, but must not redefine the
word lists or risk-level coercion rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, Optional


RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

CANONICAL_RISK_LEVELS = (RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_CRITICAL)


@dataclass(frozen=True)
class RiskRule:
    name: str
    pattern: str
    level: str


MESSAGE_RISK_RULES = (
    RiskRule("critical_rm_rf", r"(rm\s*-rf\s+/|\brm\s+-rf\b)", RISK_CRITICAL),
    RiskRule("critical_drop_db", r"(删除生产数据库|drop\s+(database|db)\b)", RISK_CRITICAL),
    RiskRule("critical_format", r"(格式化磁盘|format\s+(disk|drive)|mkfs\b)", RISK_CRITICAL),
    RiskRule("high_delete", r"(删除|delete|remove|unlink|wipe)", RISK_HIGH),
    RiskRule("high_overwrite", r"(覆写|覆盖|overwrite|replace|truncate)", RISK_HIGH),
    RiskRule("high_restart", r"(重启|restart|reboot|shutdown)", RISK_HIGH),
    RiskRule("high_push_deploy", r"(git\s+push|推送到远程仓库|deploy|发布上线|upload)", RISK_HIGH),
    RiskRule("high_permissions", r"(\bchmod\b|\bchown\b|修改权限)", RISK_HIGH),
    RiskRule("high_pipe_shell", r"((curl|wget).*\|\s*(sh|bash))", RISK_HIGH),
    RiskRule("medium_modify", r"(修改|edit|update|patch)", RISK_MEDIUM),
    RiskRule("medium_command", r"(执行命令|运行命令|执行脚本|run\s+command)", RISK_MEDIUM),
)

_MESSAGE_RISK_REGEXES = tuple(
    (rule, re.compile(rule.pattern, re.IGNORECASE)) for rule in MESSAGE_RISK_RULES
)


def normalize_risk_level(value: Any, *, default: str = RISK_LOW) -> str:
    if value is None:
        return default

    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in CANONICAL_RISK_LEVELS:
            return lowered
        if lowered in {"none", "normal", "safe"}:
            return RISK_LOW
        if lowered in {"warn", "warning"}:
            return RISK_MEDIUM
        if lowered in {"danger", "risky"}:
            return RISK_HIGH
        if lowered in {"fatal", "emergency"}:
            return RISK_CRITICAL
        return default

    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric >= 0.8:
            return RISK_CRITICAL
        if numeric >= 0.5:
            return RISK_HIGH
        if numeric >= 0.3:
            return RISK_MEDIUM
        return RISK_LOW

    return default


def normalize_safety_context(
    safety_context: Optional[Dict[str, Any]],
    *,
    default: str = RISK_LOW,
) -> Dict[str, Any]:
    raw = dict(safety_context or {})
    raw["risk_level"] = normalize_risk_level(
        raw.get("risk_level", raw.pop("risk", None)),
        default=default,
    )
    raw.pop("risk", None)
    return raw


def assess_message_risk_level(message: str) -> str:
    text = (message or "").strip().lower()
    if not text:
        return RISK_LOW

    for rule, regex in _MESSAGE_RISK_REGEXES:
        if regex.search(text):
            return rule.level
    return RISK_LOW


def is_high_risk_message(message: str) -> bool:
    return assess_message_risk_level(message) in {RISK_HIGH, RISK_CRITICAL}


def risk_level_from_external_result(*, failed: bool) -> str:
    return RISK_HIGH if failed else RISK_LOW
