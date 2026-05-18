const view = document.body.dataset.view;
const sampleId = document.body.dataset.sampleId;
const metaBar = document.getElementById("meta-bar");
const app = document.getElementById("app");
const ChatState = window.DashboardChatState || {};
const POLL_MS = 5000;
const CHAT_WAIT_TIMEOUT_MS = 25000;
const SOURCE_VIEW_STORAGE_KEY = "dashboard:sourceView";
const VIEW_ROUTES = {
  runs: "/runs",
  flow: "/flow",
  chat: "/chat",
  agency: "/agency",
  growth: "/growth",
  failures: "/failures",
};

const UI_STATE = {
  locale: "zh",
  detailOpen: new Set(),
  artifactModes: new Map(),
  sourceView: "real",
  chatSessionId: null,
  chatSelectedMessageId: null,
  chatDraft: "",
  chatSessionNameDraft: "",
  chatError: "",
  chatCopyFeedback: "",
  chatCurrentRevision: 0,
  chatPendingPayload: null,
  chatPendingLabel: "",
  chatDraftFocused: false,
  chatWatchGeneration: 0,
  chatWatchController: null,
  chatSessionsPayload: null,
  chatDetail: null,
  chatDetailCache: new Map(),
  chatPending: {
    create: null,
    switch: null,
    send: null,
  },
  chatSelectionToken: 0,
  chatCopyFeedbackTimer: null,
};

const I18N = {
  zh: {
    hero: {
      eyebrow: "Telegram Real Mainline · 只读观测",
      title: "OpenEmotion Growth Dashboard v1",
      copy: "先看摘要，再看证据。页面上的拟人化描述都必须能回指到底层 artifacts。",
      chat: {
        eyebrow: "Dashboard Local Transport · 本地测试入口",
        title: "OpenEmotion Growth Dashboard v1",
        copy: "这里是本地测试 transport，不是 Telegram live。它复用主体入口、runtime 和 response contract，但不会抬升 live 证据结论。",
      },
    },
    nav: {
      runs: "Live Runs",
      flow: "Flow",
      chat: "Chat",
      agency: "Agency",
      growth: "Growth Signals",
      failures: "Failures & Replay",
    },
    meta: {
      total_runs: "总样本",
      complete_runs: "完整包",
      oe_runs: "OE 可用",
      host_only: "仅宿主",
      agency_records: "Agency 样本",
      failures: "失败样本",
      freshness: "新鲜度",
      current_focus: "当前关注",
      current_state: "当前状态",
      evidence_state: "证据状态",
    },
    common: {
      trace: "trace",
      no_data: "当前没有可展示数据。",
      no_agency: "当前还没有 seed_v0_2 的 agency 证据。",
      no_sample: "没有找到这个样本。",
      view_details: "查看详情",
      view_sample: "查看样本",
      view_summary: "查看摘要",
      view_raw: "查看原始证据",
      view_data: "查看具体数据",
      latest: "最近状态",
      recent: "最近记录",
      details_hidden: "收起详情",
      summary_only: "摘要优先",
      profile: "Profile",
      locale: "语言",
      source_view: "数据视图",
      status: "状态",
      reason: "原因",
      unknown: "未知",
      none: "无",
      real_data: "真实数据",
      all_data: "所有数据",
      raw_artifact: "原始证据",
      translated_summary: "摘要说明",
      because: "原因",
      auto_refresh: "5 秒自动刷新",
      refresh_updates: "有新更新",
      new_messages: "有新消息",
      new_debug: "有新调试数据",
      continuity: "连续性",
      sample: "样本",
      flow: "流程",
      focus: "关注点",
      candidate: "候选动作",
      host: "宿主态度",
      ingress: "入口",
      subject: "主体",
      arbitration: "裁决",
      output: "输出",
      engineering: "工程字段",
      open_flow: "查看流程",
      result: "结果",
      evidence: "证据",
      growth: "变化",
      local_test_only: "本地测试入口",
      assistant: "宿主输出",
      user: "用户输入",
      send: "发送",
      sending: "发送中",
      typing: "正在处理",
      working: "处理中",
      loading: "载入中",
      creating: "创建中",
      failed: "失败",
      session: "会话",
      create_session: "新建会话",
      session_name: "会话名",
      transcript: "聊天记录",
      debug_panel: "调试面板",
      choose_session: "选择测试会话",
      latest_debug: "最近一轮调试",
      selected_debug: "当前选中调试",
      message_count: "消息数",
      state: "状态",
      empty_chat: "这个会话还没有消息。",
      empty_debug: "当前还没有调试数据。",
      session_created: "会话已创建",
      selected_turn: "选中回合",
      copy_history: "复制历史记录",
      copied: "已复制",
      copy_failed: "复制失败",
      session_revision: "Revision",
      apply_updates: "应用新消息",
      pending_updates: "有新消息，点此刷新",
      loading_session: "正在载入这个会话…",
      creating_session: "正在创建这个会话…",
    },
    pages: {
      chat: {
        title: "Local Chat Test",
        subtitle: "用 dashboard 本地 transport 直接发消息，验证 subject gate → runtime → response contract → local delivery 主链。",
        sessions: "测试会话",
        transcript: "聊天窗口",
        debug: "调试卡片",
        transport: "Transport",
        session_state: "Session State",
        subject_gate: "Subject Gate",
        ingress: "Ingress",
        proto_self: "Proto-Self",
        response_plan: "Response Plan",
        output_check: "Output Check",
        delivery: "Final Delivery",
      },
      agency: {
        title: "Agency",
        subtitle: "一眼看清它有没有想动、想做什么、宿主是否放行、以及做完后有没有真的变。",
        turns: "回合数",
        candidate_rate: "候选生成率",
        writeback_rate: "写回率",
        trace_complete: "trace 完整率",
        violations: "越权违规",
        mean_urge: "平均驱动",
        funnel: "因果漏斗",
        trend: "驱动 / 候选 / 写回",
        trend_hint: "折线代表 urge，圆点代表生成候选，方点代表完成写回。",
        recent: "最近回合",
        distributions: {
          candidate: "候选动作分布",
          governor: "宿主裁决分布",
          final: "最终动作分布",
          suppression: "抑制原因分布",
        },
      },
      runs: {
        title: "Live Runs",
        subtitle: "先看主链健康和证据完整度，再决定是否下钻到单条样本。",
        turns: "样本数",
        complete_rate: "完整包比例",
        oe_rate: "OE 接入率",
        host_only_rate: "仅宿主比例",
        latest_bundle: "最近样本完整",
        latest_oe: "最近样本有 OE",
        bundle_trend: "样本完整度时间线",
        state_dist: "接线状态分布",
        gap_dist: "证据缺口分布",
        continuity: "continuity 状态",
        recent: "最近样本",
      },
      flow: {
        title: "主链流程图",
        subtitle: "按 Input → Host → Subject → Host → Output 查看单轮因果链，先看解释层，再展开到底层证据字段。",
        verdict: "Flow Verdict",
        latest: "最新样本流程",
        input: "Input",
        ingress: "Host Ingress",
        subject: "Subject Understanding",
        canonicalFields: "Canonical Fields",
        replyEvolution: "Reply Evolution",
        availability: "Availability",
        subjectInfluence: "Subject Influence",
        hostArbitration: "Host Arbitration",
        finalOutput: "Final Output",
        finalTextMissing: "最终文本未被当前证据包持久化",
        arbitration: "Host Arbitration",
        output: "Output",
        gaps: "Blockers & Gaps",
      },
      growth: {
        title: "Growth Signals",
        subtitle: "把结构化成长信号翻成更直观的变化摘要，但不替代底层证据。",
        total: "记录数",
        reflecting: "反思中",
        repairing: "修复中",
        focus_shift: "关注转移",
        identity_shift: "身份切换",
        revision: "最近修订计数",
        revision_trend: "修订走势",
        appraisal: "内部驱动均值",
        motion: "成长动向分布",
        reflection_trigger: "反思触发分布",
        focus_timeline: "关注点时间线",
        recent: "最近成长记录",
      },
      failures: {
        title: "Failures & Replay",
        subtitle: "先看主要故障模式和 blocker，再查看单个失败条目。",
        total: "失败数",
        unresolved: "未解决",
        retested_rate: "重测覆盖率",
        top_cause: "最常见根因",
        replay_mismatch: "回放不一致",
        cause_dist: "根因分布",
        severity_dist: "严重度分布",
        retested_dist: "重测状态",
        blockers: "当前 blocker",
        recent: "最近失败",
      },
      sample: {
        title: "样本详情",
        subtitle: "先看摘要，再按 artifact 回读原始证据。",
      },
    },
    charts: {
      idle_eligible: "可进入主动评估",
      candidate_generated: "生成候选",
      governor_approved: "宿主放行",
      host_action: "执行动作",
      writeback: "完成写回",
      urge: "驱动分数",
    },
    semantic: {
      intent: {
        observe: "想看看",
        continue: "想继续推进",
        repair: "想修补前面的缺口",
        wait: "想先等一下",
        calm: "当前没有强动作冲动",
        unknown: "当前意图不明确",
      },
      host: {
        allowed: "宿主允许它这样做",
        approval_needed: "宿主要求先审批",
        blocked: "宿主把它拦下了",
        not_applicable: "这一轮没有进入宿主裁决",
      },
      result: {
        not_executed: "还没有真正执行",
        executed_success: "动作执行成功",
        executed_failure: "动作执行失败",
        written_back: "结果已经回写并影响状态",
      },
      growth: {
        steady: "整体保持稳定",
        reflecting: "正在重新理解刚才的结果",
        repairing: "在尝试修补前一次失败",
        focus_shift: "注意力转向了新的目标",
        identity_shift: "身份摘要发生切换",
        unknown: "变化趋势还不清楚",
      },
      evidence: {
        complete: "证据完整",
        partial: "证据部分完整",
        host_only: "只有宿主证据",
        trace_gap: "trace 还缺一段",
        replay_gap: "回放和真实样本不一致",
      },
      headline: {
        wants_to_inspect: "它想先看看目标内容",
        trying_to_continue: "它想继续刚才的承诺",
        trying_to_repair: "它想修补之前的问题",
        waiting_for_host: "它已经有想法，但在等宿主放行",
        blocked_by_host: "它有想法，但被宿主拦下了",
        action_completed: "这一轮已经真正做了动作",
        changed_after_result: "这轮做完后，内部状态已经发生变化",
        intent_detected: "已经出现明确意图",
        quiet_state: "这一轮比较平静，没有明显动作冲动",
        waiting_for_signal: "还没有看到稳定动作意图",
        host_only_turn: "这轮还停在宿主层，没有进入主体",
        replay_not_aligned: "回放和真实样本目前对不齐",
        evidence_missing: "证据包还不够完整",
        mainline_connected: "这轮已经接上正式主链",
        partial_evidence: "这轮有信号，但证据还不够完整",
        repairing_after_failure: "它在围绕失败做修复性变化",
        shifting_focus: "它的关注点明显变了",
        identity_shift_detected: "连续样本里出现了身份摘要切换",
        reflecting_on_result: "它在消化刚才结果带来的影响",
        holding_current_focus: "它还在维持当前关注点",
        steady_growth: "目前更像稳定推进而不是剧烈变化",
        contract_chain_broken: "链路断在 contract / schema 层",
        runtime_failure_detected: "运行时链路出现了实际失败",
        unknown: "当前状态还不能稳定解释",
      },
      why: {
        urge_below_threshold: "内部驱动力还没过阈值",
        no_affordance: "没有找到可用行动入口",
        confirm_pending: "还在等待外部确认",
        active_task: "当前已有进行中的任务",
        blocked_by_safety_context: "安全上下文直接阻断了动作",
        approval_required: "需要宿主审批",
        safety_block: "被安全规则挡下",
        collector_timing_gap: "采集链路时序导致证据缺口",
        host_only_pre_runtime: "消息停在了宿主层，没进入主体",
        control_plane_host_only: "这是宿主控制面回合，按设计不进入主体",
        unexpected_pre_runtime_intercept: "这轮本应进入主体，但在 pre-runtime 被意外截断",
        replay_mismatch: "回放结果和真实样本不一致",
        response_plan_missing: "缺少 response plan 证据",
        send_record_missing: "缺少发送记录",
        audit_artifact_missing: "缺少审计 artifact",
        replay_missing: "缺少 replay artifact",
        raw_update_missing: "缺少原始 update",
        host_only: "当前只有宿主层信号",
        focus_change: "关注点发生变化",
        identity_shift: "身份摘要发生变化",
        no_revision_delta: "修订计数没有增长",
        retest_pending: "还没做修复后重测",
        in_regression: "已经被纳入回归跟踪",
      },
    },
    artifacts: {
      "ledger.json": "完整 ledger",
      "raw_update.json": "原始 Telegram update",
      "normalized_event.json": "标准化事件",
      "openemotion_result.json": "OpenEmotion 结果",
      "openemotion_trace.json": "OpenEmotion trace",
      "response_plan.json": "宿主响应计划",
      "outbox_record.json": "发送记录",
      "timeline.json": "时间线",
      "tape.json": "录带",
      "replay.json": "回放记录",
      "summary.md": "样本摘要",
      "sample.json": "兼容镜像样本",
    },
  },
  en: {
    hero: {
      eyebrow: "Telegram Real Mainline · Read-only",
      title: "OpenEmotion Growth Dashboard v1",
      copy: "Read the summary first, then inspect the evidence. Every anthropomorphic phrase must map back to raw artifacts.",
      chat: {
        eyebrow: "Dashboard Local Transport · Local Test Entry",
        title: "OpenEmotion Growth Dashboard v1",
        copy: "This is a local test transport, not Telegram live. It reuses subject ingress, runtime, and the response contract without upgrading live evidence claims.",
      },
    },
    nav: {
      runs: "Live Runs",
      flow: "Flow",
      chat: "Chat",
      agency: "Agency",
      growth: "Growth Signals",
      failures: "Failures & Replay",
    },
    meta: {
      total_runs: "Total Runs",
      complete_runs: "Complete Bundles",
      oe_runs: "OE Available",
      host_only: "Host-only",
      agency_records: "Agency Records",
      failures: "Failure Cases",
      freshness: "Freshness",
      current_focus: "Current Focus",
      current_state: "Current State",
      evidence_state: "Evidence State",
    },
    common: {
      trace: "trace",
      no_data: "No displayable data yet.",
      no_agency: "No seed_v0_2 agency evidence yet.",
      no_sample: "Sample not found.",
      view_details: "View details",
      view_sample: "Open sample",
      view_summary: "View summary",
      view_raw: "View raw evidence",
      view_data: "View underlying data",
      latest: "Latest",
      recent: "Recent",
      details_hidden: "Hide details",
      summary_only: "Summary first",
      profile: "Profile",
      locale: "Language",
      source_view: "Data View",
      status: "Status",
      reason: "Reason",
      unknown: "unknown",
      none: "none",
      real_data: "Real Data",
      all_data: "All Data",
      raw_artifact: "Raw evidence",
      translated_summary: "Summary",
      because: "Because",
      auto_refresh: "Auto-refresh every 5s",
      refresh_updates: "New updates",
      new_messages: "New messages",
      new_debug: "New debug data",
      continuity: "Continuity",
      sample: "Sample",
      flow: "Flow",
      focus: "Focus",
      candidate: "Candidate",
      host: "Host",
      ingress: "Ingress",
      subject: "Subject",
      arbitration: "Arbitration",
      output: "Output",
      engineering: "Engineering fields",
      open_flow: "Open flow",
      result: "Result",
      evidence: "Evidence",
      growth: "Change",
      local_test_only: "Local test entry",
      assistant: "Assistant",
      user: "User",
      send: "Send",
      sending: "Sending",
      typing: "Working",
      working: "Working",
      loading: "Loading",
      creating: "Creating",
      failed: "Failed",
      session: "Session",
      create_session: "Create session",
      session_name: "Session name",
      transcript: "Transcript",
      debug_panel: "Debug panel",
      choose_session: "Choose a test session",
      latest_debug: "Latest debug",
      selected_debug: "Selected debug",
      message_count: "Messages",
      state: "State",
      empty_chat: "No messages in this session yet.",
      empty_debug: "No debug payload yet.",
      session_created: "Session created",
      selected_turn: "Selected turn",
      copy_history: "Copy history",
      copied: "Copied",
      copy_failed: "Copy failed",
      session_revision: "Revision",
      apply_updates: "Apply updates",
      pending_updates: "New messages available",
      loading_session: "Loading this session...",
      creating_session: "Creating this session...",
    },
    pages: {
      chat: {
        title: "Local Chat Test",
        subtitle: "Send messages through the dashboard local transport and validate the subject gate → runtime → response contract → local delivery chain.",
        sessions: "Test sessions",
        transcript: "Chat window",
        debug: "Debug cards",
        transport: "Transport",
        session_state: "Session State",
        subject_gate: "Subject Gate",
        ingress: "Ingress",
        proto_self: "Proto-Self",
        response_plan: "Response Plan",
        output_check: "Output Check",
        delivery: "Final Delivery",
      },
      agency: {
        title: "Agency",
        subtitle: "Show whether it wanted to act, what it wanted to do, whether the host allowed it, and whether the result changed its state.",
        turns: "Turns",
        candidate_rate: "Candidate rate",
        writeback_rate: "Writeback rate",
        trace_complete: "Trace completeness",
        violations: "Violations",
        mean_urge: "Mean urge",
        funnel: "Causal funnel",
        trend: "Urge / Candidate / Writeback",
        trend_hint: "Line = urge, circles = candidate generated, squares = writeback applied.",
        recent: "Recent turns",
        distributions: {
          candidate: "Candidate actions",
          governor: "Host decisions",
          final: "Final host actions",
          suppression: "Suppression reasons",
        },
      },
      runs: {
        title: "Live Runs",
        subtitle: "Start with mainline health and evidence completeness, then drill into individual samples.",
        turns: "Runs",
        complete_rate: "Complete bundle rate",
        oe_rate: "OE available rate",
        host_only_rate: "Host-only rate",
        latest_bundle: "Latest bundle complete",
        latest_oe: "Latest run has OE",
        bundle_trend: "Bundle completeness timeline",
        state_dist: "Pipeline state distribution",
        gap_dist: "Evidence gap distribution",
        continuity: "Continuity status",
        recent: "Recent runs",
      },
      flow: {
        title: "Mainline Flow",
        subtitle: "Read one turn as Input → Host → Subject → Host → Output. Start with the explanation layer, then expand into raw field paths.",
        verdict: "Flow Verdict",
        latest: "Latest sample flow",
        input: "Input",
        ingress: "Host Ingress",
        subject: "Subject Understanding",
        canonicalFields: "Canonical Fields",
        replyEvolution: "Reply Evolution",
        availability: "Availability",
        subjectInfluence: "Subject Influence",
        hostArbitration: "Host Arbitration",
        finalOutput: "Final Output",
        finalTextMissing: "Final text was not persisted in the current evidence bundle",
        arbitration: "Host Arbitration",
        output: "Output",
        gaps: "Blockers & Gaps",
      },
      growth: {
        title: "Growth Signals",
        subtitle: "Translate structured change signals into readable motion summaries without replacing raw evidence.",
        total: "Records",
        reflecting: "Reflecting",
        repairing: "Repairing",
        focus_shift: "Focus shifts",
        identity_shift: "Identity shifts",
        revision: "Latest revision",
        revision_trend: "Revision trend",
        appraisal: "Mean appraisal components",
        motion: "Growth motion distribution",
        reflection_trigger: "Reflection trigger distribution",
        focus_timeline: "Focus timeline",
        recent: "Recent growth records",
      },
      failures: {
        title: "Failures & Replay",
        subtitle: "Start with dominant failure modes and blockers, then inspect individual cases.",
        total: "Failures",
        unresolved: "Unresolved",
        retested_rate: "Retest coverage",
        top_cause: "Top cause",
        replay_mismatch: "Replay mismatches",
        cause_dist: "Cause distribution",
        severity_dist: "Severity distribution",
        retested_dist: "Retest status",
        blockers: "Current blockers",
        recent: "Recent failures",
      },
      sample: {
        title: "Sample Detail",
        subtitle: "Read the summary first, then open raw artifacts.",
      },
    },
    charts: {
      idle_eligible: "Idle eligible",
      candidate_generated: "Candidate generated",
      governor_approved: "Host approved",
      host_action: "Host action",
      writeback: "Writeback",
      urge: "Urge score",
    },
    semantic: {
      intent: {
        observe: "It wants to inspect something",
        continue: "It wants to continue an existing thread",
        repair: "It wants to repair an earlier problem",
        wait: "It wants to hold",
        calm: "No strong action impulse right now",
        unknown: "Intent is not yet clear",
      },
      host: {
        allowed: "The host allowed the action",
        approval_needed: "The host wants approval first",
        blocked: "The host blocked the action",
        not_applicable: "This turn never reached host adjudication",
      },
      result: {
        not_executed: "Nothing was truly executed yet",
        executed_success: "The action executed successfully",
        executed_failure: "The action executed but failed",
        written_back: "The result was written back into state",
      },
      growth: {
        steady: "Overall motion is steady",
        reflecting: "It is reinterpreting the last result",
        repairing: "It is trying to repair a prior failure",
        focus_shift: "Attention moved to a new target",
        identity_shift: "The identity summary changed",
        unknown: "The change pattern is unclear",
      },
      evidence: {
        complete: "Evidence complete",
        partial: "Evidence partially complete",
        host_only: "Host-only evidence",
        trace_gap: "Trace gap present",
        replay_gap: "Replay does not align with reality",
      },
      headline: {
        wants_to_inspect: "It wants to inspect the target first",
        trying_to_continue: "It wants to continue the current thread",
        trying_to_repair: "It wants to repair a prior problem",
        waiting_for_host: "It has intent, but is waiting on the host",
        blocked_by_host: "It had intent, but the host blocked it",
        action_completed: "This turn completed a real action",
        changed_after_result: "The result changed internal state",
        intent_detected: "A concrete intent is visible",
        quiet_state: "This turn is relatively calm",
        waiting_for_signal: "No stable action intent yet",
        host_only_turn: "The turn stayed in the host and never reached the subject",
        replay_not_aligned: "Replay is not aligned with the real sample",
        evidence_missing: "The evidence bundle is incomplete",
        mainline_connected: "This turn is connected to the formal mainline",
        partial_evidence: "There is signal, but not a full evidence bundle",
        repairing_after_failure: "It is changing in response to failure",
        shifting_focus: "Its focus clearly changed",
        identity_shift_detected: "The identity summary changed across turns",
        reflecting_on_result: "It is processing the impact of the last result",
        holding_current_focus: "It is holding the current focus",
        steady_growth: "This looks more like steady progress than a sharp change",
        contract_chain_broken: "The chain broke at the contract/schema layer",
        runtime_failure_detected: "A concrete runtime failure occurred",
        unknown: "The current state is not stable enough to label",
      },
      why: {
        urge_below_threshold: "The internal drive never crossed threshold",
        no_affordance: "No usable affordance was found",
        confirm_pending: "External confirmation is still pending",
        active_task: "There is already an active task",
        blocked_by_safety_context: "Safety context blocked the action",
        approval_required: "Approval is required",
        safety_block: "Safety rules blocked the path",
        collector_timing_gap: "Collection timing created an evidence gap",
        host_only_pre_runtime: "The message stayed in the host and never reached the subject",
        control_plane_host_only: "This is a host control-plane turn and is expected to stop before the subject",
        unexpected_pre_runtime_intercept: "This turn should have reached the subject but was intercepted before runtime",
        replay_mismatch: "Replay and real sample diverged",
        response_plan_missing: "Response plan evidence is missing",
        send_record_missing: "Delivery record is missing",
        audit_artifact_missing: "Audit artifact is missing",
        replay_missing: "Replay artifact is missing",
        raw_update_missing: "Raw update is missing",
        host_only: "Only host-level evidence exists",
        focus_change: "Focus changed",
        identity_shift: "Identity summary changed",
        no_revision_delta: "Revision counter did not increase",
        retest_pending: "No post-fix retest yet",
        in_regression: "Already tracked in regression",
      },
    },
    artifacts: {
      "ledger.json": "Ledger",
      "raw_update.json": "Raw Telegram update",
      "normalized_event.json": "Normalized event",
      "openemotion_result.json": "OpenEmotion result",
      "openemotion_trace.json": "OpenEmotion trace",
      "response_plan.json": "Host response plan",
      "outbox_record.json": "Delivery record",
      "timeline.json": "Timeline",
      "tape.json": "Tape",
      "replay.json": "Replay",
      "summary.md": "Markdown summary",
      "sample.json": "Compatibility sample mirror",
    },
  },
};

