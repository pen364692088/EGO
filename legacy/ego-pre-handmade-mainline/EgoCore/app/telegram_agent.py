"""
Telegram Agent - EgoCore Telegram 入口

使用新的 runEmbeddedEgoCoreAgent 作为唯一入口。

版本: v2.0.0
Created: 2026-03-19
"""

import asyncio
import logging
from typing import Optional, Dict, Any

from app.runtime import (
    run_agent,
    create_run_id,
    get_session_manager,
    get_reply_dispatcher,
    get_telegram_adapter,
    set_telegram_bot,
    SessionKey,
    ReplyPayload,
    ReplyType,
)

logger = logging.getLogger(__name__)


async def handle_telegram_message(
    bot,
    update: Dict[str, Any],
) -> Optional[str]:
    """
    处理 Telegram 消息
    
    所有 Telegram 请求必须走 runEmbeddedEgoCoreAgent。
    
    Args:
        bot: Telegram bot 实例
        update: Telegram update 对象
    
    Returns:
        回复文本 (或 None 表示静默)
    """
    # 提取消息信息
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id")
    username = message.get("from", {}).get("username", "unknown")
    text = message.get("text", "")
    message_id = message.get("message_id")
    
    if not text:
        return None
    
    # 构建 session key
    # 格式: telegram:dm:<user_id> 或 telegram:group:<group_id>
    chat_type = message.get("chat", {}).get("type", "private")
    if chat_type == "private":
        session_key = f"telegram:dm:{user_id}"
    else:
        group_id = message.get("chat", {}).get("id")
        session_key = f"telegram:group:{group_id}"
    
    # 设置 bot 实例
    set_telegram_bot(bot)
    
    # 运行 agent
    result = await run_agent(
        prompt=text,
        session_key=session_key,
        user_id=str(user_id),
        channel="telegram",
        sender_name=username,
        message_to=str(chat_id),
    )
    
    # 记录日志
    logger.info(
        f"Telegram: session={session_key} user={user_id} "
        f"status={result.status.value} duration={result.duration_ms}ms"
    )
    
    # 返回回复
    return result.reply_text


async def telegram_webhook_handler(bot, update: Dict[str, Any]) -> None:
    """
    Telegram webhook 处理器
    
    这是 Telegram bot 的正式入口点。
    """
    reply = await handle_telegram_message(bot, update)
    
    if reply:
        # 获取 chat_id
        message = update.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        
        if chat_id:
            await bot.send_message(chat_id=chat_id, text=reply)


class TelegramAgentAdapter:
    """
    Telegram Agent 适配器
    
    将 Telegram 消息转换为 EgoCore 运行请求。
    """
    
    def __init__(self, bot=None):
        self._bot = bot
    
    def set_bot(self, bot) -> None:
        """设置 bot 实例"""
        self._bot = bot
        set_telegram_bot(bot)
    
    async def handle_message(self, update: Dict[str, Any]) -> Optional[str]:
        """处理消息"""
        if not self._bot:
            logger.error("TelegramAgentAdapter: bot not set")
            return None
        
        return await handle_telegram_message(self._bot, update)
    
    async def send_reply(self, chat_id: int, text: str) -> bool:
        """发送回复"""
        if not self._bot:
            return False
        
        try:
            await self._bot.send_message(chat_id=chat_id, text=text)
            return True
        except Exception as e:
            logger.error(f"TelegramAgentAdapter: send failed: {e}")
            return False


# 全局适配器实例
_telegram_adapter: Optional[TelegramAgentAdapter] = None


def get_telegram_agent_adapter() -> TelegramAgentAdapter:
    """获取 Telegram agent 适配器"""
    global _telegram_adapter
    if _telegram_adapter is None:
        _telegram_adapter = TelegramAgentAdapter()
    return _telegram_adapter
