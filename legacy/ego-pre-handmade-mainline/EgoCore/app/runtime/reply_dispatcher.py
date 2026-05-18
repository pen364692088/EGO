"""
ReplyDispatcher - 回复分发器

参考 OpenClaw 的 reply/streaming 层，将回复分发到各 channel。

版本: v2.0.0
Created: 2026-03-19
"""

import asyncio
from typing import Dict, Any, Optional, List, Type
from datetime import datetime, timezone
import logging

from .types import (
    ReplyPayload,
    ReplyType,
    ChannelAdapter,
    NO_REPLY,
    SILENT_REPLY_TOKENS,
)

logger = logging.getLogger(__name__)


class ReplyDispatcher:
    """
    回复分发器
    
    参考 OpenClaw 的 reply dispatcher:
    - 收集 reply payloads
    - 分发到正确的 channel
    - 处理 streaming / partial
    - 支持 NO_REPLY 静默
    """
    
    def __init__(self):
        self._adapters: Dict[str, ChannelAdapter] = {}
        self._default_channel: str = "cli"
    
    def register_adapter(self, adapter: ChannelAdapter) -> None:
        """注册 channel 适配器"""
        self._adapters[adapter.channel_name] = adapter
        logger.info(f"ReplyDispatcher: registered adapter for channel={adapter.channel_name}")
    
    def set_default_channel(self, channel: str) -> None:
        """设置默认 channel"""
        self._default_channel = channel
    
    async def dispatch(
        self,
        payload: ReplyPayload,
        channel: Optional[str] = None,
    ) -> bool:
        """
        分发回复
        
        Args:
            payload: 回复载荷
            channel: 目标 channel (None 使用默认)
        
        Returns:
            是否成功
        """
        # 检查静默回复
        if self._is_silent(payload):
            logger.debug(f"ReplyDispatcher: silent reply, skipping dispatch")
            return True
        
        # 选择 channel
        target_channel = channel or self._default_channel
        adapter = self._adapters.get(target_channel)
        
        if not adapter:
            logger.warning(f"ReplyDispatcher: no adapter for channel={target_channel}")
            return False
        
        # 格式化并发送
        try:
            formatted = adapter.format_for_channel(payload)
            payload.content = formatted
            
            success = await adapter.send_reply(payload)
            
            logger.debug(
                f"ReplyDispatcher: dispatched type={payload.type.value} "
                f"channel={target_channel} success={success}"
            )
            
            return success
            
        except Exception as e:
            logger.error(f"ReplyDispatcher: dispatch failed: {e}")
            return False
    
    async def dispatch_partial(
        self,
        text: str,
        sequence: int,
        run_id: str,
        session_id: str,
        channel: Optional[str] = None,
    ) -> bool:
        """
        分发部分回复 (streaming)
        
        Args:
            text: 部分文本
            sequence: 序号
            run_id: 运行 ID
            session_id: 会话 ID
            channel: 目标 channel
        """
        target_channel = channel or self._default_channel
        adapter = self._adapters.get(target_channel)
        
        if not adapter:
            return False
        
        try:
            return await adapter.send_partial(text, sequence)
        except Exception as e:
            logger.error(f"ReplyDispatcher: partial dispatch failed: {e}")
            return False
    
    def _is_silent(self, payload: ReplyPayload) -> bool:
        """检查是否静默回复"""
        if payload.type == ReplyType.SILENT:
            return True
        
        content = payload.content.strip()
        if content in SILENT_REPLY_TOKENS:
            return True
        
        return False
    
    def get_registered_channels(self) -> List[str]:
        """获取已注册的 channels"""
        return list(self._adapters.keys())


# =============================================================================
# Channel Adapters
# =============================================================================

class CLIAdapter:
    """CLI channel 适配器"""
    
    @property
    def channel_name(self) -> str:
        return "cli"
    
    async def send_reply(self, payload: ReplyPayload) -> bool:
        """发送回复到 CLI"""
        # CLI 直接打印
        print(payload.content)
        return True
    
    async def send_partial(self, text: str, sequence: int) -> bool:
        """发送部分回复"""
        # CLI streaming: 打印到同一行
        print(f"\r[{sequence}] {text}", end="", flush=True)
        return True
    
    async def send_typing(self, is_typing: bool) -> bool:
        """发送打字状态"""
        # CLI 不需要打字状态
        return True
    
    def format_for_channel(self, payload: ReplyPayload) -> str:
        """格式化回复"""
        # CLI 支持原始 markdown
        return payload.content


