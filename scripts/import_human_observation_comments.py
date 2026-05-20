#!/usr/bin/env python3
"""Convert human trial comments into structured observation packets.

The output is advisory evidence for repair planning. It is intentionally not a
closeout oracle: human comments can describe a pass/fail, but this script does
not treat them as automatic proof that an issue can be closed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO


DEFAULT_REPO = "pen364692088/EGO"
SCHEMA_VERSION = "ego_operator.human_observation_packet.v1"

FIELD_ALIASES = {
    "prompt": {
        "prompt",
        "user prompt",
        "user input",
        "input",
        "用户输入",
        "输入",
        "提示",
        "提示词",
        "问题",
    },
    "expected": {"expected", "expectation", "expected behavior", "期望", "预期", "期待", "应该"},
    "observed": {"observed", "actual", "actual behavior", "result", "观察", "实际", "结果", "现象"},
    "tool_use": {"tool use", "tool calls", "tool", "工具", "工具调用", "工具使用"},
    "memory_hit": {"memory hit", "memory", "记忆命中", "记忆", "是否误用记忆"},
    "correction_needed": {
        "needs correction",
        "correction",
        "是否需要纠正",
        "需要纠正",
        "用户纠正",
    },
    "score": {"score", "rating", "体验评分", "评分", "分数"},
    "provider": {"provider", "model", "模型", "供应商", "llm"},
    "failure_class": {"failure class", "failure", "失败类型", "问题类型", "失败分类"},
    "trace_path": {"trace", "trace path", "report", "report path", "日志", "报告", "trace路径"},
    "related_issue": {"issue", "related issue", "candidate issue", "关联issue", "关联 issue", "任务"},
}

FIELD_LINE_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?([^:：\n]{1,64})(?:\*\*)?\s*[:：]\s*(.*)$")
ISSUE_RE = re.compile(r"#\d+")


class ImportErrorWithCode(Exception):
    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True)
class CommentSource:
    issue: str | None = None
    comment_index: int | str | None = None
    comment_url: str | None = None
    author: str | None = None
    created_at: str | None = None
    title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "issue": self.issue,
                "comment_index": self.comment_index,
                "comment_url": self.comment_url,
                "author": self.author,
                "created_at": self.created_at,
                "title": self.title,
            }.items()
            if value not in {None, ""}
        }


def _normalize_label(label: str) -> str:
    value = (label or "").strip().strip("*").strip()
    value = re.sub(r"\s+", " ", value)
    return value.casefold()


def _field_for_label(label: str) -> str | None:
    normalized = _normalize_label(label)
    for field, aliases in FIELD_ALIASES.items():
        if normalized in {_normalize_label(alias) for alias in aliases}:
            return field
    return None


def parse_fields(text: str) -> dict[str, str]:
    values: dict[str, list[str]] = {}
    current_field: str | None = None
    for line in (text or "").splitlines():
        match = FIELD_LINE_RE.match(line)
        if match:
            field = _field_for_label(match.group(1))
            if field:
                current_field = field
                value = match.group(2).strip()
                if value:
                    values.setdefault(field, []).append(value)
                continue

        if current_field and (line.startswith((" ", "\t")) or line.strip().startswith(("-", "*"))):
            continuation = line.strip()
            if continuation:
                values.setdefault(current_field, []).append(continuation)
        elif not line.strip():
            current_field = None

    return {field: "\n".join(parts).strip() for field, parts in values.items() if any(parts)}


def infer_failure_class(text: str) -> str:
    lowered = (text or "").casefold()
    if "429" in lowered or "too many requests" in lowered or "限流" in text:
        return "provider_rate_limit"
    if "fake approval" in lowered or "伪造 approval" in text or "没有对应的真实 proposal" in text:
        return "approval_hallucination"
    if "timeout" in lowered or "超时" in text:
        return "command_timeout"
    if "截断" in text or "truncated" in lowered:
        return "output_truncation"
    if "workspace 外" in text or "路径" in text and ("误判" in text or "写错" in text or "fallback" in lowered):
        return "path_intent_mismatch"
    if "记住" in text and ("误报" in text or "没写入" in text or "blocked" in lowered):
        return "memory_write_misreport"
    if "web_fetch" in lowered or "联网" in text:
        return "web_fetch_recovery"
    return "unknown"


def _parse_score(value: str) -> dict[str, Any] | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", value or "")
    if not match:
        return None
    return {"value": float(match.group(1)), "scale": float(match.group(2)), "raw": value}


def _raw_excerpt(text: str, limit: int = 1200) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    head = value[: limit // 2]
    tail = value[-limit // 2 :]
    return f"{head}\n...[omitted {len(value) - limit} chars]...\n{tail}"


def _related_issues(fields: dict[str, str], text: str) -> list[str]:
    issue_values = []
    if fields.get("related_issue"):
        issue_values.extend(ISSUE_RE.findall(fields["related_issue"]))
    issue_values.extend(ISSUE_RE.findall(text or ""))
    seen: set[str] = set()
    result: list[str] = []
    for issue in issue_values:
        if issue not in seen:
            seen.add(issue)
            result.append(issue)
    return result


def build_packet(text: str, *, source: CommentSource | None = None, include_raw: bool = False) -> dict[str, Any]:
    fields = parse_fields(text)
    failure_class = fields.get("failure_class") or infer_failure_class(text)
    parse_status = "structured" if fields.get("prompt") and fields.get("observed") else "partial"
    if not fields and failure_class == "unknown":
        parse_status = "unstructured"

    packet: dict[str, Any] = {
        "status": "ok",
        "schema_version": SCHEMA_VERSION,
        "parse_status": parse_status,
        "source": (source or CommentSource()).to_dict(),
        "observation_class": "human_comment_observation",
        "closeout_allowed": False,
        "requires_review": True,
        "fields": fields,
        "failure_class": failure_class,
        "related_issues": _related_issues(fields, text),
        "raw_excerpt": _raw_excerpt(text),
        "suggested_next_step": suggested_next_step(failure_class, parse_status),
        "claim_ceiling": (
            "human observation packet only; not deterministic proof, real-provider pass, "
            "runtime efficacy, stable user benefit, live autonomy, or consciousness"
        ),
        "non_authority_note": (
            "GitHub comments are operator observations. Use them to plan a minimal regression or "
            "repair issue; do not close tasks from this packet alone."
        ),
    }
    if fields.get("score"):
        packet["score"] = _parse_score(fields["score"])
    if include_raw:
        packet["raw_text"] = text
    return packet


def suggested_next_step(failure_class: str, parse_status: str) -> str:
    if parse_status == "unstructured":
        return "ask for a clearer prompt/expected/observed packet or inspect the linked issue comment manually"
    mapping = {
        "approval_hallucination": "add or reuse a deterministic fake-approval repair regression",
        "command_timeout": "split long-running command timeout/retry policy if timeout is still user-visible",
        "output_truncation": "add or reuse a compact digest display regression",
        "path_intent_mismatch": "add or reuse a path-intent fidelity regression for the exact path",
        "provider_rate_limit": "add or reuse provider error/fallback diagnostics regression",
        "memory_write_misreport": "add or reuse memory-write gate and misreport regression",
        "web_fetch_recovery": "add or reuse web_fetch approval/safe-auto recovery regression",
    }
    return mapping.get(failure_class, "create a minimal deterministic regression before runtime changes")


def _gh_json(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise ImportErrorWithCode(
            "gh_command_failed",
            completed.stderr.strip() or completed.stdout.strip() or f"gh exited {completed.returncode}",
            gh_args=args,
            returncode=completed.returncode,
        )
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ImportErrorWithCode("invalid_gh_json", "gh returned invalid JSON", raw=completed.stdout) from exc
    if not isinstance(payload, dict):
        raise ImportErrorWithCode("invalid_gh_json", "gh returned non-object JSON", raw=completed.stdout)
    return payload


def fetch_issue_comments(issue: str, *, repo: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _gh_json(
        [
            "issue",
            "view",
            issue,
            "--repo",
            repo,
            "--json",
            "number,title,url,comments",
        ]
    )
    comments = payload.get("comments")
    if not isinstance(comments, list):
        raise ImportErrorWithCode("missing_comments", "gh issue view response has no comments array")
    return payload, comments


def selected_comment_indexes(count: int, selector: str) -> list[int]:
    if count <= 0:
        return []
    if selector == "all":
        return list(range(count))
    if selector == "latest":
        return [count - 1]
    try:
        index = int(selector)
    except ValueError as exc:
        raise ImportErrorWithCode(
            "invalid_comment_index",
            "comment index must be latest, all, or a zero-based integer",
            value=selector,
        ) from exc
    if index < 0 or index >= count:
        raise ImportErrorWithCode("comment_index_out_of_range", "comment index is out of range", value=index, count=count)
    return [index]


def packets_from_issue_comments(
    issue: str,
    *,
    repo: str,
    comment_index: str,
    include_raw: bool = False,
) -> list[dict[str, Any]]:
    issue_payload, comments = fetch_issue_comments(issue, repo=repo)
    indexes = selected_comment_indexes(len(comments), comment_index)
    packets: list[dict[str, Any]] = []
    for index in indexes:
        comment = comments[index]
        if not isinstance(comment, dict):
            continue
        source = CommentSource(
            issue=f"#{issue_payload.get('number', issue)}",
            title=str(issue_payload.get("title") or ""),
            comment_index=index,
            comment_url=str(comment.get("url") or ""),
            author=str((comment.get("author") or {}).get("login") or comment.get("author") or ""),
            created_at=str(comment.get("createdAt") or ""),
        )
        packets.append(build_packet(str(comment.get("body") or ""), source=source, include_raw=include_raw))
    return packets


def read_text_input(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.comment_file:
        return Path(args.comment_file).read_text(encoding="utf-8")
    return sys.stdin.read()


def write_json(payload: dict[str, Any], stream: TextIO) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    stream.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import human observation comments into structured packets.")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--issue", help="Fetch comments from this GitHub issue when no direct text/file is provided.")
    parser.add_argument("--comment-index", default="latest", help="latest, all, or zero-based comment index.")
    parser.add_argument("--comment-file", help="Read one comment body from a local file.")
    parser.add_argument("--text", help="Read one comment body from an argument.")
    parser.add_argument("--include-raw", action="store_true", help="Include full raw comment text in the packet.")
    return parser


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = stdout or sys.stdout
    try:
        if args.issue and not args.text and not args.comment_file:
            packets = packets_from_issue_comments(
                args.issue,
                repo=args.repo,
                comment_index=args.comment_index,
                include_raw=args.include_raw,
            )
        else:
            packets = [build_packet(read_text_input(args), include_raw=args.include_raw)]
        payload = {
            "status": "ok",
            "schema_version": SCHEMA_VERSION,
            "packet_count": len(packets),
            "packets": packets,
        }
        write_json(payload, out)
        return 0
    except ImportErrorWithCode as exc:
        write_json({"status": "error", "error": exc.code, "message": exc.message, **exc.details}, out)
        return 2
    except Exception as exc:
        write_json({"status": "error", "error": type(exc).__name__, "message": str(exc)}, out)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
