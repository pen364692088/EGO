
import tempfile
from pathlib import Path
from app.runtime_v2.action_protocol import RuntimeV2Action

target = Path(tempfile.gettempdir()) / 'pytest-of-LEO' / 'pytest-1' / 'test_runtime_v2_loop_runs_plan0' / 'hello.html'
s = '{"type":"act","tool":"file","input":{"operation":"read","path":"' + str(target) + '"}}'
a = RuntimeV2Action.from_model_output(s)
print('TARGET', str(target))
print('ACTION_TYPE', a.type)
print('RAW', a.raw)

s2 = '{"type":"complete","summary":"已完成","verification":{"target":"' + str(target) + '","expected":"modern"}}'
a2 = RuntimeV2Action.from_model_output(s2)
print('COMPLETE_TYPE', a2.type)
print('COMPLETE_RAW', a2.raw)
