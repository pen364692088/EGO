"""
EgoCore Response Module

提供自然表达层组件：
- Verbalizer: v2 自然表达层
- VerbalizerV3: v3 关系感知 + 风格条件化
- RelationshipContext: 短期关系上下文
- StyleProfile: 风格配置
"""

from app.response.verbalizer import Verbalizer, get_verbalizer, verbalize
from app.response.verbalizer_v3 import VerbalizerV3, create_verbalizer_v3
from app.response.relationship_context import (
    RelationshipContext,
    RelationshipContextManager,
    RelationshipEvent,
    SocialArc,
    get_relationship_context_manager,
)
from app.response.style_profile import (
    StyleProfile,
    StyleDimensions,
    StyleProfileManager,
    get_style_profile_manager,
    get_warm_style,
    get_neutral_style,
    get_repair_style,
    get_task_style,
)
from app.response.question_verbalizer import (
    QuestionVerbalizer,
    ShortQuestionType,
    verbalize_question,
    is_short_question,
)

__all__ = [
    # Verbalizer v2
    "Verbalizer",
    "get_verbalizer",
    "verbalize",
    # Verbalizer v3
    "VerbalizerV3",
    "create_verbalizer_v3",
    # Relationship Context
    "RelationshipContext",
    "RelationshipContextManager",
    "RelationshipEvent",
    "SocialArc",
    "get_relationship_context_manager",
    # Style Profile
    "StyleProfile",
    "StyleDimensions",
    "StyleProfileManager",
    "get_style_profile_manager",
    "get_warm_style",
    "get_neutral_style",
    "get_repair_style",
    "get_task_style",
    # Question Verbalizer (P1-C)
    "QuestionVerbalizer",
    "ShortQuestionType",
    "verbalize_question",
    "is_short_question",
]
