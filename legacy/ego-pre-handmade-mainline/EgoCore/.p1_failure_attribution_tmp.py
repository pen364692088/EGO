
import asyncio
import tempfile
from pathlib import Path
from app.runtime_v2.loop import RuntimeV2Loop
from app.runtime_v2.action_protocol import RuntimeV2Action

async def main():
    loop = RuntimeV2Loop()
    target = Path(tempfile.gettempdir()) / 'p1_loop_debug.html'
    target.write_text('background: modern', encoding='utf-8')
    actions = iter([
        RuntimeV2Action.from_model_output('{"type":"plan","goal":"改配色","steps":["修改文件","验证结果"]}'),
        RuntimeV2Action.from_model_output('{"type":"act","tool":"file","input":{"operation":"read","path":"' + str(target).replace('\\','\\\\') + '"}}'),
        RuntimeV2Action.from_model_output('{"type":"complete","summary":"已完成","verification":{"target":"' + str(target).replace('\\','\\\\') + '","expected":"modern"}}'),
    ])
    async def fake_decide(_state):
        return next(actions)
    async def fake_execute(_tool, _tool_input):
        return {"success": True, "tool": "file", "stdout": "background: modern", "stderr": "", "exit_code": 0, "metadata": {}}
    loop._decide = fake_decide
    loop.tool_broker.execute = fake_execute
    result = await loop.run_turn_typed('session:test', '请修改 hello.html 配色')
    state = loop.get_state('session:test')
    print('RESULT_STATUS', result.status)
    print('RESULT_REPLY', result.reply_text)
    print('LAST_VERIFICATION', state.last_verification_result)
    print('LAST_TOOL_RESULT', state.last_tool_result)
    print('TASK_STATUS', state.task_status)
    print('CURRENT_STEP', state.current_step)
    print('HISTORY_TAIL', state.history[-5:])
    print('TARGET_EXISTS', target.exists())
    print('TARGET_CONTENT', target.read_text(encoding='utf-8'))

asyncio.run(main())
