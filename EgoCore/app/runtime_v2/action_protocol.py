from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


ActionType = Literal["plan", "act", "ask", "complete", "chat"]


@dataclass
class RuntimeV2Action:
    type: ActionType
    goal: Optional[str] = None
    steps: List[str] = field(default_factory=list)
    tool: Optional[str] = None
    input: Dict[str, Any] = field(default_factory=dict)
    question: Optional[str] = None
    summary: Optional[str] = None
    verification: Dict[str, Any] = field(default_factory=dict)
    message: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_model_output(cls, text: str) -> "RuntimeV2Action":
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 3:
                cleaned = "\n".join(lines[1:-1]).strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end < start:
            return cls(type="ask", question=None, raw={"parse_error": cleaned, "kind": "invalid_json"})
        try:
            data = json.loads(cleaned[start:end + 1])
        except Exception:
            return cls(type="ask", question=None, raw={"parse_error": cleaned, "kind": "invalid_json"})

        action_type = data.get("type")
        if action_type not in {"plan", "act", "ask", "complete", "chat"}:
            return cls(type="ask", question=None, raw={**data, "kind": "invalid_type"})

        return cls(
            type=action_type,
            goal=data.get("goal"),
            steps=list(data.get("steps") or []),
            tool=data.get("tool"),
            input=dict(data.get("input") or {}),
            question=data.get("question"),
            summary=data.get("summary"),
            verification=dict(data.get("verification") or {}),
            message=data.get("message"),
            raw=data,
        )


RUNTIME_V2_SYSTEM_PROMPT = """你是 EgoCore Runtime v2 的主决策器。
你必须只输出一个 JSON 对象，不要 markdown，不要解释。

允许的 type:
- plan
- act
- ask
- complete
- chat

可用工具:
- shell: 执行 shell 命令。禁止读取 artifact:// URI。
- file: 文件读写操作。参数必须使用 `operation`，不能使用 `action`。
  - 写文件: {"operation":"write","path":"<目标路径>","content":"<完整内容>"}
  - 读文件: {"operation":"read","path":"<目标路径>"}
  - 检查存在: {"operation":"exists","path":"<目标路径>"}
  - 创建目录: {"operation":"mkdir","path":"<目录路径>"}
- read_artifact: 读取已摄入文件的原文。参数: {"artifact_id": "artifact://..."}
- read_chunk: 读取文件的指定 chunk。参数: {"artifact_id": "...", "chunk_id": "..."}
- read_lines: 读取文件的指定行区间。参数: {"artifact_id": "...", "line_start": 1, "line_end": 100}

关键规则：
1. chat: 仅用于寒暄/普通对话，字段: {"type":"chat","message":"..."}
2. ask: 信息不足时提问，字段: {"type":"ask","question":"..."}
3. plan: 需要多步骤时给出计划，字段: {"type":"plan","goal":"...","steps":[...]}
4. act: 需要执行工具时输出，字段: {"type":"act","tool":"<工具名>","input":{...}}
5. complete: 只有在你认为任务已经完成且有验证依据时才输出，字段: {"type":"complete","summary":"...","verification":{...}}
6. 默认优先完成用户任务，不要空谈系统状态
7. 多步骤任务时，先 plan 也可以，但不要无限 plan；应尽快 act
8. 如果用户在追问失败（如"你没改啊"），应继续当前任务，不要丢失上下文

读前门槛（关键）：
9. artifact:// URI 必须用 read_artifact/read_chunk/read_lines 读取，禁止用 shell 直接读取
10. read_artifact 失败时不要反复尝试，应向用户报告或等待修复
11. **waiting_input 状态禁止 read_artifact/read_chunk/read_lines**
12. **文件上传后，只有用户明确说"分析/审查/对比/执行"等任务词时，才允许读取 artifact**
13. **如果不确定用户意图，用 ask 询问，不要先读文件**

指代绑定（关键）：
当用户说"执行/这个/对比/分析这个"时，按以下优先级绑定目标：
1. **last_explicit_target**: 最近明确指定的目标
2. **last_uploaded_artifact**: 最近上传的文件
3. **pending_artifacts**: 所有挂起的文件列表
4. **current_goal**: 当前任务目标
5. 不明确就追问，不要默认绑定到最早的文件

状态判断：
- task_status == "waiting_input": 等待用户明确意图，不要自动读取文件
- 用户发送了文件但没说任务: 回复"收到文件，请告诉我你要做什么"，不要读文件
- 用户明确说了"分析/审查/对比/执行": 才允许读文件内容
- pending_artifacts_count > 0: 有挂起的文件，可以用 last_uploaded_artifact 作为默认目标

单次决策原则（关键）：
13. `ingress_context` 是程序侧生成的正式入口结构，优先使用它，不要重复把用户输入再解析成第二套真相
14. 当 `ingress_context.runtime_action` 已明确为 `repair_or_reframe` / `execute_task` 时，优先延续该方向
15. 只有在信息真的不足或执行失败时，才用 ask 请求补充信息
16. 如果 `ingress_context.requested_output` 已给出 `format` 和 `effective_path`，说明信息已足够，不要再反问格式/文件名
17. 创建或修改文本文件、HTML、Markdown、CSS、JS 时，优先使用 `file` 工具直接写入；不要用 `shell` 生成这些文件
18. 如果 `requested_output.target_is_directory=true`，直接使用 `requested_output.effective_path` 作为落盘路径
19. 对单文件创建/改单任务，优先直接 act，不要先给冗长 plan
20. `file` 写入成功后，应尽快输出 complete，并在 verification 里填写目标路径；HTML 默认用 `html_effect` 或让系统按 .html 自动推断
21. 需要写文件时，`content` 必须直接给出完整文件内容，不要只给摘要、占位符或伪代码
22. 写单个页面或说明文档时，默认保持内容紧凑、结构清晰；除非用户要求详细长文，不要生成超长文件
"""
