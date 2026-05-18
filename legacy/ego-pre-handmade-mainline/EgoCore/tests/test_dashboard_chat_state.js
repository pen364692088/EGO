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

testOptimisticSendLifecycle();
testFailedSendKeepsVisibleFailure();
testSessionDescriptorUpsertAndReplace();
console.log("dashboard_chat_state ok");
