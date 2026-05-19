const assert = require("assert");
const path = require("path");

const ChatState = require(path.resolve(__dirname, "../app/dashboard/static/dashboard_chat_state.js"));

function testOptimisticSendLifecycle() {
  const detail = ChatState.buildSessionDetail(
    {
      session_id: "dashboard:test:default",
      session_name: "default",
      message_count: 2,
      session_revision: 3,
      last_message_id: "msg_00002",
    },
    {
      transcript: [
        {
          message_id: "msg_00001",
          role: "user",
          text: "hello",
          status: "received",
          delivery_kind: "ingress",
          created_at: "2026-04-10T12:00:00+00:00",
        },
        {
          message_id: "msg_00002",
          role: "assistant",
          text: "world",
          status: "chat",
          delivery_kind: "chat",
          created_at: "2026-04-10T12:00:01+00:00",
        },
      ],
      session_state: { task_status: "chat" },
      session_revision: 3,
    },
  );

  const optimistic = ChatState.buildOptimisticSend(detail, {
    text: "ping",
    nowIso: "2026-04-10T12:00:02+00:00",
    userMessageId: "local_user",
    typingMessageId: "local_typing",
  });

  assert.equal(optimistic.transcript.length, 4);
  assert.equal(optimistic.transcript[2].status, "sending");
  assert.equal(optimistic.transcript[3].typing, true);

  const success = ChatState.reconcileSendSuccess(
    optimistic,
    {
      session: {
        session_id: "dashboard:test:default",
        session_name: "default",
        message_count: 4,
        session_revision: 4,
        last_message_id: "msg_00004",
      },
      messages: {
        user: {
          message_id: "msg_00003",
          role: "user",
          text: "ping",
          status: "received",
          delivery_kind: "ingress",
          created_at: "2026-04-10T12:00:02+00:00",
        },
        assistant: {
          message_id: "msg_00004",
          role: "assistant",
          text: "pong",
          status: "chat",
          delivery_kind: "chat",
          created_at: "2026-04-10T12:00:03+00:00",
        },
      },
      debug: { trace_id: "trace_ok" },
      session_state: { task_status: "chat" },
      session_revision: 4,
    },
    {
      userMessageId: "local_user",
      typingMessageId: "local_typing",
    },
  );

  assert.deepEqual(
    success.transcript.map((item) => item.message_id),
    ["msg_00001", "msg_00002", "msg_00003", "msg_00004"],
  );
  assert.equal(success.debug_history.msg_00004.trace_id, "trace_ok");
}

function testFailedSendKeepsVisibleFailure() {
  const optimistic = ChatState.buildOptimisticSend(
    ChatState.buildSessionDetail(
      {
        session_id: "dashboard:test:default",
        session_name: "default",
      },
      { transcript: [], session_state: {} },
    ),
    {
      text: "will fail",
      nowIso: "2026-04-10T12:05:00+00:00",
      userMessageId: "local_user_fail",
      typingMessageId: "local_typing_fail",
    },
  );

  const failed = ChatState.markSendFailed(optimistic, {
    userMessageId: "local_user_fail",
    typingMessageId: "local_typing_fail",
    errorMessage: "provider timeout",
  });

  assert.equal(failed.transcript.length, 1);
  assert.equal(failed.transcript[0].status, "failed");
  assert.equal(failed.transcript[0].local_failed, true);
  assert.equal(failed.transcript[0].error_message, "provider timeout");
}

function testSessionDescriptorUpsertAndReplace() {
  const payload = ChatState.upsertSessionDescriptor(
    {
      default_session_id: "dashboard:test:default",
      sessions: [
        {
          session_id: "dashboard:test:default",
          session_name: "default",
          updated_at: "2026-04-10T12:00:00+00:00",
        },
      ],
    },
    {
      session_id: "dashboard:temp:123",
      session_name: "draft",
      updated_at: "2026-04-10T12:01:00+00:00",
    },
  );

  const replaced = ChatState.upsertSessionDescriptor(
    payload,
    {
      session_id: "dashboard:test:new",
      session_name: "new",
      updated_at: "2026-04-10T12:02:00+00:00",
    },
    { replaceSessionId: "dashboard:temp:123" },
  );

  assert.deepEqual(
    replaced.sessions.map((item) => item.session_id),
    ["dashboard:test:new", "dashboard:test:default"],
  );
}