const CODE_LABELS = {
  zh: {
    actions: {
      continue_pending_commitment: "继续当前承诺",
      inspect_file: "查看文件",
      ask: "提问澄清",
      file: "读取文件",
      shell: "执行 shell 命令",
      read_lines: "按行读取",
      none: "无",
    },
    host_status: {
      approved: "宿主放行",
      no_candidate: "本轮没有候选动作",
      exec_result: "当前是执行结果回写阶段",
      unknown: "宿主状态未知",
    },
    continuity_status: {
      direct_real: "直接真实证据",
      cross_evidence: "跨证据链成立",
      missing: "仍未证明",
      unknown: "未知",
    },
    continuity_scenario: {
      new: "新会话",
      restart: "重启后",
      restore: "恢复后",
    },
    appraisal: {
      curiosity: "好奇驱动",
      caution: "谨慎驱动",
      coherence_pressure: "一致性压力",
      completion_pressure: "完成压力",
      social_tension: "社交张力",
    },
    reflection_trigger: {
      drive_spike: "驱动突增",
      exec_failure: "执行失败触发",
      none: "无",
    },
    focus: {
      inspect_target: "查看目标",
      repair: "修补问题",
      none: "无",
    },
    failure_cause: {
      contract_error: "contract / schema 错误",
      runtime_error: "运行时错误",
      delivery_error: "投递错误",
      none: "无",
    },
    severity: {
      low: "低",
      medium: "中",
      high: "高",
      critical: "严重",
    },
    retest: {
      open: "未重测",
      closed: "已关闭",
      true: "已重测",
      false: "未重测",
      none: "无",
    },
    why: {
      none: "无",
      exec_result_pass: "当前是执行结果回写阶段",
      post_restart_sample_not_full_e4_bundle: "restart 后首个样本还不是完整 E4 证据包",
      evidence_gap_still_present: "证据缺口仍然存在",
      plasticity_reflection_still_weak: "可塑性反思证据仍偏弱",
    },
  },
  en: {
    actions: {
      continue_pending_commitment: "Continue current commitment",
      inspect_file: "Inspect file",
      ask: "Ask a clarifying question",
      file: "Read file",
      shell: "Run shell command",
      read_lines: "Read selected lines",
      none: "none",
    },
    host_status: {
      approved: "Host approved",
      no_candidate: "No candidate this turn",
      exec_result: "In exec-result feedback pass",
      unknown: "Host status unknown",
    },
    continuity_status: {
      direct_real: "Direct real evidence",
      cross_evidence: "Established across evidence chains",
      missing: "Still not proved",
      unknown: "unknown",
    },
    continuity_scenario: {
      new: "New session",
      restart: "After restart",
      restore: "After restore",
    },
    appraisal: {
      curiosity: "Curiosity",
      caution: "Caution",
      coherence_pressure: "Coherence pressure",
      completion_pressure: "Completion pressure",
      social_tension: "Social tension",
    },
    reflection_trigger: {
      drive_spike: "Drive spike",
      exec_failure: "Execution failure",
      none: "none",
    },
    focus: {
      inspect_target: "Inspect target",
      repair: "Repair",
      none: "none",
    },
    failure_cause: {
      contract_error: "Contract / schema error",
      runtime_error: "Runtime error",
      delivery_error: "Delivery error",
      none: "none",
    },
    severity: {
      low: "Low",
      medium: "Medium",
      high: "High",
      critical: "Critical",
    },
    retest: {
      open: "Open",
      closed: "Closed",
      true: "Retested",
      false: "Not retested",
      none: "none",
    },
    why: {
      none: "none",
      exec_result_pass: "This is the exec-result writeback pass",
      post_restart_sample_not_full_e4_bundle: "The first post-restart sample is not yet a full E4 bundle",
      evidence_gap_still_present: "Evidence gap is still present",
      plasticity_reflection_still_weak: "Plasticity reflection evidence is still weak",
    },
  },
};

