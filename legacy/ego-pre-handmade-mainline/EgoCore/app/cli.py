"""
CLI Agent - EgoCore CLI 入口

使用新的 runEmbeddedEgoCoreAgent 作为唯一入口。

版本: v2.0.0
Created: 2026-03-19
"""

import asyncio
import sys
from typing import Optional

from app.runtime import (
    run_agent,
    run_agent_sync,
    create_run_id,
    get_session_manager,
    get_reply_dispatcher,
    get_cli_adapter,
    SessionKey,
)


async def cli_main(
    prompt: str,
    session_key: Optional[str] = None,
) -> None:
    """
    CLI 主入口
    
    所有 CLI 请求必须走 runEmbeddedEgoCoreAgent。
    """
    # 解析 session key
    if not session_key:
        session_key = "cli:dm:default"
    
    session_manager = get_session_manager()
    session = await session_manager.get_or_create(session_key, "cli")
    
    print(f"[Session: {session.session_id}]")
    print(f"[Turn: {session.turn_index + 1}]")
    print()
    
    # 运行 agent
    result = await run_agent(
        prompt=prompt,
        session_key=session_key,
        user_id="cli_user",
        channel="cli",
    )
    
    # 输出结果
    if result.reply_text:
        print(result.reply_text)
    else:
        print("(silent)")
    
    print()
    print(f"[Status: {result.status.value}] [Duration: {result.duration_ms}ms]")


def cli_entry():
    """CLI 入口点"""
    if len(sys.argv) < 2:
        print("Usage: python -m app.cli \"your message\"")
        print("       python -m app.cli \"your message\" --session <session_key>")
        sys.exit(1)
    
    prompt = sys.argv[1]
    session_key = None
    
    if "--session" in sys.argv:
        idx = sys.argv.index("--session")
        if idx + 1 < len(sys.argv):
            session_key = sys.argv[idx + 1]
    
    asyncio.run(cli_main(prompt, session_key))


if __name__ == "__main__":
    cli_entry()