function makeAssistant() {
  return {
    message_id: "msg_00002",
    role: "assistant",
    text: "world",
    status: "chat",
    delivery_kind: "chat",
    created_at: "2026-04-10T12:00:01+00:00",
  };
}

function makeHappyDebug(overrides = {}) {
  return {
    subject_gate: {
      ingress: { ok: true, reason: "ok" },
      finalize: { ok: true, reason: "stable_subject_path" },
    },
    ingress: {
      runtime_action: "chat",
      interaction_kind: "chat",
      request_mode: "respond",
      parser_source: "semantic_parser",
    },
    proto_self: {
      subject_profile: "seed_v0_2",
      policy_hint: { ask_preferred: false },
      response_tendency: {
        preferred_mode: "respond",
        preferred_tone: "calm",
        suggested_next_step: "continue",
      },
    },
    response_plan: {
      kind: "chat",
      delivery_kind: "chat",
      reply_authority: "model_chat",
      authority_source: "host_runtime",
    },
    output_check: {
      passed: true,
      reason: "accepted",
      applied_authority: "model_chat",
      reply_origin: "chat_mainline",
    },
    delivery: {
      should_send: true,
      delivery_kind: "chat",
      text_preview: "world",
    },
    ...overrides,
  };
}

function testTurnFlowModelHappyPath() {
  const flow = ChatState.buildTurnFlowModel(makeHappyDebug(), makeAssistant(), { task_status: "chat" });

  assert.equal(flow.selected_message_id, "msg_00002");
  assert.equal(flow.turn_status, "pass");
  assert.equal(flow.flow_steps.length, 6);
  assert.deepEqual(
    flow.flow_steps.map((step) => step.id),
    ["subject_gate", "ingress", "proto_self", "response_plan", "output_check", "delivery"],
  );
  assert.equal(flow.headline_key, "overall_headline_pass");
  assert.equal(flow.flow_steps[2].headline_key, "proto_self_headline_pass");
  assert.equal(flow.flow_steps[5].status, "pass");
  assert(flow.key_influences.some((entry) => entry.label === "preferred_mode" && entry.value === "respond"));
}

function testTurnFlowModelHostOnlyWhenSubjectGateFails() {
  const flow = ChatState.buildTurnFlowModel(
    makeHappyDebug({
      subject_gate: { ingress: { ok: false, reason: "intent_gate_rejected" } },
      proto_self: {},
      output_check: {},
      delivery: { should_send: false, delivery_kind: "chat", text_preview: "" },
    }),
    makeAssistant(),
    { task_status: "chat" },
  );

  assert.equal(flow.turn_status, "host_only");
  assert.equal(flow.headline_key, "overall_headline_host_only");
  assert.equal(flow.flow_steps[0].status, "host_only");
  assert.equal(flow.flow_steps[2].status, "host_only");
}

function testTurnFlowModelDegradedWhenHostBlocksSend() {
  const flow = ChatState.buildTurnFlowModel(
    makeHappyDebug({
      output_check: {
        passed: false,
        reason: "intent_gate_blocked",
        applied_authority: "host_guard",
        reply_origin: "host_guard",
      },
      delivery: {
        should_send: false,
        delivery_kind: "chat",
        text_preview: "blocked",
      },
    }),
    makeAssistant(),
    { task_status: "chat" },
  );

  assert.equal(flow.turn_status, "degraded");
  assert.equal(flow.summary_key, "overall_summary_degraded");
  assert.equal(flow.flow_steps[4].status, "degraded");
  assert.equal(flow.flow_steps[5].status, "degraded");
}

function testTurnFlowModelSurvivesMissingProtoSelf() {
  const flow = ChatState.buildTurnFlowModel(
    makeHappyDebug({
      proto_self: undefined,
    }),
    makeAssistant(),
    { task_status: "chat" },
  );

  assert.equal(flow.flow_steps.length, 6);
  assert.equal(flow.flow_steps[2].id, "proto_self");
  assert.equal(flow.flow_steps[2].status, "broken");
  assert.equal(flow.flow_steps[2].headline_key, "proto_self_headline_missing");
}

testOptimisticSendLifecycle();
testFailedSendKeepsVisibleFailure();
testSessionDescriptorUpsertAndReplace();
testTurnFlowModelHappyPath();
testTurnFlowModelHostOnlyWhenSubjectGateFails();
testTurnFlowModelDegradedWhenHostBlocksSend();
testTurnFlowModelSurvivesMissingProtoSelf();
console.log("dashboard_chat_state ok");