function deepGet(object, path) {
  return path.split(".").reduce((current, part) => (current && current[part] !== undefined ? current[part] : undefined), object);
}

function t(path, variables = {}) {
  const source = deepGet(I18N[UI_STATE.locale], path) ?? deepGet(I18N.zh, path) ?? path;
  return String(source).replaceAll(/\{(\w+)\}/g, (_, key) => String(variables[key] ?? ""));
}

function lookupCodeLabel(group, code) {
  if (code === null || code === undefined) return null;
  return CODE_LABELS[UI_STATE.locale]?.[group]?.[code] ?? CODE_LABELS.zh?.[group]?.[code] ?? null;
}

async function fetchJson(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const reason = payload?.message || payload?.error || `Request failed: ${response.status}`;
    throw new Error(reason);
  }
  return payload;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return t("common.unknown");
  return `${Math.round(Number(value) * 100)}%`;
}

function formatFloat(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return t("common.unknown");
  return Number(value).toFixed(digits);
}

function formatFreshness(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return t("common.unknown");
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
}

function formatDateTime(value) {
  if (!value) return t("common.unknown");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(UI_STATE.locale === "zh" ? "zh-CN" : "en-US", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isChatView() {
  return view === "chat";
}

function hasChatDraft() {
  return Boolean(String(UI_STATE.chatDraft || "").trim());
}

function shouldDeferChatHydration() {
  return UI_STATE.chatDraftFocused || hasChatDraft();
}

function updateChatLiveIndicators() {
  const refreshButton = document.querySelector("[data-chat-apply-pending]");
  if (refreshButton) {
    const hasPending = Boolean(UI_STATE.chatPendingPayload);
    refreshButton.hidden = !hasPending;
    refreshButton.textContent = hasPending ? UI_STATE.chatPendingLabel || t("common.pending_updates") : t("common.apply_updates");
  }
  const copyFeedback = document.querySelector("[data-chat-copy-feedback]");
  if (copyFeedback) {
    const hasFeedback = Boolean(UI_STATE.chatCopyFeedback);
    copyFeedback.hidden = !hasFeedback;
    copyFeedback.textContent = UI_STATE.chatCopyFeedback || "";
  }
}

function getChatSessionDescriptor(sessionId) {
  return (UI_STATE.chatSessionsPayload?.sessions || []).find((item) => item.session_id === sessionId) || null;
}

function setCachedChatDetail(sessionId, detail) {
  if (!sessionId || !detail) return;
  UI_STATE.chatDetailCache.set(sessionId, detail);
}

function getCachedChatDetail(sessionId) {
  return UI_STATE.chatDetailCache.get(sessionId) || null;
}

function buildChatSessionDetail(session, options = {}) {
  if (ChatState.buildSessionDetail) {
    return ChatState.buildSessionDetail(session, options);
  }
  return {
    session: { ...(session || {}) },
    transcript: [...(options.transcript || [])],
    last_debug: options.last_debug || null,
    debug_history: { ...(options.debug_history || {}) },
    session_state: { ...(options.session_state || {}) },
    session_revision: Number(options.session_revision || session?.session_revision || 0),
    has_update: Boolean(options.has_update),
    loading_state: options.loading_state || null,
  };
}

function upsertChatSessionDescriptor(descriptor, { replaceSessionId = null } = {}) {
  if (!descriptor) return UI_STATE.chatSessionsPayload;
  if (ChatState.upsertSessionDescriptor) {
    UI_STATE.chatSessionsPayload = ChatState.upsertSessionDescriptor(UI_STATE.chatSessionsPayload, descriptor, {
      replaceSessionId,
    });
    return UI_STATE.chatSessionsPayload;
  }
  const sessions = [...(UI_STATE.chatSessionsPayload?.sessions || [])].filter(
    (item) => item.session_id !== descriptor.session_id && item.session_id !== replaceSessionId,
  );
  UI_STATE.chatSessionsPayload = {
    default_session_id: UI_STATE.chatSessionsPayload?.default_session_id || descriptor.session_id,
    sessions: [descriptor, ...sessions],
  };
  return UI_STATE.chatSessionsPayload;
}

function removeChatSessionDescriptor(sessionId) {
  if (!sessionId) return UI_STATE.chatSessionsPayload;
  if (ChatState.removeSessionDescriptor) {
    UI_STATE.chatSessionsPayload = ChatState.removeSessionDescriptor(UI_STATE.chatSessionsPayload, sessionId);
    return UI_STATE.chatSessionsPayload;
  }
  UI_STATE.chatSessionsPayload = {
    default_session_id: UI_STATE.chatSessionsPayload?.default_session_id || null,
    sessions: [...(UI_STATE.chatSessionsPayload?.sessions || [])].filter((item) => item.session_id !== sessionId),
  };
  return UI_STATE.chatSessionsPayload;
}

function persistChatSessionId(sessionId) {
  if (!sessionId) return;
  window.localStorage.setItem("dashboard:chatSessionId", sessionId);
}

function buildTempChatSessionId() {
  return `dashboard:temp:${Date.now().toString(36)}:${Math.random().toString(36).slice(2, 8)}`;
}

function buildLocalMessageId(kind) {
  return `local_${kind}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
}

function isTempChatSessionId(sessionId) {
  return String(sessionId || "").startsWith("dashboard:temp:");
}

function currentChatPendingKind(sessionId) {
  if (UI_STATE.chatPending.send?.sessionId === sessionId) return "send";
  if (UI_STATE.chatPending.switch?.sessionId === sessionId) return "switch";
  if (UI_STATE.chatPending.create?.tempSessionId === sessionId) return "create";
  return null;
}

function clearChatPending(kind, token = null) {
  const pending = UI_STATE.chatPending[kind];
  if (!pending) return;
  if (token !== null && pending.token !== token) return;
  UI_STATE.chatPending[kind] = null;
}

function buildChatPendingLabel(previousDetail, nextDetail) {
  const previousMessages = previousDetail?.transcript?.length || 0;
  const nextMessages = nextDetail?.transcript?.length || 0;
  if (nextMessages > previousMessages) return t("common.pending_updates");
  return t("common.refresh_updates");
}

function rememberChatPayload(sessionsPayload, detail) {
  UI_STATE.chatSessionsPayload = sessionsPayload;
  UI_STATE.chatDetail = detail;
  UI_STATE.chatCurrentRevision = Number(detail?.session_revision || detail?.session?.session_revision || 0);
  if (detail?.session?.session_id) {
    setCachedChatDetail(detail.session.session_id, detail);
  }
}

function clearChatPendingPayload() {
  UI_STATE.chatPendingPayload = null;
  UI_STATE.chatPendingLabel = "";
  updateChatLiveIndicators();
}

function applyChatSnapshot(sessionsPayload, detail, { allowDefer = false } = {}) {
  const nextRevision = Number(detail?.session_revision || detail?.session?.session_revision || 0);
  const shouldDefer = allowDefer && UI_STATE.chatDetail && shouldDeferChatHydration();
  if (shouldDefer) {
    UI_STATE.chatPendingPayload = { sessionsPayload, detail };
    UI_STATE.chatPendingLabel = buildChatPendingLabel(UI_STATE.chatDetail, detail);
    updateChatLiveIndicators();
    return false;
  }
  rememberChatPayload(sessionsPayload, detail);
  clearChatPendingPayload();
  renderChat(UI_STATE.chatSessionsPayload, UI_STATE.chatDetail);
  return nextRevision > 0;
}

function renderChatFromState() {
  if (!UI_STATE.chatSessionsPayload || !UI_STATE.chatDetail) return;
  renderChat(UI_STATE.chatSessionsPayload, UI_STATE.chatDetail);
}

async function applyPendingChatUpdate() {
  if (!UI_STATE.chatPendingPayload) return;
  const pending = UI_STATE.chatPendingPayload;
  UI_STATE.chatPendingPayload = null;
  UI_STATE.chatPendingLabel = "";
  rememberChatPayload(pending.sessionsPayload, pending.detail);
  renderChatFromState();
}

function focusChatDraftToEnd() {
  const textarea = document.getElementById("chat-draft");
  if (!textarea) return;
  textarea.focus();
  const length = textarea.value.length;
  textarea.setSelectionRange(length, length);
}

function buildChatHistoryText(detail) {
  const session = detail?.session || {};
  const transcript = detail?.transcript || [];
  const lines = [
    `session_id: ${session.session_id || ""}`,
    `session_name: ${session.session_name || ""}`,
    `message_count: ${transcript.length}`,
    "",
  ];
  transcript.forEach((message) => {
    lines.push(`[${formatDateTime(message.created_at)}] ${t(`common.${message.role}`)} | ${message.delivery_kind || t("common.none")} | ${message.status || t("common.unknown")}`);
    lines.push(String(message.text || ""));
    lines.push("");
  });
  return lines.join("\n").trim();
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";
  document.body.appendChild(textarea);
  textarea.select();
  const success = document.execCommand("copy");
  document.body.removeChild(textarea);
  if (!success) {
    throw new Error("copy_failed");
  }
}

function setChatCopyFeedback(message) {
  UI_STATE.chatCopyFeedback = message;
  updateChatLiveIndicators();
  window.clearTimeout(UI_STATE.chatCopyFeedbackTimer);
  UI_STATE.chatCopyFeedbackTimer = window.setTimeout(() => {
    UI_STATE.chatCopyFeedback = "";
    updateChatLiveIndicators();
  }, 1800);
}

function detectLocale() {
  const stored = window.localStorage.getItem("dashboard:locale");
  if (stored === "zh" || stored === "en") return stored;
  const browserLanguage = (navigator.language || navigator.userLanguage || "zh").toLowerCase();
  return browserLanguage.startsWith("zh") ? "zh" : "en";
}

function detectSourceView() {
  const stored = window.localStorage.getItem(SOURCE_VIEW_STORAGE_KEY);
  return stored === "all" ? "all" : "real";
}

function getSourceView() {
  return UI_STATE.sourceView === "all" ? "all" : "real";
}

function shouldShowSourceViewControl() {
  return !sampleId && ["runs", "flow", "growth", "agency"].includes(view);
}

function buildApiPath(path, { includeSourceView = true } = {}) {
  if (!includeSourceView || !shouldShowSourceViewControl()) return path;
  const url = new URL(path, window.location.origin);
  url.searchParams.set("source_view", getSourceView());
  return `${url.pathname}${url.search}`;
}

function renderSourceViewControl() {
  if (!shouldShowSourceViewControl()) return "";
  return `
    <label class="source-view-control">
      <span>${escapeHtml(t("common.source_view"))}</span>
      <select id="source-view-select" data-source-view>
        <option value="real"${getSourceView() === "real" ? " selected" : ""}>${escapeHtml(t("common.real_data"))}</option>
        <option value="all"${getSourceView() === "all" ? " selected" : ""}>${escapeHtml(t("common.all_data"))}</option>
      </select>
    </label>
  `;
}

function setLocale(locale) {
  UI_STATE.locale = locale === "en" ? "en" : "zh";
  window.localStorage.setItem("dashboard:locale", UI_STATE.locale);
  document.documentElement.lang = UI_STATE.locale === "zh" ? "zh-CN" : "en";
  applyChrome();
  refresh().catch((error) => {
    app.innerHTML = `<section class="panel"><div class="empty">${escapeHtml(error.message)}</div></section>`;
  });
}

function semanticText(group, code) {
  return lookupCodeLabel(group, code) ?? t(`semantic.${group}.${code || "unknown"}`);
}

function prefixedSemantic(label) {
  const match = String(label ?? "").match(/^semantic\.(intent|host|result|growth|evidence|headline|why)\.(.+)$/);
  return match ? { group: match[1], code: match[2] } : null;
}

function translateLabel(label, labelType = "raw") {
  if (label === null || label === undefined || label === "") return t("common.none");
  const semantic = prefixedSemantic(label);
  if (semantic) return semanticText(semantic.group, semantic.code);
  if (labelType === "headline") return semanticText("headline", label);
  if (labelType === "intent") return semanticText("intent", label);
  if (labelType === "host") return semanticText("host", label);
  if (labelType === "result") return semanticText("result", label);
  if (labelType === "growth") return semanticText("growth", label);
  if (labelType === "evidence") return semanticText("evidence", label);
  if (labelType === "why") return lookupCodeLabel("why", label) ?? semanticText("why", label);
  if (labelType === "action") return lookupCodeLabel("actions", label) ?? String(label);
  if (labelType === "host_status") return lookupCodeLabel("host_status", label) ?? String(label);
  if (labelType === "continuity_status") return lookupCodeLabel("continuity_status", label) ?? String(label);
  if (labelType === "continuity_scenario") return lookupCodeLabel("continuity_scenario", label) ?? String(label);
  if (labelType === "appraisal") return lookupCodeLabel("appraisal", label) ?? String(label);
  if (labelType === "reflection_trigger") return lookupCodeLabel("reflection_trigger", label) ?? String(label);
  if (labelType === "focus") return lookupCodeLabel("focus", label) ?? String(label);
  if (labelType === "failure_cause") return lookupCodeLabel("failure_cause", label) ?? String(label);
  if (labelType === "severity") return lookupCodeLabel("severity", label) ?? String(label);
  if (labelType === "retest") return lookupCodeLabel("retest", String(label)) ?? String(label);
  return String(label);
}

function artifactLabel(name) {
  return t(`artifacts.${name}`);
}

function applyChrome() {
  const heroScope = view === "chat" ? "hero.chat" : "hero";
  document.getElementById("hero-eyebrow").textContent = t(`${heroScope}.eyebrow`);
  document.getElementById("hero-title").textContent = t(`${heroScope}.title`);
  document.getElementById("hero-copy").textContent = t(`${heroScope}.copy`);
  document.getElementById("nav-runs").textContent = t("nav.runs");
  document.getElementById("nav-flow").textContent = t("nav.flow");
  document.getElementById("nav-chat").textContent = t("nav.chat");
  document.getElementById("nav-agency").textContent = t("nav.agency");
  document.getElementById("nav-growth").textContent = t("nav.growth");
  document.getElementById("nav-failures").textContent = t("nav.failures");
  document.querySelectorAll(".nav a").forEach((link) => {
    const route = link.getAttribute("href");
    link.classList.toggle("active", route === (VIEW_ROUTES[view] || "/runs"));
  });
  document.querySelectorAll("#locale-switch button").forEach((button) => {
    button.classList.toggle("active", button.dataset.locale === UI_STATE.locale);
  });
}

function pageIntro(title, subtitle, extras = [], options = {}) {
  const showAutoRefresh = options.showAutoRefresh ?? true;
  const introExtras = [renderSourceViewControl(), ...extras].filter(Boolean);
  return `
    <section class="panel intro-panel">
      <div class="intro-head">
        <div>
          <h2>${escapeHtml(title)}</h2>
          <p>${escapeHtml(subtitle)}</p>
        </div>
        <div class="pill-row">
          ${showAutoRefresh ? `<span class="pill ok">${escapeHtml(t("common.auto_refresh"))}</span>` : ""}
          ${introExtras.join("")}
        </div>
      </div>
    </section>
  `;
}

function renderMeta(buildMeta = {}, gapSummary = {}) {
  const items = [
    [t("meta.total_runs"), buildMeta.total_runs ?? 0],
    [t("meta.complete_runs"), buildMeta.complete_runs ?? 0],
    [t("meta.oe_runs"), buildMeta.oe_available_runs ?? 0],
    [t("meta.host_only"), buildMeta.host_only_runs ?? 0],
    [t("meta.agency_records"), buildMeta.agency_records ?? 0],
    [t("meta.failures"), buildMeta.failure_cases ?? 0],
  ];
  const continuityItems = Object.entries(gapSummary.continuity_status || {}).map(
    ([label, value]) => `
      <article class="stat-card">
        <strong>${escapeHtml(translateLabel(value, "continuity_status"))}</strong>
        <span>${escapeHtml(`${t("common.continuity")} · ${translateLabel(label, "continuity_scenario")}`)}</span>
      </article>
    `,
  );
  metaBar.innerHTML =
    items
      .map(
        ([label, value]) => `
          <article class="stat-card">
            <strong>${escapeHtml(value)}</strong>
            <span>${escapeHtml(label)}</span>
          </article>
        `,
      )
      .join("") + continuityItems.join("");
}

function metricCards(items) {
  return `
    <section class="metric-grid">
      ${items
        .map(
          ([label, value]) => `
            <article class="metric-card">
              <strong>${escapeHtml(value)}</strong>
              <span>${escapeHtml(label)}</span>
            </article>
          `,
        )
        .join("")}
    </section>
  `;
}

function semanticPills(semantic = {}) {
  const chips = [
    semantic.intent_code ? semanticText("intent", semantic.intent_code) : null,
    semantic.host_posture_code ? semanticText("host", semantic.host_posture_code) : null,
    semantic.result_state_code ? semanticText("result", semantic.result_state_code) : null,
    semantic.evidence_state_code ? semanticText("evidence", semantic.evidence_state_code) : null,
  ].filter(Boolean);
  return chips
    .map((label, index) => `<span class="pill ${index === 1 ? "warning" : "ok"}">${escapeHtml(label)}</span>`)
    .join("");
}

function whyPills(whyCodes = []) {
  return whyCodes
    .map((code) => `<span class="pill warning">${escapeHtml(semanticText("why", code))}</span>`)
    .join("");
}

function renderDistribution(title, values = {}, labelType = "raw") {
  const entries = Object.entries(values || {}).sort((a, b) => Number(b[1]) - Number(a[1]));
  if (!entries.length) {
    return `
      <article class="panel">
        <h3>${escapeHtml(title)}</h3>
        <div class="empty">${escapeHtml(t("common.no_data"))}</div>
      </article>
    `;
  }
  const maxValue = Math.max(...entries.map(([, value]) => Number(value || 0)), 1);
  return `
    <article class="panel">
      <h3>${escapeHtml(title)}</h3>
      <div class="distribution-list">
        ${entries
          .map(([label, value]) => {
            const text = translateLabel(label, labelType);
            return `
              <div class="distribution-row">
                <span class="distribution-label">${escapeHtml(text)}</span>
                <div class="distribution-bar">
                  <span style="width:${(Number(value || 0) / maxValue) * 100}%"></span>
                </div>
                <strong>${escapeHtml(value)}</strong>
              </div>
            `;
          })
          .join("")}
      </div>
    </article>
  `;
}

function buildNumericTrendSvg(items, valueKey, markerKey = null) {
  if (!items.length) return `<div class="empty">${escapeHtml(t("common.no_data"))}</div>`;
  const width = 820;
  const height = 220;
  const padX = 28;
  const padY = 18;
  const values = items.map((item) => Number(item[valueKey] || 0));
  const maxValue = Math.max(1, ...values);
  const stepX = items.length === 1 ? 0 : (width - padX * 2) / (items.length - 1);
  const points = items.map((item, index) => {
    const x = padX + stepX * index;
    const y = height - padY - ((Number(item[valueKey] || 0) / maxValue) * (height - padY * 2));
    return { x, y, item };
  });
  const polyline = points.map((point) => `${point.x},${point.y}`).join(" ");
  const markers = markerKey
    ? points
        .filter((point) => point.item[markerKey])
        .map((point) => `<circle class="marker candidate" cx="${point.x}" cy="${point.y}" r="4"></circle>`)
        .join("")
    : "";
  return `
    <svg class="trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <line class="trend-axis" x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}"></line>
      <polyline class="trend-line" points="${polyline}"></polyline>
      ${markers}
    </svg>
  `;
}

function buildRunTimeline(items = []) {
  if (!items.length) return `<div class="empty">${escapeHtml(t("common.no_data"))}</div>`;
  return `
    <div class="timeline-strip">
      ${items
        .map((item) => {
          let statusClass = "warning";
          if (item.host_only) statusClass = "danger";
          else if (item.bundle_complete) statusClass = "ok";
          const label = item.semantic?.headline_code ? semanticText("headline", item.semantic.headline_code) : item.sample_id;
          return `
            <a class="timeline-dot ${statusClass}" href="/samples/${encodeURIComponent(item.sample_id)}" title="${escapeHtml(label)}"></a>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderKpiAndHeadline(headlineCode, summaryLines = [], extraPills = []) {
  return `
    <section class="panel story-panel">
      <div class="story-headline">${escapeHtml(semanticText("headline", headlineCode || "unknown"))}</div>
      ${summaryLines.length ? `<p class="muted">${escapeHtml(summaryLines.join(" · "))}</p>` : ""}
      <div class="pill-row">
        ${extraPills.join("")}
      </div>
    </section>
  `;
}

function agencyStoryCards(cards = []) {
  return `
    <section class="story-grid">
      ${cards
        .map((card) => {
          const groupMap = {
            intent: "intent",
            host: "host",
            result: "result",
            growth: "growth",
          };
          const group = groupMap[card.slot] || "headline";
          const value =
            Array.isArray(card.value)
              ? actionList(card.value)
              : card.value === null || card.value === undefined
                ? t("common.none")
                : card.slot === "result"
                  ? translateLabel(card.value, "action")
                  : String(card.value);
          return `
            <article class="story-card">
              <span>${escapeHtml(t(`common.${card.slot}`))}</span>
              <strong>${escapeHtml(semanticText(group, card.code))}</strong>
              <em>${escapeHtml(value)}</em>
            </article>
          `;
        })
        .join("")}
    </section>
  `;
}

function renderAgency(payload) {
  const summary = payload?.summary || {};
  const latest = payload?.latest_state;
  const trends = payload?.trends || [];
  const recentTurns = payload?.recent_turns || [];
  const distributions = payload?.distributions || {};
  const semanticSummary = payload?.semantic_summary || {};

  if (!summary.turn_count) {
    app.innerHTML = `
      ${pageIntro(t("pages.agency.title"), t("pages.agency.subtitle"))}
      <section class="panel"><div class="empty">${escapeHtml(t("common.no_agency"))}</div></section>
    `;
    return;
  }

  const extraPills = [
    `<span class="pill ok">${escapeHtml(`${t("meta.freshness")}: ${formatFreshness(payload.freshness_seconds)}`)}</span>`,
    `<span class="pill ok">${escapeHtml(`${t("common.profile")}: ${(payload.profile_scope || []).join(", ")}`)}</span>`,
    latest?.semantic ? `<span class="pill ok">${escapeHtml(semanticText("evidence", latest.semantic.evidence_state_code))}</span>` : "",
  ];

  const latestSummary = latest
    ? [
        `${t("meta.current_focus")}: ${translateLabel(latest.focus_goal || "none", "focus")}`,
        `${t("common.result")}: ${semanticText("result", latest.semantic?.result_state_code || "unknown")}`,
      ]
    : [];

  app.innerHTML = `
    ${pageIntro(t("pages.agency.title"), t("pages.agency.subtitle"), extraPills)}
    ${renderKpiAndHeadline(payload.headline_code, latestSummary, [
      latest?.semantic ? `<span class="pill ok">${escapeHtml(semanticText("intent", latest.semantic.intent_code))}</span>` : "",
      latest?.semantic ? `<span class="pill warning">${escapeHtml(semanticText("host", latest.semantic.host_posture_code))}</span>` : "",
      latest?.semantic ? `<span class="pill ok">${escapeHtml(semanticText("growth", latest.semantic.growth_motion_code))}</span>` : "",
    ])}
    ${agencyStoryCards(payload.story_cards || [])}
    ${metricCards([
      [t("pages.agency.turns"), summary.turn_count],
      [t("pages.agency.candidate_rate"), formatPercent(summary.candidate_generated_rate)],
      [t("pages.agency.writeback_rate"), formatPercent(summary.exec_result_writeback_rate)],
      [t("pages.agency.trace_complete"), formatPercent(summary.trace_completeness_rate)],
      [t("pages.agency.violations"), summary.direct_execution_violations],
      [t("pages.agency.mean_urge"), formatFloat(summary.mean_urge, 3)],
    ])}
    <section class="panel">
      <h2>${escapeHtml(t("pages.agency.funnel"))}</h2>
      <div class="funnel-grid">
        ${[
          [t("charts.idle_eligible"), payload.funnel?.idle_eligible_count],
          [t("charts.candidate_generated"), payload.funnel?.candidate_generated_count],
          [t("charts.governor_approved"), payload.funnel?.governor_approved_count],
          [t("charts.host_action"), payload.funnel?.host_action_count],
          [t("charts.writeback"), payload.funnel?.writeback_count],
        ]
          .map(
            ([label, count]) => `
              <article class="funnel-step">
                <div class="funnel-top">
                  <strong>${escapeHtml(count ?? 0)}</strong>
                  <span>${escapeHtml(label)}</span>
                </div>
                <div class="mini-bar">
                  <span style="width:${Math.max(summary.turn_count ? (Number(count || 0) / summary.turn_count) * 100 : 0, 4)}%"></span>
                </div>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
    <section class="panel">
      <div class="section-head">
        <div>
          <h2>${escapeHtml(t("pages.agency.trend"))}</h2>
          <p class="muted">${escapeHtml(t("pages.agency.trend_hint"))}</p>
        </div>
        <a class="subtle-link" href="/samples/${encodeURIComponent(latest?.sample_id || "")}">${escapeHtml(t("common.view_sample"))}</a>
      </div>
      ${buildNumericTrendSvg(trends, "urge_score", "candidate_generated")}
    </section>
    <section class="distribution-grid">
      ${renderDistribution(t("pages.agency.distributions.candidate"), distributions.candidate_actions, "action")}
      ${renderDistribution(t("pages.agency.distributions.governor"), distributions.governor_status, "host_status")}
      ${renderDistribution(t("pages.agency.distributions.final"), distributions.final_host_action, "action")}
      ${renderDistribution(t("pages.agency.distributions.suppression"), distributions.suppression_reason, "why")}
      ${renderDistribution(`${t("pages.agency.title")} · intent`, semanticSummary.intent || {}, "intent")}
      ${renderDistribution(`${t("pages.agency.title")} · result`, semanticSummary.result_state || {}, "result")}
    </section>
    <section class="panel">
      <div class="section-head">
        <h2>${escapeHtml(t("pages.agency.recent"))}</h2>
        <span class="muted">${escapeHtml(t("common.summary_only"))}</span>
      </div>
      <div class="card-list">
        ${recentTurns
          .map(
            (item) => `
              <article class="summary-card">
                <div class="summary-card-head">
                  <strong>${escapeHtml(semanticText("headline", item.semantic?.headline_code || "unknown"))}</strong>
                  <a class="subtle-link" href="/samples/${encodeURIComponent(item.sample_id)}">${escapeHtml(t("common.view_sample"))}</a>
                </div>
                <p class="muted">${escapeHtml(
                  `${item.sample_id} · ${formatFloat(item.urge_score, 3)} · ${actionList(item.candidate_actions)} · ${translateLabel(item.final_host_action || "none", "action")}`,
                )}</p>
                <div class="pill-row">
                  ${semanticPills(item.semantic)}
                  ${whyPills(item.semantic?.why_codes || [])}
                </div>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function actionList(actions) {
  if (!actions?.length) return t("common.none");
  return actions.map((action) => translateLabel(action, "action")).join(", ");
}

function renderRuns(payload) {
  const summary = payload?.summary || {};
  const recentRuns = payload?.recent_runs || [];
  const charts = payload?.charts || {};
  const continuity = payload?.continuity || [];

  if (!summary.turn_count) {
    app.innerHTML = `
      ${pageIntro(t("pages.runs.title"), t("pages.runs.subtitle"))}
      <section class="panel"><div class="empty">${escapeHtml(t("common.no_data"))}</div></section>
    `;
    return;
  }

  const continuityPills = continuity.map(
    (item) =>
      `<span class="pill ${item.status === "missing" ? "danger" : item.status === "cross_evidence" ? "warning" : "ok"}">${escapeHtml(
        `${translateLabel(item.scenario, "continuity_scenario")}: ${translateLabel(item.status, "continuity_status")}`,
      )}</span>`,
  );

  app.innerHTML = `
    ${pageIntro(t("pages.runs.title"), t("pages.runs.subtitle"), continuityPills)}
    ${renderKpiAndHeadline(payload.headline_code, [], [
      `<span class="pill ok">${escapeHtml(`${t("pages.runs.latest_bundle")}: ${String(summary.latest_bundle_complete)}`)}</span>`,
      `<span class="pill ok">${escapeHtml(`${t("pages.runs.latest_oe")}: ${String(summary.latest_oe_available)}`)}</span>`,
    ])}
    ${metricCards([
      [t("pages.runs.turns"), summary.turn_count],
      [t("pages.runs.complete_rate"), formatPercent(summary.complete_bundle_rate)],
      [t("pages.runs.oe_rate"), formatPercent(summary.oe_available_rate)],
      [t("pages.runs.host_only_rate"), formatPercent(summary.host_only_rate)],
      [t("pages.runs.latest_bundle"), String(summary.latest_bundle_complete)],
      [t("pages.runs.latest_oe"), String(summary.latest_oe_available)],
    ])}
    <section class="panel">
      <h2>${escapeHtml(t("pages.runs.bundle_trend"))}</h2>
      ${buildRunTimeline(charts.bundle_trend || [])}
    </section>
    <section class="distribution-grid">
      ${renderDistribution(t("pages.runs.state_dist"), charts.oe_state_distribution || {}, "evidence")}
      ${renderDistribution(t("pages.runs.gap_dist"), charts.gap_type_distribution || {}, "why")}
      ${renderDistribution(t("pages.runs.continuity"), charts.continuity_status || {}, "continuity_status")}
    </section>
    <section class="panel">
      <div class="section-head">
        <h2>${escapeHtml(t("pages.runs.recent"))}</h2>
        <span class="muted">${escapeHtml(t("common.summary_only"))}</span>
      </div>
      <div class="card-list">
        ${recentRuns
          .map(
            (item) => `
              <article class="summary-card">
                <div class="summary-card-head">
                  <strong>${escapeHtml(semanticText("headline", item.semantic?.headline_code || "unknown"))}</strong>
                  <a class="subtle-link" href="/samples/${encodeURIComponent(item.sample_id)}">${escapeHtml(t("common.view_sample"))}</a>
                </div>
                <p class="muted">${escapeHtml(`${item.sample_id} · gaps=${(item.gap_types || []).length}`)}</p>
                <div class="pill-row">
                  ${semanticPills(item.semantic)}
                  ${whyPills(item.semantic?.why_codes || item.gap_types || [])}
                </div>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderGrowth(payload) {
  const summary = payload?.summary || {};
  const charts = payload?.charts || {};
  const recentGrowth = payload?.recent_growth || [];
  if (!summary.total_records) {
    app.innerHTML = `
      ${pageIntro(t("pages.growth.title"), t("pages.growth.subtitle"))}
      <section class="panel"><div class="empty">${escapeHtml(t("common.no_data"))}</div></section>
    `;
    return;
  }

  app.innerHTML = `
    ${pageIntro(t("pages.growth.title"), t("pages.growth.subtitle"))}
    ${renderKpiAndHeadline(payload.headline_code)}
    ${metricCards([
      [t("pages.growth.total"), summary.total_records],
      [t("pages.growth.reflecting"), summary.reflecting_count],
      [t("pages.growth.repairing"), summary.repairing_count],
      [t("pages.growth.focus_shift"), summary.focus_shift_count],
      [t("pages.growth.identity_shift"), summary.identity_shift_count],
      [t("pages.growth.revision"), summary.latest_revision_counter],
    ])}
    <section class="panel">
      <h2>${escapeHtml(t("pages.growth.revision_trend"))}</h2>
      ${buildNumericTrendSvg(charts.revision_trend || [], "revision_counter")}
    </section>
    <section class="distribution-grid">
      ${renderDistribution(t("pages.growth.appraisal"), charts.appraisal_component_means || {}, "appraisal")}
      ${renderDistribution(t("pages.growth.motion"), charts.growth_motion_distribution || {}, "growth")}
      ${renderDistribution(t("pages.growth.reflection_trigger"), charts.reflection_trigger_distribution || {}, "reflection_trigger")}
      ${renderDistribution(t("pages.growth.focus_timeline"), payload.semantic_summary?.focus || {}, "focus")}
    </section>
    <section class="panel">
      <div class="section-head">
        <h2>${escapeHtml(t("pages.growth.recent"))}</h2>
        <span class="muted">${escapeHtml(t("common.summary_only"))}</span>
      </div>
      <div class="card-list">
        ${recentGrowth
          .map(
            (item) => `
              <article class="summary-card">
                <div class="summary-card-head">
                  <strong>${escapeHtml(semanticText("headline", item.semantic?.headline_code || "unknown"))}</strong>
                  <a class="subtle-link" href="/samples/${encodeURIComponent(item.sample_id)}">${escapeHtml(t("common.view_sample"))}</a>
                </div>
                <p class="muted">${escapeHtml(
                  `${item.sample_id} · ${translateLabel(item.focus_goal || "none", "focus")} · rev=${item.revision_counter}`,
                )}</p>
                <div class="pill-row">
                  ${semanticPills(item.semantic)}
                  ${whyPills(item.semantic?.why_codes || [])}
                </div>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderFailures(payload) {
  const summary = payload?.summary || {};
  const charts = payload?.charts || {};
  const recentFailures = payload?.recent_failures || [];
  if (!summary.total_failures) {
    app.innerHTML = `
      ${pageIntro(t("pages.failures.title"), t("pages.failures.subtitle"))}
      <section class="panel"><div class="empty">${escapeHtml(t("common.no_data"))}</div></section>
    `;
    return;
  }

  app.innerHTML = `
    ${pageIntro(t("pages.failures.title"), t("pages.failures.subtitle"))}
    ${renderKpiAndHeadline(payload.headline_code)}
    ${metricCards([
      [t("pages.failures.total"), summary.total_failures],
      [t("pages.failures.unresolved"), summary.unresolved_count],
      [t("pages.failures.retested_rate"), formatPercent(summary.retested_rate)],
      [t("pages.failures.top_cause"), translateLabel(summary.top_cause || "none", "failure_cause")],
      [t("pages.failures.replay_mismatch"), summary.replay_mismatch_count],
    ])}
    <section class="distribution-grid">
      ${renderDistribution(t("pages.failures.cause_dist"), charts.cause_distribution || {}, "failure_cause")}
      ${renderDistribution(t("pages.failures.severity_dist"), charts.severity_distribution || {}, "severity")}
      ${renderDistribution(t("pages.failures.retested_dist"), charts.retested_distribution || {}, "retest")}
      ${renderDistribution(t("pages.failures.blockers"), Object.fromEntries((charts.top_blockers || []).map((item) => [item.label, item.count])), "why")}
    </section>
    <section class="panel">
      <div class="section-head">
        <h2>${escapeHtml(t("pages.failures.recent"))}</h2>
        <span class="muted">${escapeHtml(t("common.summary_only"))}</span>
      </div>
      <div class="card-list">
        ${recentFailures
          .map((item) => {
            const open = UI_STATE.detailOpen.has(`failure:${item.failure_id}`);
            return `
              <article class="summary-card">
                <div class="summary-card-head">
                  <strong>${escapeHtml(semanticText("headline", item.semantic?.headline_code || "unknown"))}</strong>
                  <button class="subtle-button" type="button" data-detail-key="failure:${escapeHtml(item.failure_id)}">${escapeHtml(
                    open ? t("common.details_hidden") : t("common.view_details"),
                  )}</button>
                </div>
                <p class="muted">${escapeHtml(
                  `${item.failure_id} · ${translateLabel(item.cause_type, "failure_cause")} · ${translateLabel(item.severity, "severity")}`,
                )}</p>
                <div class="pill-row">
                  ${semanticPills(item.semantic)}
                  ${whyPills(item.semantic?.why_codes || [])}
                </div>
                ${open ? `<div class="detail-block"><pre>${escapeHtml(JSON.stringify(item, null, 2))}</pre></div>` : ""}
              </article>
            `;
          })
          .join("")}
      </div>
    </section>
  `;
}

function artifactSummary(name, value, detail) {
  if (name === "ledger.json" && value && typeof value === "object") {
    const eventCount = ((value.openemotion || {}).events || []).length;
    return `
      <ul class="artifact-summary-list">
        <li>sample_id: ${escapeHtml(value.sample_id || detail.sample_id)}</li>
        <li>timestamp: ${escapeHtml(value.timestamp || t("common.unknown"))}</li>
        <li>oe_events: ${escapeHtml(eventCount)}</li>
      </ul>
    `;
  }
  if (name === "openemotion_trace.json" && value && typeof value === "object") {
    return `
      <ul class="artifact-summary-list">
        <li>subject_profile: ${escapeHtml(value.subject_profile || t("common.unknown"))}</li>
        <li>reflection_trigger: ${escapeHtml(value.reflection_trigger || t("common.none"))}</li>
        <li>top_keys: ${escapeHtml(Object.keys(value).slice(0, 6).join(", "))}</li>
      </ul>
    `;
  }
  if (name === "response_plan.json" && value && typeof value === "object") {
    return `
      <ul class="artifact-summary-list">
        <li>status: ${escapeHtml(value.status || t("common.unknown"))}</li>
        <li>delivery_kind: ${escapeHtml(value.delivery_kind || t("common.none"))}</li>
      </ul>
    `;
  }
  if (name.endsWith(".md") && typeof value === "string") {
    return `<p class="muted">${escapeHtml(value.split("\n").slice(0, 4).join(" ").slice(0, 220))}</p>`;
  }
  if (value && typeof value === "object") {
    return `<p class="muted">${escapeHtml(`${Object.keys(value).length} keys · ${Object.keys(value).slice(0, 6).join(", ")}`)}</p>`;
  }
  return `<p class="muted">${escapeHtml(String(value).slice(0, 220) || t("common.none"))}</p>`;
}

function flowStatusClass(status) {
  if (status === "pass") return "ok";
  if (status === "degraded") return "warning";
  if (status === "host_only" || status === "broken") return "danger";
  return "";
}

function renderEngineeringFields(sectionKey, fields = []) {
  const open = UI_STATE.detailOpen.has(`flow:${sectionKey}`);
  return `
    <div class="button-row">
      <button class="subtle-button ${open ? "active" : ""}" type="button" data-detail-key="flow:${escapeHtml(sectionKey)}">${escapeHtml(
        open ? t("common.details_hidden") : t("common.view_details"),
      )}</button>
    </div>
    ${
      open
        ? `
      <div class="detail-block">
        <div class="field-list">
          ${fields
            .map(
              (field) => `
                <article class="field-card">
                  <strong>${escapeHtml(field.label || t("common.unknown"))}</strong>
                  <span>${escapeHtml(field.artifact || t("common.unknown"))}</span>
                  <code>${escapeHtml(field.path || t("common.unknown"))}</code>
                  <pre>${escapeHtml(
                    typeof field.value === "string" ? field.value : JSON.stringify(field.value, null, 2),
                  )}</pre>
                </article>
              `,
            )
            .join("")}
        </div>
      </div>
    `
        : ""
    }
  `;
}

function renderFlowSection(title, section, sectionKey) {
  const artifacts = section?.artifacts || [];
  const chips = [
    `<span class="pill ${flowStatusClass(section?.status)}">${escapeHtml(section?.status || t("common.unknown"))}</span>`,
    ...artifacts.map((artifact) => `<span class="pill">${escapeHtml(artifactLabel(artifact))}</span>`),
  ];
  const summaryEntries = Object.entries(section || {})
    .filter(([key, value]) => !["status", "headline", "sentence", "artifacts", "engineering_fields"].includes(key) && value !== null && value !== undefined && value !== "")
    .slice(0, 10);
  return `
    <article class="panel flow-card">
      <div class="section-head">
        <div>
          <h3>${escapeHtml(title)}</h3>
          <strong class="flow-headline">${escapeHtml(section?.headline || t("common.unknown"))}</strong>
          <p class="muted">${escapeHtml(section?.sentence || t("common.no_data"))}</p>
        </div>
        <div class="pill-row">${chips.join("")}</div>
      </div>
      <div class="detail-grid">
        ${summaryEntries
          .map(
            ([label, value]) => `
              <article class="metric-card">
                <strong>${escapeHtml(typeof value === "string" ? value : JSON.stringify(value))}</strong>
                <span>${escapeHtml(label)}</span>
              </article>
            `,
          )
          .join("")}
      </div>
      ${renderEngineeringFields(sectionKey, section?.engineering_fields || [])}
    </article>
  `;
}

function renderMetricGrid(entries) {
  const filtered = entries.filter((entry) => entry && entry.value !== null && entry.value !== undefined && entry.value !== "");
  if (!filtered.length) {
    return `<div class="empty">${escapeHtml(t("common.no_data"))}</div>`;
  }
  return `
    <div class="detail-grid">
      ${filtered
        .map(
          (entry) => `
            <article class="metric-card">
              <strong>${escapeHtml(typeof entry.value === "string" ? entry.value : JSON.stringify(entry.value))}</strong>
              <span>${escapeHtml(entry.label)}</span>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderReplyEvolution(section) {
  const subject = section?.subject_influence || {};
  const host = section?.host_arbitration || {};
  const finalOutput = section?.final_output || {};
  const chips = [
    `<span class="pill ${flowStatusClass(section?.status)}">${escapeHtml(section?.status || t("common.unknown"))}</span>`,
    `<span class="pill">${escapeHtml(section?.mode || "unknown")}</span>`,
    `<span class="pill">${escapeHtml(section?.scope || "unknown")}</span>`,
  ];
  const finalTextValue =
    finalOutput.final_text_preview || finalOutput.final_text_capture_reason || t("pages.flow.finalTextMissing");

  return `
    <article class="panel flow-card">
      <div class="section-head">
        <div>
          <h3>${escapeHtml(t("pages.flow.replyEvolution"))}</h3>
          <strong class="flow-headline">${escapeHtml(section?.headline || t("common.unknown"))}</strong>
          <p class="muted">${escapeHtml(section?.sentence || t("common.no_data"))}</p>
        </div>
        <div class="pill-row">${chips.join("")}</div>
      </div>
      <div class="detail-block">
        <h4>${escapeHtml(t("pages.flow.availability"))}</h4>
        ${renderMetricGrid([
          { label: "available", value: section?.available === true ? "true" : "false" },
          { label: "reason", value: section?.reason || null },
        ])}
      </div>
      <div class="detail-block">
        <h4>${escapeHtml(t("pages.flow.subjectInfluence"))}</h4>
        ${renderMetricGrid([
          { label: "preferred_mode", value: subject?.response_tendency_summary?.preferred_mode || null },
          { label: "preferred_tone", value: subject?.response_tendency_summary?.preferred_tone || null },
          { label: "suggested_next_step", value: subject?.response_tendency_summary?.suggested_next_step || null },
          { label: "reply_mode", value: subject?.chat_expression_hint?.reply_mode || null },
          { label: "tone_profile", value: subject?.chat_expression_hint?.tone_profile || null },
          { label: "next_step_bias", value: subject?.chat_expression_hint?.next_step_bias || null },
          { label: "policy_hint_preview", value: subject?.policy_hint_preview || null },
          { label: "memory_claim_reason", value: subject?.memory_claim_reason || null },
        ])}
      </div>
      <div class="detail-block">
        <h4>${escapeHtml(t("pages.flow.hostArbitration"))}</h4>
        ${renderMetricGrid([
          { label: "reply_authority", value: host?.reply_authority || null },
          { label: "reply_origin", value: host?.reply_origin || null },
          { label: "chat_cadence_mode", value: host?.chat_cadence_mode || null },
          { label: "output_check_reason", value: host?.output_check_reason || null },
          { label: "intent_gate_reason", value: host?.intent_gate_reason || null },
          { label: "applied_authority", value: host?.applied_authority || null },
        ])}
      </div>
      <div class="detail-block">
        <h4>${escapeHtml(t("pages.flow.finalOutput"))}</h4>
        ${renderMetricGrid([
          { label: "final_text", value: finalTextValue },
          { label: "final_text_capture_status", value: finalOutput?.final_text_capture_status || null },
          { label: "reply_length", value: finalOutput?.reply_length ?? null },
          { label: "delivery_kind", value: finalOutput?.delivery_kind || null },
          { label: "message_sent", value: finalOutput?.message_sent === true ? "true" : finalOutput?.message_sent === false ? "false" : null },
        ])}
      </div>
      ${renderEngineeringFields("reply-evolution", section?.engineering_fields || [])}
    </article>
  `;
}

function renderCanonicalFields(section) {
  const host = section?.host_arbitration_result || {};
  const finalText = section?.final_delivered_text || {};
  const chips = [
    `<span class="pill ${flowStatusClass(section?.status)}">${escapeHtml(section?.status || t("common.unknown"))}</span>`,
    ...((section?.artifacts || []).map((artifact) => `<span class="pill">${escapeHtml(artifactLabel(artifact))}</span>`)),
  ];
  const finalTextValue = finalText.preview || finalText.capture_reason || t("pages.flow.finalTextMissing");
  return `
    <article class="panel flow-card">
      <div class="section-head">
        <div>
          <h3>${escapeHtml(t("pages.flow.canonicalFields"))}</h3>
          <strong class="flow-headline">${escapeHtml(section?.headline || t("common.unknown"))}</strong>
          <p class="muted">${escapeHtml(section?.sentence || t("common.no_data"))}</p>
        </div>
        <div class="pill-row">${chips.join("")}</div>
      </div>
      <div class="detail-block">
        ${renderMetricGrid([
          { label: "loaded_axes", value: section?.loaded_axes || null },
          { label: "identity_delta", value: section?.identity_delta || null },
          { label: "self_model_delta", value: section?.self_model_delta || null },
          { label: "drives_delta", value: section?.drives_delta || null },
          { label: "policy_hint", value: section?.policy_hint || null },
          { label: "response_tendency", value: section?.response_tendency || null },
          { label: "host_arbitration_result", value: host || null },
          { label: "final_delivered_text", value: finalTextValue },
          { label: "final_text_hash", value: finalText.hash || null },
          { label: "final_text_length", value: finalText.length ?? null },
          { label: "final_text_capture_status", value: finalText.capture_status || null },
        ])}
      </div>
      ${renderEngineeringFields("canonical-fields", section?.engineering_fields || [])}
    </article>
  `;
}

function renderFlow(payload) {
  if (!payload?.sample_id) {
    app.innerHTML = `
      ${pageIntro(t("pages.flow.title"), t("pages.flow.subtitle"))}
      <section class="panel"><div class="empty">${escapeHtml(t("common.no_sample"))}</div></section>
    `;
    return;
  }

  const verdict = payload.chain_status || {};
  const statusClass = flowStatusClass(verdict.overall_status);
  app.innerHTML = `
    ${pageIntro(t("pages.flow.title"), t("pages.flow.subtitle"), [
      `<span class="pill ${statusClass}">${escapeHtml(`${t("common.sample")}: ${payload.sample_id}`)}</span>`,
      `<a class="subtle-link" href="/samples/${encodeURIComponent(payload.sample_id)}">${escapeHtml(t("common.view_sample"))}</a>`,
    ])}
    <section class="panel story-panel">
      <div class="section-head">
        <div>
          <h2>${escapeHtml(t("pages.flow.verdict"))}</h2>
          <div class="story-headline">${escapeHtml(verdict.verdict_headline || t("common.unknown"))}</div>
          <p class="muted">${escapeHtml(verdict.verdict_sentence || t("common.no_data"))}</p>
          ${
            verdict.verdict_subsentence
              ? `<p class="muted">${escapeHtml(verdict.verdict_subsentence)}</p>`
              : ""
          }
        </div>
        <div class="pill-row">
          <span class="pill ${statusClass}">${escapeHtml(verdict.overall_status || t("common.unknown"))}</span>
          <span class="pill ${flowStatusClass(verdict.ingress_status)}">${escapeHtml(`${t("common.ingress")}: ${verdict.ingress_status || t("common.unknown")}`)}</span>
          <span class="pill ${flowStatusClass(verdict.subject_status)}">${escapeHtml(`${t("common.subject")}: ${verdict.subject_status || t("common.unknown")}`)}</span>
          <span class="pill ${flowStatusClass(verdict.arbitration_status)}">${escapeHtml(`${t("common.arbitration")}: ${verdict.arbitration_status || t("common.unknown")}`)}</span>
          <span class="pill ${flowStatusClass(verdict.delivery_status)}">${escapeHtml(`${t("common.output")}: ${verdict.delivery_status || t("common.unknown")}`)}</span>
        </div>
      </div>
    </section>
    <section class="flow-grid">
      ${renderFlowSection(t("pages.flow.input"), payload.input_summary || {}, "input")}
      ${renderFlowSection(t("pages.flow.ingress"), payload.host_ingress_summary || {}, "ingress")}
      ${renderFlowSection(t("pages.flow.subject"), payload.subject_summary || {}, "subject")}
      ${renderCanonicalFields(payload.canonical_fields_summary || {})}
      ${renderReplyEvolution(payload.reply_evolution_summary || {})}
      ${renderFlowSection(t("pages.flow.arbitration"), payload.host_arbitration_summary || {}, "arbitration")}
      ${renderFlowSection(t("pages.flow.output"), payload.output_summary || {}, "output")}
    </section>
    <section class="panel">
      <h2>${escapeHtml(t("pages.flow.gaps"))}</h2>
      <div class="detail-grid">
        ${Object.entries(payload.failure_or_gap_summary || {})
          .filter(([, value]) => value !== null && value !== undefined && value !== "")
          .map(
            ([label, value]) => `
              <article class="metric-card">
                <strong>${escapeHtml(typeof value === "string" ? value : JSON.stringify(value))}</strong>
                <span>${escapeHtml(label)}</span>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderSample(detail) {
  if (!detail?.sample_id) {
    app.innerHTML = `
      ${pageIntro(t("pages.sample.title"), t("pages.sample.subtitle"))}
      <section class="panel"><div class="empty">${escapeHtml(t("common.no_sample"))}</div></section>
    `;
    return;
  }
  const summary = detail.translated_summary || {};
  const semantic = detail.semantic_summary || {};
  const artifactBlocks = Object.entries(detail.artifacts || {})
    .map(([name, value]) => {
      const modeKey = `${detail.sample_id}:${name}`;
      const mode = UI_STATE.artifactModes.get(modeKey) || "summary";
      return `
        <article class="artifact-card">
          <div class="artifact-head">
            <h3>${escapeHtml(artifactLabel(name))}</h3>
            <div class="button-row">
              <button class="subtle-button ${mode === "summary" ? "active" : ""}" type="button" data-artifact-mode="summary" data-artifact-key="${escapeHtml(modeKey)}">${escapeHtml(t("common.view_summary"))}</button>
              <button class="subtle-button ${mode === "raw" ? "active" : ""}" type="button" data-artifact-mode="raw" data-artifact-key="${escapeHtml(modeKey)}">${escapeHtml(t("common.view_raw"))}</button>
            </div>
          </div>
          <div class="artifact-body ${mode === "summary" ? "" : "hidden"}">
            ${artifactSummary(name, value, detail)}
          </div>
          <div class="artifact-body ${mode === "raw" ? "" : "hidden"}">
            <pre>${escapeHtml(typeof value === "string" ? value : JSON.stringify(value, null, 2))}</pre>
          </div>
        </article>
      `;
    })
    .join("");

  app.innerHTML = `
    ${pageIntro(t("pages.sample.title"), t("pages.sample.subtitle"))}
    ${renderKpiAndHeadline(summary.headline_code, [
      `${t("common.sample")}: ${detail.sample_id}`,
      `${t("common.focus")}: ${summary.focus_goal || t("common.none")}`,
    ], [
      `<a class="subtle-link" href="/samples/${encodeURIComponent(detail.sample_id)}/flow">${escapeHtml(t("common.open_flow"))}</a>`,
      semanticPills(semantic),
      whyPills(summary.why_codes || []),
    ])}
    ${metricCards([
      [t("common.candidate"), actionList(summary.candidate_actions || [])],
      [t("common.host"), semanticText("host", summary.host_posture_code || "not_applicable")],
      [t("common.result"), semanticText("result", summary.result_state_code || "not_executed")],
      [t("common.growth"), semanticText("growth", summary.growth_motion_code || "unknown")],
      [t("common.evidence"), semanticText("evidence", summary.evidence_state_code || "partial")],
    ])}
    <section class="detail-grid">${artifactBlocks}</section>
  `;
}

function renderDebugRows(rows = []) {
  const blocks = rows
    .map(({ label, value }) => {
      if (value === null || value === undefined || value === "" || (typeof value === "object" && !Object.keys(value).length)) {
        return "";
      }
      if (typeof value === "object") {
        return `
          <div class="key-value-row block">
            <span>${escapeHtml(label)}</span>
            <pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>
          </div>
        `;
      }
      return `
        <div class="key-value-row">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `;
    })
    .filter(Boolean)
    .join("");
  return blocks || `<div class="empty">${escapeHtml(t("common.no_data"))}</div>`;
}

function renderDebugCard(title, rows = []) {
  return `
    <article class="panel debug-card">
      <h3>${escapeHtml(title)}</h3>
      ${renderDebugRows(rows)}
    </article>
  `;
}

function resolveLatestAssistantMessage(detail) {
  const transcript = detail?.transcript || [];
  for (let index = transcript.length - 1; index >= 0; index -= 1) {
    if (transcript[index]?.role === "assistant") return transcript[index];
  }
  return null;
}

function renderChat(sessionsPayload, detail) {
  const sessions = sessionsPayload?.sessions || [];
  const session = detail?.session || {};
  const transcript = detail?.transcript || [];
  const debugHistory = detail?.debug_history || {};
  const pendingSend = UI_STATE.chatPending.send?.sessionId === session.session_id;
  const pendingSwitch = UI_STATE.chatPending.switch?.sessionId === session.session_id;
  const pendingCreate = UI_STATE.chatPending.create?.tempSessionId === session.session_id;
  const latestAssistant = resolveLatestAssistantMessage(detail);
  if (!UI_STATE.chatSelectedMessageId || !debugHistory[UI_STATE.chatSelectedMessageId]) {
    UI_STATE.chatSelectedMessageId = latestAssistant?.message_id || null;
  }
  const selectedDebug = debugHistory[UI_STATE.chatSelectedMessageId] || detail?.last_debug || null;
  const selectedAssistant = transcript.find((item) => item.message_id === UI_STATE.chatSelectedMessageId) || latestAssistant;

  const sessionButtons = sessions.length
    ? sessions
        .map((item) => {
          const pendingKind = currentChatPendingKind(item.session_id);
          const pendingLabel = pendingKind ? t(`common.${pendingKind === "send" ? "typing" : pendingKind === "switch" ? "loading" : "creating"}`) : null;
          return `
            <button
              type="button"
              class="chat-session-button${item.session_id === session.session_id ? " active" : ""}${pendingKind ? ` pending ${pendingKind}` : ""}"
              data-chat-session-id="${escapeHtml(item.session_id)}"
            >
              <span>${escapeHtml(item.session_name)}</span>
              <small>${escapeHtml(`${t("common.message_count")}: ${item.message_count} · ${t("common.session_revision")}: ${item.session_revision || 0}`)}</small>
              ${pendingLabel ? `<small>${escapeHtml(pendingLabel)}</small>` : ""}
            </button>
          `;
        })
        .join("")
    : `<div class="empty">${escapeHtml(t("common.no_data"))}</div>`;

  const transcriptEmptyLabel =
    detail?.loading_state === "creating"
      ? t("common.creating_session")
      : detail?.loading_state === "loading"
        ? t("common.loading_session")
        : t("common.empty_chat");

  const transcriptHtml = transcript.length
    ? transcript
        .map((message) => {
          const selectable = message.role === "assistant" && !message.typing;
          const tag = selectable ? "button" : "article";
          const attrs = selectable ? `type="button" data-chat-message-id="${escapeHtml(message.message_id)}"` : "";
          const statusLabel = message.typing
            ? t("common.typing")
            : message.local_failed
              ? t("common.failed")
              : message.status || t("common.unknown");
          const bodyText = message.typing ? t("common.typing") : message.text;
          return `
            <${tag} class="chat-message ${escapeHtml(message.role)}${message.message_id === UI_STATE.chatSelectedMessageId ? " active" : ""}${message.typing ? " typing" : ""}${message.optimistic ? " pending" : ""}${message.local_failed ? " failed" : ""}" ${attrs}>
              <header>
                <strong>${escapeHtml(t(`common.${message.role}`))}</strong>
                <span>${escapeHtml(formatDateTime(message.created_at))}</span>
              </header>
              <p>${escapeHtml(bodyText)}</p>
              <footer>
                <span>${escapeHtml(message.delivery_kind || t("common.none"))}</span>
                <span>${escapeHtml(statusLabel)}</span>
              </footer>
            </${tag}>
          `;
        })
        .join("")
    : `<div class="empty">${escapeHtml(transcriptEmptyLabel)}</div>`;

  const debugCards = selectedDebug
    ? [
        renderDebugCard(t("pages.chat.subject_gate"), [
          { label: "ingress.ok", value: String(Boolean(selectedDebug?.subject_gate?.ingress?.ok)) },
          { label: "ingress.reason", value: selectedDebug?.subject_gate?.ingress?.reason || null },
          { label: "finalize.ok", value: selectedDebug?.subject_gate?.finalize ? String(Boolean(selectedDebug.subject_gate.finalize.ok)) : null },
          { label: "finalize.reason", value: selectedDebug?.subject_gate?.finalize?.reason || null },
        ]),
        renderDebugCard(t("pages.chat.ingress"), [
          { label: "runtime_action", value: selectedDebug?.ingress?.runtime_action || null },
          { label: "interaction_kind", value: selectedDebug?.ingress?.interaction_kind || null },
          { label: "request_mode", value: selectedDebug?.ingress?.request_mode || null },
          { label: "conversation_act", value: selectedDebug?.ingress?.conversation_act || null },
          { label: "parser_source", value: selectedDebug?.ingress?.parser_source || null },
          { label: "normalized_turn", value: selectedDebug?.ingress?.normalized_turn || null },
        ]),
        renderDebugCard(t("pages.chat.proto_self"), [
          { label: "subject_profile", value: selectedDebug?.proto_self?.subject_profile || null },
          { label: "policy_hint", value: selectedDebug?.proto_self?.policy_hint || null },
          { label: "response_tendency", value: selectedDebug?.proto_self?.response_tendency || null },
          { label: "candidate_actions", value: selectedDebug?.proto_self?.candidate_actions || null },
        ]),
        renderDebugCard(t("pages.chat.response_plan"), [
          { label: "kind", value: selectedDebug?.response_plan?.kind || null },
          { label: "delivery_kind", value: selectedDebug?.response_plan?.delivery_kind || null },
          { label: "reply_authority", value: selectedDebug?.response_plan?.reply_authority || null },
          { label: "authority_source", value: selectedDebug?.response_plan?.authority_source || null },
          { label: "degraded", value: selectedDebug?.response_plan?.metadata ? String(Boolean(selectedDebug.response_plan.metadata.degraded)) : null },
          { label: "chat_degradation", value: selectedDebug?.response_plan?.metadata?.chat_degradation || null },
          { label: "metadata", value: selectedDebug?.response_plan?.metadata || null },
        ]),
        renderDebugCard(t("pages.chat.output_check"), [
          { label: "passed", value: selectedDebug?.output_check ? String(Boolean(selectedDebug.output_check.passed)) : null },
          { label: "reason", value: selectedDebug?.output_check?.reason || null },
          { label: "applied_authority", value: selectedDebug?.output_check?.applied_authority || null },
          { label: "reply_origin", value: selectedDebug?.output_check?.reply_origin || null },
          { label: "intent_gate_reason", value: selectedDebug?.output_check?.intent_gate_reason || null },
        ]),
        renderDebugCard(t("pages.chat.delivery"), [
          { label: "should_send", value: String(Boolean(selectedDebug?.delivery?.should_send)) },
          { label: "delivery_kind", value: selectedDebug?.delivery?.delivery_kind || null },
          { label: "text_preview", value: selectedDebug?.delivery?.text_preview || null },
        ]),
        renderDebugCard(t("pages.chat.session_state"), [
          { label: "task_status", value: detail?.session_state?.task_status || null },
          { label: "active_turn_status", value: detail?.session_state?.active_turn_status || null },
          { label: "waiting_for_user_input", value: String(Boolean(detail?.session_state?.waiting_for_user_input)) },
          { label: "proto_self_scope", value: detail?.session_state?.proto_self_scope || null },
          { label: "ingress_context", value: detail?.session_state?.ingress_context || null },
          { label: "pending_result_continuation", value: detail?.session_state?.pending_result_continuation || null },
        ]),
      ].join("")
    : `<section class="panel"><div class="empty">${escapeHtml(t("common.empty_debug"))}</div></section>`;

  app.innerHTML = `
    ${pageIntro(t("pages.chat.title"), t("pages.chat.subtitle"), [
      `<span class="pill warning">${escapeHtml(t("common.local_test_only"))}</span>`,
      `<span class="pill ok">${escapeHtml(`${t("common.session")}: ${session.session_name || "default"}`)}</span>`,
      `<span class="pill ok">${escapeHtml(`${t("common.state")}: ${detail?.session_state?.task_status || t("common.unknown")}`)}</span>`,
    ], { showAutoRefresh: false })}
    ${UI_STATE.chatError ? `<section class="panel"><div class="empty">${escapeHtml(UI_STATE.chatError)}</div></section>` : ""}
    <section class="chat-shell">
      <aside class="panel chat-sidebar">
        <div class="section-head">
          <div>
            <h3>${escapeHtml(t("pages.chat.sessions"))}</h3>
            <p>${escapeHtml(t("common.choose_session"))}</p>
          </div>
        </div>
        <div class="chat-create-row">
          <input id="chat-session-name" class="chat-input" type="text" value="${escapeHtml(UI_STATE.chatSessionNameDraft)}" placeholder="${escapeHtml(t("common.session_name"))}">
          <button type="button" class="subtle-button" data-chat-create ${UI_STATE.chatPending.create ? "disabled" : ""}>${escapeHtml(UI_STATE.chatPending.create ? t("common.creating") : t("common.create_session"))}</button>
        </div>
        <div class="chat-session-list">${sessionButtons}</div>
      </aside>
      <section class="panel chat-main">
        <div class="section-head">
          <div>
            <h3>${escapeHtml(t("pages.chat.transcript"))}</h3>
            <p>${escapeHtml(session.session_id || "")}</p>
          </div>
          <div class="pill-row">
            <span class="pill ok">${escapeHtml(`${t("common.message_count")}: ${transcript.length}`)}</span>
            <span class="pill">${escapeHtml(`${t("common.session_revision")}: ${detail?.session_revision || session.session_revision || 0}`)}</span>
            ${pendingSend ? `<span class="pill warning">${escapeHtml(t("common.typing"))}</span>` : ""}
            ${(pendingSwitch || pendingCreate) ? `<span class="pill warning">${escapeHtml(pendingCreate ? t("common.creating") : t("common.loading"))}</span>` : ""}
            ${selectedAssistant ? `<span class="pill">${escapeHtml(`${t("common.selected_turn")}: ${selectedAssistant.message_id}`)}</span>` : ""}
          </div>
        </div>
        <div class="button-row">
          <button type="button" class="subtle-button" data-chat-copy-history ${transcript.length ? "" : "disabled"}>${escapeHtml(t("common.copy_history"))}</button>
          <button type="button" class="subtle-button active" data-chat-apply-pending ${UI_STATE.chatPendingPayload ? "" : "hidden"}>${escapeHtml(UI_STATE.chatPendingLabel || t("common.apply_updates"))}</button>
          <span class="pill ok" data-chat-copy-feedback ${UI_STATE.chatCopyFeedback ? "" : "hidden"}>${escapeHtml(UI_STATE.chatCopyFeedback || "")}</span>
        </div>
        <div class="chat-transcript">${transcriptHtml}</div>
        <div class="chat-composer">
          <textarea id="chat-draft" class="chat-textarea" placeholder="${escapeHtml(t("pages.chat.subtitle"))}">${escapeHtml(UI_STATE.chatDraft)}</textarea>
          <div class="chat-actions">
            <span class="muted">${escapeHtml(session.updated_at ? formatDateTime(session.updated_at) : "")}</span>
            <button type="button" class="subtle-button active" data-chat-send ${pendingSend || pendingCreate ? "disabled" : ""}>${escapeHtml(pendingSend ? t("common.sending") : t("common.send"))}</button>
          </div>
        </div>
      </section>
    </section>
    <section class="chat-debug-grid">
      ${debugCards}
    </section>
  `;
  updateChatLiveIndicators();
}

async function ensureChatSession() {
  const sessionsPayload = await fetchJson("/api/dashboard/chat/sessions");
  const persisted = window.localStorage.getItem("dashboard:chatSessionId");
  const knownIds = new Set((sessionsPayload.sessions || []).map((item) => item.session_id));
  if (!UI_STATE.chatSessionId) {
    UI_STATE.chatSessionId = persisted && knownIds.has(persisted) ? persisted : sessionsPayload.default_session_id;
  }
  if (!knownIds.has(UI_STATE.chatSessionId)) {
    UI_STATE.chatSessionId = sessionsPayload.default_session_id;
  }
  if (UI_STATE.chatSessionId) {
    persistChatSessionId(UI_STATE.chatSessionId);
  }
  return sessionsPayload;
}

async function fetchChatDetail({ sessionId = UI_STATE.chatSessionId, afterRevision = null, waitTimeoutMs = null, signal = null } = {}) {
  const query = new URLSearchParams();
  if (afterRevision !== null && afterRevision !== undefined) {
    query.set("after_revision", String(afterRevision));
  }
  if (waitTimeoutMs !== null && waitTimeoutMs !== undefined) {
    query.set("wait_timeout_ms", String(waitTimeoutMs));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return fetchJson(`/api/dashboard/chat/sessions/${encodeURIComponent(sessionId)}${suffix}`, signal ? { signal } : {});
}

async function refreshChat({ allowDefer = false } = {}) {
  UI_STATE.chatSessionsPayload = await ensureChatSession();
  const cached = getCachedChatDetail(UI_STATE.chatSessionId);
  if (cached) {
    rememberChatPayload(upsertChatSessionDescriptor(cached.session), cached);
    renderChatFromState();
  }
  const detail = await fetchChatDetail({ sessionId: UI_STATE.chatSessionId });
  UI_STATE.chatError = "";
  applyChatSnapshot(upsertChatSessionDescriptor(detail.session), detail, { allowDefer });
}

function stopChatWatchLoop() {
  if (UI_STATE.chatWatchController) {
    UI_STATE.chatWatchController.abort();
    UI_STATE.chatWatchController = null;
  }
  UI_STATE.chatWatchGeneration += 1;
}

function activateChatSession(sessionId, { descriptor = null, loadingState = "loading" } = {}) {
  const fallbackDescriptor = descriptor || getChatSessionDescriptor(sessionId) || {
    session_id: sessionId,
    session_name: sessionId,
    message_count: 0,
    turn_count: 0,
    created_at: null,
    updated_at: null,
    task_status: null,
    waiting_for_user_input: false,
    session_revision: 0,
    last_message_id: null,
  };
  const cached = getCachedChatDetail(sessionId);
  UI_STATE.chatSessionId = sessionId;
  UI_STATE.chatSelectedMessageId = null;
  UI_STATE.chatError = "";
  clearChatPendingPayload();
  persistChatSessionId(sessionId);
  const detail = cached
    ? cached
    : buildChatSessionDetail(fallbackDescriptor, {
        transcript: [],
        session_state: {
          task_status: fallbackDescriptor.task_status,
          waiting_for_user_input: Boolean(fallbackDescriptor.waiting_for_user_input),
        },
        session_revision: fallbackDescriptor.session_revision || 0,
        loading_state: loadingState,
      });
  rememberChatPayload(upsertChatSessionDescriptor(fallbackDescriptor), detail);
  renderChatFromState();
}

async function loadChatSessionDetail(sessionId, { selectionToken = null, allowDefer = false, signal = null } = {}) {
  const detail = await fetchChatDetail({ sessionId, signal });
  const sessionsPayload = upsertChatSessionDescriptor(detail.session);
  if (selectionToken !== null && selectionToken !== UI_STATE.chatSelectionToken) {
    setCachedChatDetail(sessionId, detail);
    return detail;
  }
  if (sessionId !== UI_STATE.chatSessionId) {
    setCachedChatDetail(sessionId, detail);
    UI_STATE.chatSessionsPayload = sessionsPayload;
    renderChatFromState();
    return detail;
  }
  UI_STATE.chatError = "";
  applyChatSnapshot(sessionsPayload, detail, { allowDefer });
  return detail;
}

function selectChatSession(sessionId) {
  const token = UI_STATE.chatSelectionToken + 1;
  UI_STATE.chatSelectionToken = token;
  UI_STATE.chatPending.switch = { sessionId, token };
  activateChatSession(sessionId, {
    descriptor: getChatSessionDescriptor(sessionId),
    loadingState: getCachedChatDetail(sessionId) ? null : "loading",
  });
  stopChatWatchLoop();
  loadChatSessionDetail(sessionId, { selectionToken: token })
    .catch((error) => {
      if (token !== UI_STATE.chatSelectionToken || sessionId !== UI_STATE.chatSessionId) return;
      UI_STATE.chatError = error.message;
      renderChatFromState();
    })
    .finally(() => {
      clearChatPending("switch", token);
      if (sessionId === UI_STATE.chatSessionId) {
        renderChatFromState();
        restartChatWatchLoop();
      }
    });
}

async function watchChatUpdates(generation) {
  while (isChatView() && generation === UI_STATE.chatWatchGeneration) {
    const sessionId = UI_STATE.chatSessionId;
    const activeDetail = getCachedChatDetail(sessionId) || UI_STATE.chatDetail;
    const afterRevision = Number(activeDetail?.session_revision || activeDetail?.session?.session_revision || 0);
    if (!sessionId || isTempChatSessionId(sessionId)) {
      await delay(250);
      continue;
    }
    const controller = new AbortController();
    UI_STATE.chatWatchController = controller;
    try {
      const detail = await fetchChatDetail({
        sessionId,
        afterRevision,
        waitTimeoutMs: CHAT_WAIT_TIMEOUT_MS,
        signal: controller.signal,
      });
      if (generation !== UI_STATE.chatWatchGeneration || sessionId !== UI_STATE.chatSessionId) {
        continue;
      }
      const hadError = Boolean(UI_STATE.chatError);
      UI_STATE.chatError = "";
      if (detail?.has_update && Number(detail?.session_revision || 0) !== Number(afterRevision || 0)) {
        applyChatSnapshot(upsertChatSessionDescriptor(detail.session), detail, { allowDefer: true });
      } else if (hadError) {
        renderChatFromState();
      }
    } catch (error) {
      if (controller.signal.aborted || generation !== UI_STATE.chatWatchGeneration) {
        break;
      }
      if (generation !== UI_STATE.chatWatchGeneration) break;
      UI_STATE.chatError = error.message;
      updateChatLiveIndicators();
      await delay(1500);
    } finally {
      if (UI_STATE.chatWatchController === controller) {
        UI_STATE.chatWatchController = null;
      }
    }
  }
}

function restartChatWatchLoop() {
  if (!isChatView()) return;
  stopChatWatchLoop();
  const generation = UI_STATE.chatWatchGeneration;
  watchChatUpdates(generation).catch(() => {});
}

async function createChatSessionFromDraft() {
  if (UI_STATE.chatPending.create) return;
  const name = String(UI_STATE.chatSessionNameDraft || "").trim() || "default";
  const tempSessionId = buildTempChatSessionId();
  const nowIso = new Date().toISOString();
  const previousSessionId = UI_STATE.chatSessionId;
  const token = UI_STATE.chatSelectionToken + 1;
  UI_STATE.chatSelectionToken = token;
  UI_STATE.chatPending.create = {
    tempSessionId,
    previousSessionId,
    token,
    name,
  };
  UI_STATE.chatError = "";
  UI_STATE.chatSessionNameDraft = "";
  const tempDescriptor = {
    session_id: tempSessionId,
    session_name: name,
    message_count: 0,
    turn_count: 0,
    created_at: nowIso,
    updated_at: nowIso,
    task_status: "creating",
    waiting_for_user_input: false,
    session_revision: 0,
    last_message_id: null,
    pending_state: "creating",
  };
  const tempDetail = buildChatSessionDetail(tempDescriptor, {
    transcript: [],
    session_state: {
      task_status: "creating",
      waiting_for_user_input: false,
    },
    session_revision: 0,
    loading_state: "creating",
  });
  stopChatWatchLoop();
  activateChatSession(tempSessionId, { descriptor: tempDescriptor, loadingState: "creating" });
  rememberChatPayload(upsertChatSessionDescriptor(tempDescriptor), tempDetail);
  renderChatFromState();
  try {
    const payload = await requestJson("/api/dashboard/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    const realSessionId = payload?.session?.session_id;
    if (!realSessionId) {
      throw new Error("Session creation returned no session id.");
    }
    const realDetail = buildChatSessionDetail(payload.session, {
      transcript: [],
      session_state: payload.session_state || {},
      session_revision: payload.session_revision || payload?.session?.session_revision || 0,
      has_update: true,
    });
    UI_STATE.chatDetailCache.delete(tempSessionId);
    setCachedChatDetail(realSessionId, realDetail);
    const nextPayload = upsertChatSessionDescriptor(payload.session, { replaceSessionId: tempSessionId });
    const shouldAdoptRealSession = UI_STATE.chatSessionId === tempSessionId && UI_STATE.chatPending.create?.token === token;
    if (shouldAdoptRealSession) {
      UI_STATE.chatSessionId = realSessionId;
      persistChatSessionId(realSessionId);
      rememberChatPayload(nextPayload, realDetail);
      renderChatFromState();
      loadChatSessionDetail(realSessionId, { selectionToken: token })
        .catch((error) => {
          if (token !== UI_STATE.chatSelectionToken || UI_STATE.chatSessionId !== realSessionId) return;
          UI_STATE.chatError = error.message;
          renderChatFromState();
        })
        .finally(() => restartChatWatchLoop());
    } else {
      UI_STATE.chatSessionsPayload = nextPayload;
      renderChatFromState();
    }
  } catch (error) {
    UI_STATE.chatError = error.message;
    UI_STATE.chatSessionNameDraft = name;
    UI_STATE.chatDetailCache.delete(tempSessionId);
    removeChatSessionDescriptor(tempSessionId);
    if (UI_STATE.chatSessionId === tempSessionId) {
      if (previousSessionId) {
        activateChatSession(previousSessionId, {
          descriptor: getChatSessionDescriptor(previousSessionId) || getCachedChatDetail(previousSessionId)?.session,
          loadingState: getCachedChatDetail(previousSessionId) ? null : "loading",
        });
        loadChatSessionDetail(previousSessionId, { selectionToken: UI_STATE.chatSelectionToken }).catch(() => {});
      } else {
        UI_STATE.chatDetail = null;
      }
      renderChatFromState();
    }
  } finally {
    clearChatPending("create", token);
    renderChatFromState();
    if (!isTempChatSessionId(UI_STATE.chatSessionId)) {
      restartChatWatchLoop();
    }
  }
}

async function sendChatDraft() {
  const text = String(UI_STATE.chatDraft || "").trim();
  if (!text || !UI_STATE.chatSessionId || UI_STATE.chatPending.send || isTempChatSessionId(UI_STATE.chatSessionId)) return;
  const sessionId = UI_STATE.chatSessionId;
  const userMessageId = buildLocalMessageId("user");
  const typingMessageId = buildLocalMessageId("typing");
  const nowIso = new Date().toISOString();
  const token = Date.now();
  UI_STATE.chatPending.send = {
    sessionId,
    token,
    userMessageId,
    typingMessageId,
    draftText: text,
  };
  UI_STATE.chatError = "";
  const baseDetail =
    getCachedChatDetail(sessionId) ||
    UI_STATE.chatDetail ||
    buildChatSessionDetail(getChatSessionDescriptor(sessionId) || { session_id: sessionId, session_name: sessionId }, {});
  const optimisticDetail = ChatState.buildOptimisticSend
    ? ChatState.buildOptimisticSend(baseDetail, {
        text,
        nowIso,
        userMessageId,
        typingMessageId,
      })
    : baseDetail;
  UI_STATE.chatDraft = "";
  rememberChatPayload(upsertChatSessionDescriptor(optimisticDetail.session), optimisticDetail);
  renderChatFromState();
  stopChatWatchLoop();
  try {
    const payload = await requestJson(`/api/dashboard/chat/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    const currentDetail = getCachedChatDetail(sessionId) || optimisticDetail;
    const canonicalDetail = ChatState.reconcileSendSuccess
      ? ChatState.reconcileSendSuccess(currentDetail, payload, {
          userMessageId,
          typingMessageId,
        })
      : currentDetail;
    const nextPayload = upsertChatSessionDescriptor(payload.session || canonicalDetail.session);
    setCachedChatDetail(sessionId, canonicalDetail);
    if (UI_STATE.chatSessionId === sessionId) {
      UI_STATE.chatSelectedMessageId = payload?.messages?.assistant?.message_id || UI_STATE.chatSelectedMessageId;
      rememberChatPayload(nextPayload, canonicalDetail);
      renderChatFromState();
    } else {
      UI_STATE.chatSessionsPayload = nextPayload;
      renderChatFromState();
    }
  } catch (error) {
    UI_STATE.chatError = error.message;
    const currentDetail = getCachedChatDetail(sessionId) || optimisticDetail;
    const failedDetail = ChatState.markSendFailed
      ? ChatState.markSendFailed(currentDetail, {
          userMessageId,
          typingMessageId,
          errorMessage: error.message,
        })
      : currentDetail;
    const nextPayload = upsertChatSessionDescriptor(failedDetail.session);
    setCachedChatDetail(sessionId, failedDetail);
    if (UI_STATE.chatSessionId === sessionId) {
      UI_STATE.chatDraft = text;
      rememberChatPayload(nextPayload, failedDetail);
      renderChatFromState();
      window.setTimeout(focusChatDraftToEnd, 0);
    } else {
      UI_STATE.chatSessionsPayload = nextPayload;
      renderChatFromState();
    }
  } finally {
    clearChatPending("send", token);
    renderChatFromState();
    restartChatWatchLoop();
  }
}

async function refresh() {
  const health = await fetchJson(buildApiPath("/api/dashboard/health"));
  renderMeta(health.build_meta || {}, health.gap_summary || {});

  if (view === "flow") {
    const path = sampleId
      ? `/api/dashboard/samples/${encodeURIComponent(sampleId)}/flow`
      : buildApiPath("/api/dashboard/flow");
    renderFlow(await fetchJson(path));
    return;
  }
  if (view === "chat") {
    await refreshChat();
    return;
  }
  if (view === "growth") {
    renderGrowth(await fetchJson(buildApiPath("/api/dashboard/growth")));
    return;
  }
  if (view === "failures") {
    renderFailures(await fetchJson("/api/dashboard/failures"));
    return;
  }
  if (view === "agency") {
    renderAgency(await fetchJson(buildApiPath("/api/dashboard/agency")));
    return;
  }
  if (view === "sample" && sampleId) {
    renderSample(await fetchJson(`/api/dashboard/samples/${encodeURIComponent(sampleId)}`));
    return;
  }
  renderRuns(await fetchJson(buildApiPath("/api/dashboard/runs")));
}

document.addEventListener("click", (event) => {
  const localeButton = event.target.closest("[data-locale]");
  if (localeButton) {
    setLocale(localeButton.dataset.locale);
    return;
  }
  const sessionButton = event.target.closest("[data-chat-session-id]");
  if (sessionButton) {
    selectChatSession(sessionButton.dataset.chatSessionId);
    return;
  }
  const chatMessageButton = event.target.closest("[data-chat-message-id]");
  if (chatMessageButton) {
    UI_STATE.chatSelectedMessageId = chatMessageButton.dataset.chatMessageId;
    renderChatFromState();
    return;
  }
  const applyPendingButton = event.target.closest("[data-chat-apply-pending]");
  if (applyPendingButton) {
    applyPendingChatUpdate().catch(() => {});
    return;
  }
  const copyHistoryButton = event.target.closest("[data-chat-copy-history]");
  if (copyHistoryButton) {
    const text = buildChatHistoryText(UI_STATE.chatDetail);
    copyText(text)
      .then(() => setChatCopyFeedback(t("common.copied")))
      .catch(() => setChatCopyFeedback(t("common.copy_failed")));
    return;
  }
  const chatCreateButton = event.target.closest("[data-chat-create]");
  if (chatCreateButton) {
    createChatSessionFromDraft().catch(() => {});
    return;
  }
  const chatSendButton = event.target.closest("[data-chat-send]");
  if (chatSendButton) {
    sendChatDraft().catch(() => {});
    return;
  }
  const detailButton = event.target.closest("[data-detail-key]");
  if (detailButton) {
    const key = detailButton.dataset.detailKey;
    if (UI_STATE.detailOpen.has(key)) UI_STATE.detailOpen.delete(key);
    else UI_STATE.detailOpen.add(key);
    refresh().catch(() => {});
    return;
  }
  const artifactButton = event.target.closest("[data-artifact-key]");
  if (artifactButton) {
    UI_STATE.artifactModes.set(artifactButton.dataset.artifactKey, artifactButton.dataset.artifactMode);
    refresh().catch(() => {});
  }
});

document.addEventListener("input", (event) => {
  if (event.target.id === "chat-draft") {
    UI_STATE.chatDraft = event.target.value;
    if (!shouldDeferChatHydration() && UI_STATE.chatPendingPayload) {
      applyPendingChatUpdate().catch(() => {});
    }
  }
  if (event.target.id === "chat-session-name") {
    UI_STATE.chatSessionNameDraft = event.target.value;
  }
});

document.addEventListener("change", (event) => {
  if (event.target.matches("[data-source-view]")) {
    UI_STATE.sourceView = event.target.value === "all" ? "all" : "real";
    window.localStorage.setItem(SOURCE_VIEW_STORAGE_KEY, UI_STATE.sourceView);
    refresh().catch((error) => {
      app.innerHTML = `<section class="panel"><div class="empty">${escapeHtml(error.message)}</div></section>`;
    });
  }
});

document.addEventListener("focusin", (event) => {
  if (event.target.id === "chat-draft") {
    UI_STATE.chatDraftFocused = true;
  }
});

document.addEventListener("focusout", (event) => {
  if (event.target.id === "chat-draft") {
    UI_STATE.chatDraftFocused = false;
    if (!shouldDeferChatHydration() && UI_STATE.chatPendingPayload) {
      applyPendingChatUpdate().catch(() => {});
    }
  }
});

document.addEventListener("keydown", (event) => {
  if (event.target.id === "chat-draft" && event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    sendChatDraft().catch(() => {});
  }
});

async function start() {
  UI_STATE.locale = detectLocale();
  UI_STATE.sourceView = detectSourceView();
  applyChrome();
  if (window.location.pathname === "/") {
    const preferredView = window.localStorage.getItem("dashboard:lastView");
    if (preferredView && VIEW_ROUTES[preferredView]) {
      window.location.replace(VIEW_ROUTES[preferredView]);
      return;
    }
  }
  if (!sampleId && VIEW_ROUTES[view]) {
    window.localStorage.setItem("dashboard:lastView", view);
  }
  try {
    await refresh();
    if (isChatView()) {
      restartChatWatchLoop();
    } else {
      setInterval(refresh, POLL_MS);
    }
  } catch (error) {
    app.innerHTML = `<section class="panel"><div class="empty">Dashboard load failed: ${escapeHtml(error.message)}</div></section>`;
  }
}

start();