class TelegramAdapter:
    """Telegram channel 适配器"""
    
    def __init__(self, bot_instance=None):
        self._bot = bot_instance
    
    @property
    def channel_name(self) -> str:
        return "telegram"
    
    def set_bot(self, bot_instance) -> None:
        """设置 bot 实例"""
        self._bot = bot_instance
    
    async def send_reply(self, payload: ReplyPayload) -> bool:
        """发送回复到 Telegram"""
        if not self._bot:
            logger.warning("TelegramAdapter: bot not set")
            return False
        
        # 从 metadata 获取目标
        chat_id = payload.metadata.get("chat_id")
        if not chat_id:
            logger.warning("TelegramAdapter: no chat_id in metadata")
            return False
        
        try:
            # 发送消息
            # 对于 MARKDOWN 类型，先 escape 特殊字符
            if payload.type == ReplyType.MARKDOWN:
                from telegram.helpers import escape_markdown
                escaped_content = escape_markdown(payload.content, version=1)
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=escaped_content,
                    parse_mode="Markdown",
                )
            else:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=payload.content,
                )
            return True
        except Exception as e:
            logger.error(f"TelegramAdapter: send failed: {e}")
            # Fallback to plain text
            try:
                await self._bot.send_message(chat_id=chat_id, text=payload.content)
                return True
            except Exception as e2:
                logger.error(f"TelegramAdapter: plain text send failed: {e2}")
                # 最后尝试截断
                if len(payload.content) > 4000:
                    try:
                        truncated = payload.content[:4000] + "\n... (已截断)"
                        await self._bot.send_message(chat_id=chat_id, text=truncated)
                        return True
                    except Exception as e3:
                        logger.error(f"TelegramAdapter: truncated send failed: {e3}")
            return False
    
    async def send_partial(self, text: str, sequence: int) -> bool:
        """发送部分回复"""
        # Telegram 不支持真正的 streaming
        # 可以选择定期编辑消息
        return True
    
    async def send_typing(self, is_typing: bool) -> bool:
        """发送打字状态"""
        if not self._bot:
            return False
        
        chat_id = self._current_chat_id
        if not chat_id:
            return False
        
        try:
            if is_typing:
                await self._bot.send_chat_action(chat_id, "typing")
            return True
        except Exception:
            return False
    
    def format_for_channel(self, payload: ReplyPayload) -> str:
        """格式化回复 (Telegram Markdown)"""
        content = payload.content
        
        # 截断过长的回复
        if len(content) > 4096:
            content = content[:4090] + "..."
        
        return content


# =============================================================================
# 全局实例
# =============================================================================

_dispatcher: Optional[ReplyDispatcher] = None
_cli_adapter: Optional[CLIAdapter] = None
_telegram_adapter: Optional[TelegramAdapter] = None


def get_reply_dispatcher() -> ReplyDispatcher:
    """获取全局回复分发器"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = ReplyDispatcher()
        # 注册默认适配器
        _dispatcher.register_adapter(get_cli_adapter())
    return _dispatcher


def get_cli_adapter() -> CLIAdapter:
    """获取 CLI 适配器"""
    global _cli_adapter
    if _cli_adapter is None:
        _cli_adapter = CLIAdapter()
    return _cli_adapter


def get_telegram_adapter() -> TelegramAdapter:
    """获取 Telegram 适配器"""
    global _telegram_adapter
    if _telegram_adapter is None:
        _telegram_adapter = TelegramAdapter()
    return _telegram_adapter


def set_telegram_bot(bot_instance) -> None:
    """设置 Telegram bot 实例"""
    adapter = get_telegram_adapter()
    adapter.set_bot(bot_instance)
    get_reply_dispatcher().register_adapter(adapter)
