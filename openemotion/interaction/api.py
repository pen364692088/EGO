"""
Interaction API endpoints for OpenEmotion

提供 /interpret 端点供 EgoCore 调用。
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from openemotion.interaction.schema import (
    SubjectInterpretationResult,
    validate_result,
)
from openemotion.interaction.interpretation import (
    interpret_interaction,
    create_fallback_result,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interaction", tags=["interaction"])


@router.post("/interpret")
async def interpret_endpoint(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """
    解释互动事件
    
    方向：EgoCore → OpenEmotion
    作用：返回主体解释、关系语义、appraisal 变化、回应倾向。
    
    Args:
        envelope: InteractionEventEnvelope dict
    
    Returns:
        SubjectInterpretationResult dict
    
    关键边界：
    - 此端点只返回解释，不返回决策
    - 返回的 SubjectInterpretationResult 不包含 should_* 字段
    """
    try:
        # 验证信封
        envelope_id = envelope.get("envelope_id", "unknown")
        schema_version = envelope.get("schema_version", "")
        
        if schema_version != "1.0.0":
            logger.warning(f"Unsupported schema version: {schema_version}")
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported schema version: {schema_version}"
            )
        
        # 执行解释
        result = interpret_interaction(envelope)
        
        # 验证结果
        result_dict = result.to_dict()
        valid, error = validate_result(result_dict)
        
        if not valid:
            logger.error(f"Invalid result: {error}")
            # 返回降级结果而不是失败
            fallback = create_fallback_result(envelope_id)
            return fallback.to_dict()
        
        logger.info(
            f"Interpretation complete: envelope={envelope_id}, "
            f"primary_mode={result.interaction_interpretation.primary_mode}, "
            f"confidence={result.interaction_interpretation.confidence:.2f}"
        )
        
        return result_dict
        
    except Exception as e:
        logger.error(f"Interpretation error: {e}")
        # 返回降级结果而不是失败
        fallback = create_fallback_result(envelope.get("envelope_id", "unknown"))
        return fallback.to_dict()


@router.get("/health")
async def interaction_health():
    """Health check for interaction module"""
    return {
        "status": "ok",
        "module": "interaction",
        "version": "1.0.0"
    }
