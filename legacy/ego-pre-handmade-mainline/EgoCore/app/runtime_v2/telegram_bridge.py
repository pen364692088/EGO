from __future__ import annotations

from app.telegram_runtime_bridge import (
    FILE_TYPE_PATTERNS,
    IntentInference,
    TelegramDeliveryAction,
    TelegramIngressDecision,
    TelegramPreRuntimeAction,
    TelegramRuntimeBridge,
    build_suggestion_response,
    build_suggestion_response_from_intent,
    extract_filename_from_text,
    infer_intent,
    infer_intent_from_filename,
)


class RuntimeV2TelegramBridge(TelegramRuntimeBridge):
    """Compatibility wrapper for legacy runtime_v2 imports."""
