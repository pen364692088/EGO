(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.DashboardChatState = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function clone(value) {
    if (value === null || value === undefined) return value;
    return JSON.parse(JSON.stringify(value));
  }

  function hasContent(value) {
    if (value === null || value === undefined) return false;
    if (typeof value === "string") return value.trim() !== "";
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === "object") return Object.keys(value).length > 0;
    return true;
  }

  function compactValue(value) {
    if (value === null || value === undefined) return null;
    if (typeof value === "string") return value.trim() || null;
    if (typeof value === "number" || typeof value === "boolean") return String(value);
    if (Array.isArray(value)) return value.length ? JSON.stringify(value) : null;
    if (typeof value === "object") return Object.keys(value).length ? JSON.stringify(value) : null;
    return String(value);
  }

  function buildMetric(label, value) {
    const compact = compactValue(value);
    if (compact === null) return null;
    return { label: String(label || ""), value: compact };
  }

  function buildStep(id, status, headline, summary, metrics, options) {
    const config = options && typeof options === "object" ? options : {};
    return {
      id: String(id || ""),
      status: String(status || "broken"),
      headline: String(headline || "unknown"),
      summary: String(summary || ""),
      headline_key: config.headline_key || null,
      summary_key: config.summary_key || null,
      metrics: (Array.isArray(metrics) ? metrics : []).filter(Boolean).slice(0, 3),
    };
  }

  function computeTurnStatus(steps) {
    const safeSteps = Array.isArray(steps) ? steps : [];
    if (safeSteps.some((step) => step && step.status === "host_only")) return "host_only";
    if (safeSteps.some((step) => step && step.status === "broken")) return "broken";
    if (safeSteps.some((step) => step && step.status === "degraded")) return "degraded";
    return "pass";
  }

  function buildTurnFlowModel(selectedDebug, selectedAssistant, sessionState) {
    const debug = selectedDebug && typeof selectedDebug === "object" ? selectedDebug : null;
    const assistant = selectedAssistant && typeof selectedAssistant === "object" ? selectedAssistant : null;
    const state = sessionState && typeof sessionState === "object" ? sessionState : {};

    if (!assistant || assistant.role !== "assistant") {
      return null;
    }

    if (!debug) {
      return {
        headline: "Assistant turn selected",
        summary: "Select an assistant turn with debug data to inspect the runtime path.",
        selected_message_id: String(assistant.message_id || ""),
        turn_status: "broken",
        flow_steps: [],
        key_influences: [],
      };
    }

    const subjectGate = debug.subject_gate && typeof debug.subject_gate === "object" ? debug.subject_gate : {};
    const ingressGate = subjectGate.ingress && typeof subjectGate.ingress === "object" ? subjectGate.ingress : {};
    const finalizeGate = subjectGate.finalize && typeof subjectGate.finalize === "object" ? subjectGate.finalize : {};
    const ingress = debug.ingress && typeof debug.ingress === "object" ? debug.ingress : {};
    const protoSelf = debug.proto_self && typeof debug.proto_self === "object" ? debug.proto_self : {};
    const responsePlan = debug.response_plan && typeof debug.response_plan === "object" ? debug.response_plan : {};
    const outputCheck = debug.output_check && typeof debug.output_check === "object" ? debug.output_check : {};
    const delivery = debug.delivery && typeof debug.delivery === "object" ? debug.delivery : {};
    const protoPolicyHint = protoSelf.policy_hint && typeof protoSelf.policy_hint === "object" ? protoSelf.policy_hint : {};
    const protoResponseTendency =
      protoSelf.response_tendency && typeof protoSelf.response_tendency === "object" ? protoSelf.response_tendency : {};

    const ingressOk = ingressGate.ok === true;
    const ingressFailed = ingressGate.ok === false;
    const finalizePresent = Object.prototype.hasOwnProperty.call(subjectGate, "finalize");
    const finalizeOk = finalizePresent ? finalizeGate.ok === true : null;
    const finalizeFailed = finalizePresent && finalizeGate.ok === false;
    const protoSelfPresent =
      hasContent(protoSelf.subject_profile) ||
      hasContent(protoPolicyHint) ||
      hasContent(protoResponseTendency) ||
      hasContent(protoSelf.candidate_actions);
    const outputPassed = outputCheck.passed === true;
    const outputFailed = outputCheck.passed === false;
    const shouldSend = delivery.should_send === true;
    const sendBlocked = delivery.should_send === false;

    const subjectGateStep = buildStep(
      "subject_gate",
      ingressFailed ? "host_only" : finalizeFailed ? "degraded" : ingressOk ? "pass" : "broken",
      ingressFailed
        ? "Ingress stopped before subject processing"
        : finalizeFailed
          ? "Subject finalize blocked downstream delivery"
          : ingressOk
            ? "Subject gate admitted this turn"
            : "Subject gate evidence is missing",
      ingressFailed
        ? "The host path stopped this turn before the subject chain took ownership."
        : finalizeFailed
          ? "Ingress passed, but finalize did not keep the turn on the subject-backed path."
          : ingressOk
            ? "This turn passed ingress and remained eligible for subject-guided handling."
            : "The selected debug payload does not expose a complete subject gate verdict.",
      [
        buildMetric("ingress_ok", ingressGate.ok),
        buildMetric("ingress_reason", ingressGate.reason),
        buildMetric("finalize_ok", finalizePresent ? finalizeGate.ok : null),
      ],
      {
        headline_key: ingressFailed
          ? "subject_gate_headline_host_only"
          : finalizeFailed
            ? "subject_gate_headline_degraded"
            : ingressOk
              ? "subject_gate_headline_pass"
              : "subject_gate_headline_missing",
        summary_key: ingressFailed
          ? "subject_gate_summary_host_only"
          : finalizeFailed
            ? "subject_gate_summary_degraded"
            : ingressOk
              ? "subject_gate_summary_pass"
              : "subject_gate_summary_missing",
      },
    );

    const ingressStep = buildStep(
      "ingress",
      hasContent(ingress.runtime_action) || hasContent(ingress.interaction_kind) ? "pass" : "broken",
      hasContent(ingress.runtime_action) || hasContent(ingress.interaction_kind)
        ? "Ingress intent was normalized into runtime fields"
        : "Ingress normalization details are missing",
      hasContent(ingress.runtime_action) || hasContent(ingress.interaction_kind)
        ? "The host parser resolved this turn into a concrete runtime shape before subject processing."
        : "No runtime_action or interaction_kind was recorded for the selected turn.",
      [
        buildMetric("runtime_action", ingress.runtime_action),
        buildMetric("interaction_kind", ingress.interaction_kind),
        buildMetric("parser_source", ingress.parser_source || ingress.request_mode),
      ],
      {
        headline_key:
          hasContent(ingress.runtime_action) || hasContent(ingress.interaction_kind)
            ? "ingress_headline_pass"
            : "ingress_headline_missing",
        summary_key:
          hasContent(ingress.runtime_action) || hasContent(ingress.interaction_kind)
            ? "ingress_summary_pass"
            : "ingress_summary_missing",
      },
    );

    const protoSelfStep = buildStep(
      "proto_self",
      protoSelfPresent ? "pass" : ingressFailed ? "host_only" : "broken",
      protoSelfPresent
        ? "Proto-Self emitted bounded guidance"
        : ingressFailed
          ? "Proto-Self was skipped because ingress never reached the subject path"
          : "Proto-Self guidance is missing",
      protoSelfPresent
        ? "The subject layer produced bounded policy and tendency hints for this turn."
        : ingressFailed
          ? "Without subject ingress, there is no proto-self layer to summarize."
          : "No subject profile, policy hint, tendency, or candidate actions were captured.",
      [
        buildMetric("subject_profile", protoSelf.subject_profile),
        buildMetric("preferred_mode", protoResponseTendency.preferred_mode),
        buildMetric("ask_preferred", protoPolicyHint.ask_preferred),
      ],
      {
        headline_key: protoSelfPresent
          ? "proto_self_headline_pass"
          : ingressFailed
            ? "proto_self_headline_host_only"
            : "proto_self_headline_missing",
        summary_key: protoSelfPresent
          ? "proto_self_summary_pass"
          : ingressFailed
            ? "proto_self_summary_host_only"
            : "proto_self_summary_missing",
      },
    );

    const responsePlanStep = buildStep(
      "response_plan",
      hasContent(responsePlan.kind) || hasContent(responsePlan.delivery_kind) || hasContent(responsePlan.reply_authority)
        ? "pass"
        : "broken",
      hasContent(responsePlan.reply_authority)
        ? "Host response plan kept explicit reply authority"
        : "Response plan is incomplete",
      hasContent(responsePlan.reply_authority)
        ? "The host assembled a delivery plan after considering subject guidance."
        : "No stable response-plan contract was recorded for the selected turn.",
      [
        buildMetric("kind", responsePlan.kind),
        buildMetric("reply_authority", responsePlan.reply_authority),
        buildMetric("delivery_kind", responsePlan.delivery_kind),
      ],
      {
        headline_key: hasContent(responsePlan.reply_authority)
          ? "response_plan_headline_pass"
          : "response_plan_headline_missing",
        summary_key: hasContent(responsePlan.reply_authority)
          ? "response_plan_summary_pass"
          : "response_plan_summary_missing",
      },
    );

    const outputCheckStep = buildStep(
      "output_check",
      outputPassed ? "pass" : outputFailed ? "degraded" : "broken",
      outputPassed
        ? "Output checks accepted the reply"
        : outputFailed
          ? "Output checks intercepted or degraded the reply"
          : "Output-check verdict is missing",
      outputPassed
        ? "The generated reply survived host-side output checks."
        : outputFailed
          ? "The host kept authority and changed or blocked the reply at the output-check stage."
          : "No explicit output-check pass/fail verdict was recorded.",
      [
        buildMetric("passed", outputCheck.passed),
        buildMetric("reason", outputCheck.reason),
        buildMetric("reply_origin", outputCheck.reply_origin || outputCheck.applied_authority),
      ],
      {
        headline_key: outputPassed
          ? "output_check_headline_pass"
          : outputFailed
            ? "output_check_headline_degraded"
            : "output_check_headline_missing",
        summary_key: outputPassed
          ? "output_check_summary_pass"
          : outputFailed
            ? "output_check_summary_degraded"
            : "output_check_summary_missing",
      },
    );

    const deliveryStep = buildStep(
      "delivery",
      shouldSend ? "pass" : sendBlocked ? "degraded" : "broken",
      shouldSend
        ? "Local delivery completed for this turn"
        : sendBlocked
          ? "The turn stopped before final delivery"
          : "Delivery state is missing",
      shouldSend
        ? "The final local transport step emitted an assistant reply."
        : sendBlocked
          ? "The host retained control and did not send a final assistant reply."
          : "No delivery verdict or final send decision was recorded.",
      [
        buildMetric("should_send", delivery.should_send),
        buildMetric("delivery_kind", delivery.delivery_kind),
        buildMetric("text_preview", delivery.text_preview),
      ],
      {
        headline_key: shouldSend
          ? "delivery_headline_pass"
          : sendBlocked
            ? "delivery_headline_degraded"
            : "delivery_headline_missing",
        summary_key: shouldSend
          ? "delivery_summary_pass"
          : sendBlocked
            ? "delivery_summary_degraded"
            : "delivery_summary_missing",
      },
    );

    const flowSteps = [
      subjectGateStep,
      ingressStep,
      protoSelfStep,
      responsePlanStep,
      outputCheckStep,
      deliveryStep,
    ];

    const keyInfluences = [
      buildMetric("preferred_mode", protoResponseTendency.preferred_mode),
      buildMetric("preferred_tone", protoResponseTendency.preferred_tone),
      buildMetric("suggested_next_step", protoResponseTendency.suggested_next_step),
      buildMetric("ask_preferred", protoPolicyHint.ask_preferred),
      buildMetric("reply_authority", responsePlan.reply_authority),
      buildMetric("reply_origin", outputCheck.reply_origin || responsePlan.authority_source),
      buildMetric("intercept_reason", outputCheck.reason || outputCheck.intent_gate_reason),
    ].filter(Boolean);

    const turnStatus = computeTurnStatus(flowSteps);
    let headline = "Turn reached a bounded chat reply path";
    let summary =
      "The selected assistant turn passed subject ingress, produced bounded guidance, stayed under host reply authority, and reached local delivery.";
    if (turnStatus === "host_only") {
      headline = "Turn stopped before subject processing";
      summary = "The selected turn stayed on the host-only path and never produced proto-self guidance.";
    } else if (turnStatus === "broken") {
      headline = "Turn is missing part of the runtime contract";
      summary = "The selected debug payload does not contain a complete path from subject gate to final delivery.";
    } else if (turnStatus === "degraded") {
      headline = "Turn entered the mainline but was held or degraded by the host";
      summary = "The subject path ran, but host-side checks or delivery decisions prevented a clean final send.";
    }

    return {
      headline,
      summary,
      headline_key:
        turnStatus === "host_only"
          ? "overall_headline_host_only"
          : turnStatus === "broken"
            ? "overall_headline_broken"
            : turnStatus === "degraded"
              ? "overall_headline_degraded"
              : "overall_headline_pass",
      summary_key:
        turnStatus === "host_only"
          ? "overall_summary_host_only"
          : turnStatus === "broken"
            ? "overall_summary_broken"
            : turnStatus === "degraded"
              ? "overall_summary_degraded"
              : "overall_summary_pass",
      selected_message_id: String(assistant.message_id || ""),
      turn_status: turnStatus,
      flow_steps: flowSteps,
      key_influences: keyInfluences,
      flags: {
        ingress_ok: ingressOk,
        finalize_ok: finalizeOk,
        proto_self_present: protoSelfPresent,
        output_check_passed: outputPassed,
        delivery_sent: shouldSend,
        reply_authority: responsePlan.reply_authority || null,
        task_status: state.task_status || null,
      },
    };
  }

  function normalizeSessionDescriptor(session) {
    const source = session && typeof session === "object" ? session : {};
    return {
      session_id: String(source.session_id || ""),
      session_name: String(source.session_name || "default"),
      message_count: Number(source.message_count || 0),
      turn_count: Number(source.turn_count || 0),
      created_at: source.created_at || null,
      updated_at: source.updated_at || null,
      task_status: source.task_status || null,
      waiting_for_user_input: Boolean(source.waiting_for_user_input),
      session_revision: Number(source.session_revision || 0),
      last_message_id: source.last_message_id || null,
      pending_state: source.pending_state || null,
    };
  }

  function buildSessionDetail(session, options) {
    const descriptor = normalizeSessionDescriptor(session);
    const extras = options && typeof options === "object" ? options : {};
    return {
      session: descriptor,
      transcript: clone(extras.transcript || []),
      last_debug: clone(extras.last_debug || null),
      debug_history: clone(extras.debug_history || {}),
      session_state: clone(extras.session_state || {}),
      session_revision: Number(
        extras.session_revision !== undefined ? extras.session_revision : descriptor.session_revision || 0,
      ),
      has_update: Boolean(extras.has_update),
      loading_state: extras.loading_state || null,
    };
  }

  function upsertSessionDescriptor(payload, descriptor, options) {
    const base = payload && typeof payload === "object" ? payload : {};
    const nextDescriptor = normalizeSessionDescriptor(descriptor);
    const replaceSessionId = options && options.replaceSessionId ? String(options.replaceSessionId) : null;
    const sessions = Array.isArray(base.sessions) ? base.sessions.map(normalizeSessionDescriptor) : [];
    const kept = sessions.filter((item) => item.session_id !== nextDescriptor.session_id && item.session_id !== replaceSessionId);
    const nextSessions = [nextDescriptor, ...kept].sort((left, right) => {
      const rightTs = Date.parse(right.updated_at || "") || 0;
      const leftTs = Date.parse(left.updated_at || "") || 0;
      if (rightTs !== leftTs) return rightTs - leftTs;
      return String(left.session_id).localeCompare(String(right.session_id));
    });
    return {
      default_session_id: base.default_session_id || nextDescriptor.session_id,
      sessions: nextSessions,
    };
  }

  function removeSessionDescriptor(payload, sessionId) {
    const base = payload && typeof payload === "object" ? payload : {};
    const targetId = String(sessionId || "");
    const nextSessions = (Array.isArray(base.sessions) ? base.sessions : [])
      .map(normalizeSessionDescriptor)
      .filter((item) => item.session_id !== targetId);
    return {
      default_session_id: base.default_session_id,
      sessions: nextSessions,
    };
  }

  function buildOptimisticSend(detail, options) {
    const base = clone(detail || {});
    const transcript = Array.isArray(base.transcript) ? base.transcript.slice() : [];
    const session = normalizeSessionDescriptor(base.session || {});
    const nowIso = options.nowIso;
    const userMessage = {
      message_id: options.userMessageId,
      role: "user",
      text: String(options.text || ""),
      status: "sending",
      delivery_kind: "ingress",
      created_at: nowIso,
      optimistic: true,
    };
    const typingMessage = {
      message_id: options.typingMessageId,
      role: "assistant",
      text: "",
      status: "typing",
      delivery_kind: "chat",
      created_at: nowIso,
      optimistic: true,
      typing: true,
    };
    transcript.push(userMessage, typingMessage);
    session.message_count = transcript.length;
    session.updated_at = nowIso;
    session.last_message_id = typingMessage.message_id;
    return {
      session,
      transcript,
      last_debug: clone(base.last_debug || null),
      debug_history: clone(base.debug_history || {}),
      session_state: clone(base.session_state || {}),
      session_revision: Number(base.session_revision || session.session_revision || 0),
      has_update: true,
      loading_state: null,
    };
  }

  function reconcileSendSuccess(detail, payload, options) {
    const base = clone(detail || {});
    const session = normalizeSessionDescriptor((payload && payload.session) || base.session || {});
    const transcript = (Array.isArray(base.transcript) ? base.transcript : []).filter(
      (message) => message.message_id !== options.userMessageId && message.message_id !== options.typingMessageId,
    );
    const userMessage = payload && payload.messages ? payload.messages.user : null;
    const assistantMessage = payload && payload.messages ? payload.messages.assistant : null;
    if (userMessage) transcript.push(clone(userMessage));
    if (assistantMessage) transcript.push(clone(assistantMessage));
    session.message_count = transcript.length;
    session.last_message_id = session.last_message_id || (assistantMessage && assistantMessage.message_id) || null;
    const debugHistory = clone(base.debug_history || {});
    if (assistantMessage && payload && payload.debug) {
      debugHistory[assistantMessage.message_id] = clone(payload.debug);
    }
    return {
      session,
      transcript,
      last_debug: clone((payload && payload.debug) || base.last_debug || null),
      debug_history: debugHistory,
      session_state: clone((payload && payload.session_state) || base.session_state || {}),
      session_revision: Number(
        (payload && payload.session_revision) || session.session_revision || base.session_revision || 0,
      ),
      has_update: true,
      loading_state: null,
    };
  }

  function markSendFailed(detail, options) {
    const base = clone(detail || {});
    const transcript = (Array.isArray(base.transcript) ? base.transcript : []).map((message) => {
      if (message.message_id === options.typingMessageId) {
        return null;
      }
      if (message.message_id === options.userMessageId) {
        return {
          ...message,
          optimistic: false,
          local_failed: true,
          status: "failed",
          error_message: String(options.errorMessage || ""),
        };
      }
      return message;
    }).filter(Boolean);
    const session = normalizeSessionDescriptor(base.session || {});
    session.message_count = transcript.length;
    session.last_message_id = transcript.length ? transcript[transcript.length - 1].message_id : null;
    return {
      session,
      transcript,
      last_debug: clone(base.last_debug || null),
      debug_history: clone(base.debug_history || {}),
      session_state: clone(base.session_state || {}),
      session_revision: Number(base.session_revision || session.session_revision || 0),
      has_update: true,
      loading_state: null,
    };
  }

  return {
    buildSessionDetail,
    buildOptimisticSend,
    buildTurnFlowModel,
    reconcileSendSuccess,
    markSendFailed,
    upsertSessionDescriptor,
    removeSessionDescriptor,
  };
});
