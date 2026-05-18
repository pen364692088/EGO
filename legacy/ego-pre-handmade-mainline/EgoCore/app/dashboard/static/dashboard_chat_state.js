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
    reconcileSendSuccess,
    markSendFailed,
    upsertSessionDescriptor,
    removeSessionDescriptor,
  };
});
