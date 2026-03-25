"""
MVP-6.1 D3: High-Impact Gating Tests

Tests for double-key betrayal gating:
- Ledger key + Violation key must both be satisfied
- Partial evidence triggers clarification path
- Trace distinguishes high_impact_candidate vs high_impact_event
- Thresholds are tunable via auto-tune parameters
"""
import pytest
import asyncio
import tempfile
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional

# Import the module under test
from emotiond.high_impact_gating import (
    HighImpactGatingEngine,
    HighImpactGatingConfig,
    DoubleKeyResult,
    LedgerKeyEvidence,
    ViolationKeyEvidence,
    GatingResult,
    HighImpactType,
    create_high_impact_trace,
    process_high_impact_event,
    get_gating_engine,
    reset_gating_engine,
    refresh_gating_config,
)
from emotiond.ledger import (
    Promise,
    PromiseLedger,
    get_ledger,
    init_ledger,
    detect_violation_in_text,
    generate_promise_id,
)
from emotiond import config


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(autouse=True)
def reset_engine():
    """Reset gating engine before each test."""
    reset_gating_engine()
    yield
    reset_gating_engine()


@pytest.fixture
def gating_config():
    """Create a test gating config."""
    cfg = HighImpactGatingConfig()
    cfg.LEDGER_CONFIDENCE_MIN = 0.5
    cfg.VIOLATION_SEVERITY_MIN = 0.6
    return cfg


@pytest.fixture
def engine(gating_config):
    """Create a test gating engine."""
    return HighImpactGatingEngine(gating_config)


async def init_test_db(db_path: str):
    """Initialize test database with all required tables."""
    import aiosqlite
    
    async with aiosqlite.connect(db_path) as db:
        # Create promises table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promises (
                promise_id TEXT PRIMARY KEY,
                promiser TEXT NOT NULL,
                promisee TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL,
                deadline REAL,
                conditions TEXT,
                confidence REAL DEFAULT 0.5,
                evidence TEXT,
                status TEXT DEFAULT 'active',
                fulfilled_at REAL,
                broken_at REAL,
                broken_evidence TEXT
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_promise_status ON promises(status)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_promise_promisee ON promises(promisee)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_promise_promiser ON promises(promiser)
        """)
        await db.commit()


# ============================================================================
# Test Class 1: Ledger Key Validation
# ============================================================================

class TestLedgerKey:
    """Tests for Ledger Key (Key 1) validation."""
    
    def test_ledger_key_valid_with_high_confidence(self):
        """Ledger key is valid when confidence >= threshold."""
        key = LedgerKeyEvidence(
            promise_id="test_123",
            content="I will help you",
            confidence=0.8,
            created_at=1234567890.0
        )
        assert key.is_valid is True
    
    def test_ledger_key_invalid_with_low_confidence(self):
        """Ledger key is invalid when confidence < threshold."""
        key = LedgerKeyEvidence(
            promise_id="test_123",
            content="I will help you",
            confidence=0.3,
            created_at=1234567890.0
        )
        assert key.is_valid is False
    
    def test_ledger_key_invalid_with_short_content(self):
        """Ledger key is invalid when content is too short."""
        key = LedgerKeyEvidence(
            promise_id="test_123",
            content="ok",
            confidence=0.8,
            created_at=1234567890.0
        )
        assert key.is_valid is False
    
    def test_ledger_key_at_threshold_boundary(self):
        """Ledger key at exact threshold is valid."""
        key = LedgerKeyEvidence(
            promise_id="test_123",
            content="I will",
            confidence=0.5,
            created_at=1234567890.0
        )
        assert key.is_valid is True
    
    def test_ledger_key_content_length_boundary(self):
        """Ledger key with exactly 3 chars is valid."""
        key = LedgerKeyEvidence(
            promise_id="test_123",
            content="abc",
            confidence=0.5,
            created_at=1234567890.0
        )
        assert key.is_valid is True


# ============================================================================
# Test Class 2: Violation Key Validation
# ============================================================================

class TestViolationKey:
    """Tests for Violation Key (Key 2) validation."""
    
    def test_violation_key_valid_with_high_severity(self):
        """Violation key is valid when severity >= threshold."""
        key = ViolationKeyEvidence(
            violation_type="contradiction",
            severity=0.8,
            evidence_text="I can't do it",
            has_valid_excuse=False
        )
        assert key.is_valid is True
    
    def test_violation_key_invalid_with_low_severity(self):
        """Violation key is invalid when severity < threshold."""
        key = ViolationKeyEvidence(
            violation_type="behavioral",
            severity=0.4,
            evidence_text="I'm busy",
            has_valid_excuse=False
        )
        assert key.is_valid is False
    
    def test_violation_key_invalid_with_excuse(self):
        """Violation key is invalid when there's a valid excuse."""
        key = ViolationKeyEvidence(
            violation_type="contradiction",
            severity=0.8,
            evidence_text="Sorry, emergency came up",
            has_valid_excuse=True,
            excuse_type="emergency"
        )
        assert key.is_valid is False
    
    def test_violation_key_at_threshold_boundary(self):
        """Violation key at exact threshold is valid."""
        key = ViolationKeyEvidence(
            violation_type="contradiction",
            severity=0.6,
            evidence_text="I can't",
            has_valid_excuse=False
        )
        assert key.is_valid is True


# ============================================================================
# Test Class 3: Double-Key Gating Logic
# ============================================================================

class TestDoubleKeyGating:
    """Tests for double-key gating logic."""
    
    @pytest.mark.asyncio
    async def test_fully_qualified_both_keys_present(self, engine, temp_db_path):
        """Both keys present → fully qualified betrayal."""
        await init_test_db(temp_db_path)
        await init_ledger(temp_db_path)
        ledger = get_ledger()
        
        # Create a promise
        promise = Promise(
            promise_id="p1",
            promiser="user:test",
            promisee="agent",
            content="I will finish the report",
            created_at=1234567890.0,
            confidence=0.8,
            evidence="I promise I will finish the report",
            status="active"
        )
        await ledger.record_promise(promise)
        
        # Create event with violation
        class MockEvent:
            text = "I can't finish the report"
        
        result = await engine.evaluate_betrayal(MockEvent(), "agent")
        
        assert result.gating_result == GatingResult.FULLY_QUALIFIED
        assert result.trace_label == "high_impact_event"
        assert "Both keys satisfied" in result.trace_reason
        assert result.ledger_key is not None
        assert result.violation_key is not None
        assert result.needs_clarification is False
    
    @pytest.mark.asyncio
    async def test_partial_ledger_only_no_violation(self, engine, temp_db_path):
        """Only ledger key present → partial, needs clarification."""
        await init_test_db(temp_db_path)
        await init_ledger(temp_db_path)
        ledger = get_ledger()
        
        # Create a promise
        promise = Promise(
            promise_id="p1",
            promiser="user:test",
            promisee="agent",
            content="I will call you",
            created_at=1234567890.0,
            confidence=0.8,
            evidence="I promise I will call you",
            status="active"
        )
        await ledger.record_promise(promise)
        
        # Create event WITHOUT violation
        class MockEvent:
            text = "See you tomorrow"
        
        result = await engine.evaluate_betrayal(MockEvent(), "agent")
        
        assert result.gating_result == GatingResult.PARTIAL_LEDGER_ONLY
        assert result.trace_label == "high_impact_candidate"
        assert "Ledger key only" in result.trace_reason
        assert result.needs_clarification is True
        assert result.clarification_type == "confirm_promise"
    
    @pytest.mark.asyncio
    async def test_partial_violation_only_no_promise(self, engine, temp_db_path):
        """Only violation key present → partial, needs clarification."""
        await init_test_db(temp_db_path)
        await init_ledger(temp_db_path)
        
        # No promise recorded
        
        # Create event with violation
        class MockEvent:
            text = "I can't do it anymore"
        
        result = await engine.evaluate_betrayal(MockEvent(), "agent")
        
        assert result.gating_result == GatingResult.PARTIAL_VIOLATION_ONLY
        assert result.trace_label == "high_impact_candidate"
        assert "Violation key only" in result.trace_reason
        assert result.needs_clarification is True
        assert result.clarification_type == "request_context"
    
    @pytest.mark.asyncio
    async def test_neither_key_present(self, engine, temp_db_path):
        """Neither key present → neither, no clarification needed."""
        await init_test_db(temp_db_path)
        await init_ledger(temp_db_path)
        
        # No promise, no violation
        class MockEvent:
            text = "Hello, how are you?"
        
        result = await engine.evaluate_betrayal(MockEvent(), "agent")
        
        assert result.gating_result == GatingResult.NEITHER
        assert result.trace_label == "high_impact_candidate"
        assert "Neither key satisfied" in result.trace_reason
        assert result.needs_clarification is False


# ============================================================================
# Test Class 4: Excuse Detection
# ============================================================================

class TestExcuseDetection:
    """Tests for valid excuse detection."""
    
    def test_extension_requested_pattern_zh(self, engine):
        """Detect Chinese extension request."""
        has_excuse, excuse_type = engine._check_for_excuse("能不能延期到明天")
        assert has_excuse is True
        assert excuse_type == "extension_requested"
    
    def test_extension_requested_pattern_en(self, engine):
        """Detect English extension request."""
        has_excuse, excuse_type = engine._check_for_excuse("Can we extend the deadline?")
        assert has_excuse is True
        assert excuse_type == "extension_requested"
    
    def test_conditions_changed_pattern_zh(self, engine):
        """Detect Chinese conditions changed."""
        has_excuse, excuse_type = engine._check_for_excuse("情况变了，现在不一样了")
        assert has_excuse is True
        assert excuse_type == "conditions_changed"
    
    def test_conditions_changed_pattern_en(self, engine):
        """Detect English conditions changed."""
        has_excuse, excuse_type = engine._check_for_excuse("The situation changed unexpectedly")
        assert has_excuse is True
        assert excuse_type == "conditions_changed"
    
    def test_emergency_pattern_zh(self, engine):
        """Detect Chinese emergency."""
        has_excuse, excuse_type = engine._check_for_excuse("有急事，紧急")
        assert has_excuse is True
        assert excuse_type == "emergency"
    
    def test_emergency_pattern_en(self, engine):
        """Detect English emergency."""
        has_excuse, excuse_type = engine._check_for_excuse("There's an emergency")
        assert has_excuse is True
        assert excuse_type == "emergency"
    
    def test_no_excuse(self, engine):
        """No excuse in neutral text."""
        has_excuse, excuse_type = engine._check_for_excuse("I just don't want to do it")
        assert has_excuse is False
        assert excuse_type is None


# ============================================================================
# Test Class 5: Trace Generation
# ============================================================================

class TestTraceGeneration:
    """Tests for trace generation."""
    
    def test_trace_fully_qualified(self):
        """Trace for fully qualified event."""
        result = DoubleKeyResult(
            event_type=HighImpactType.BETRAYAL,
            gating_result=GatingResult.FULLY_QUALIFIED,
            ledger_key=LedgerKeyEvidence(
                promise_id="p1",
                content="help you",
                confidence=0.8
            ),
            violation_key=ViolationKeyEvidence(
                violation_type="contradiction",
                severity=0.8
            ),
            trace_label="high_impact_event",
            trace_reason="Both keys satisfied",
            needs_clarification=False
        )
        
        trace = create_high_impact_trace(result)
        
        assert trace["trace_label"] == "high_impact_event"
        assert trace["gating_result"] == "fully_qualified"
        assert "ledger_key" in trace
        assert "violation_key" in trace
        assert "clarification" not in trace
    
    def test_trace_partial_with_clarification(self):
        """Trace for partial evidence with clarification."""
        result = DoubleKeyResult(
            event_type=HighImpactType.BETRAYAL,
            gating_result=GatingResult.PARTIAL_LEDGER_ONLY,
            ledger_key=LedgerKeyEvidence(
                promise_id="p1",
                content="help you",
                confidence=0.8
            ),
            trace_label="high_impact_candidate",
            trace_reason="Ledger key only",
            needs_clarification=True,
            clarification_type="confirm_promise",
            clarification_prompt="Can you confirm?"
        )
        
        trace = create_high_impact_trace(result)
        
        assert trace["trace_label"] == "high_impact_candidate"
        assert trace["gating_result"] == "partial_ledger_only"
        assert "clarification" in trace
        assert trace["clarification"]["type"] == "confirm_promise"
    
    def test_trace_includes_thresholds(self):
        """Trace includes threshold values."""
        result = DoubleKeyResult(
            event_type=HighImpactType.BETRAYAL,
            gating_result=GatingResult.FULLY_QUALIFIED,
            trace_label="high_impact_event",
            trace_reason="Test",
            ledger_threshold=0.5,
            violation_threshold=0.6
        )
        
        trace = create_high_impact_trace(result)
        
        assert trace["thresholds"]["ledger_confidence_min"] == 0.5
        assert trace["thresholds"]["violation_severity_min"] == 0.6


# ============================================================================
# Test Class 6: Auto-Tune Threshold Configuration
# ============================================================================

class TestAutoTuneThresholds:
    """Tests for tunable thresholds via auto-tune parameters."""
    
    def test_config_from_auto_tune_defaults(self):
        """Config loads default values when no auto-tune params set."""
        config.clear_auto_tune_params()
        cfg = HighImpactGatingConfig.from_auto_tune()
        
        assert cfg.LEDGER_CONFIDENCE_MIN == 0.5
        assert cfg.VIOLATION_SEVERITY_MIN == 0.6
    
    def test_config_from_auto_tune_custom(self):
        """Config loads custom auto-tune values."""
        config.clear_auto_tune_params()
        config.set_auto_tune_param("betrayal_ledger_confidence_min", 0.7)
        config.set_auto_tune_param("betrayal_violation_severity_min", 0.8)
        
        cfg = HighImpactGatingConfig.from_auto_tune()
        
        assert cfg.LEDGER_CONFIDENCE_MIN == 0.7
        assert cfg.VIOLATION_SEVERITY_MIN == 0.8
        
        config.clear_auto_tune_params()
    
    def test_engine_uses_auto_tune_config(self):
        """Engine uses config from auto-tune parameters."""
        config.clear_auto_tune_params()
        config.set_auto_tune_param("betrayal_ledger_confidence_min", 0.9)
        
        refresh_gating_config()
        engine = get_gating_engine()
        
        assert engine.config.LEDGER_CONFIDENCE_MIN == 0.9
        
        config.clear_auto_tune_params()


# ============================================================================
# Test Class 7: Integration with Event Processing
# ============================================================================

class TestEventProcessingIntegration:
    """Tests for integration with event processing."""
    
    @pytest.mark.asyncio
    async def test_process_betrayal_fully_qualified(self, temp_db_path):
        """Process betrayal event that is fully qualified."""
        await init_test_db(temp_db_path)
        await init_ledger(temp_db_path)
        ledger = get_ledger()
        
        # Setup promise
        promise = Promise(
            promise_id="p1",
            promiser="user:test",
            promisee="agent",
            content="deliver the package",
            created_at=1234567890.0,
            confidence=0.9,
            evidence="I promise to deliver",
            status="active"
        )
        await ledger.record_promise(promise)
        
        # Process event
        class MockEvent:
            text = "I can't deliver, sorry"
        
        is_qualified, result, trace = await process_high_impact_event(
            MockEvent(), "agent", "betrayal"
        )
        
        assert is_qualified is True
        assert result is not None
        assert trace is not None
        assert trace["trace_label"] == "high_impact_event"
    
    @pytest.mark.asyncio
    async def test_process_betrayal_partial(self, temp_db_path):
        """Process betrayal event that is partial."""
        await init_test_db(temp_db_path)
        await init_ledger(temp_db_path)
        
        # No promise
        class MockEvent:
            text = "I won't do it"
        
        is_qualified, result, trace = await process_high_impact_event(
            MockEvent(), "agent", "betrayal"
        )
        
        assert is_qualified is False
        assert result is not None
        assert trace is not None
        assert trace["trace_label"] == "high_impact_candidate"
    
    @pytest.mark.asyncio
    async def test_process_non_betrayal_subtype(self):
        """Non-betrayal subtypes return False."""
        class MockEvent:
            text = "Hello"
        
        is_qualified, result, trace = await process_high_impact_event(
            MockEvent(), "agent", "care"
        )
        
        assert is_qualified is False
        assert result is None
        assert trace is None


# ============================================================================
# Test Class 8: Timeout Violation Detection
# ============================================================================

class TestTimeoutViolation:
    """Tests for timeout violation detection."""
    
    @pytest.mark.asyncio
    async def test_timeout_violation_detected(self, engine, temp_db_path):
        """Timeout violations are detected as Key 2."""
        await init_test_db(temp_db_path)
        await init_ledger(temp_db_path)
        ledger = get_ledger()
        
        # Create promise with deadline in the past
        promise = Promise(
            promise_id="p1",
            promiser="user:test",
            promisee="agent",
            content="submit report",
            created_at=time.time() - 7200,  # 2 hours ago
            deadline=time.time() - 3600,  # 1 hour ago (expired)
            confidence=0.8,
            evidence="I promise to submit",
            status="active"
        )
        await ledger.record_promise(promise)
        
        # Event without explicit violation text
        class MockEvent:
            text = "Still working on it"
        
        result = await engine.evaluate_betrayal(MockEvent(), "agent")
        
        # Should detect timeout violation
        assert result.violation_key is not None
        assert result.violation_key.violation_type == "timeout"


# ============================================================================
# Test Class 9: Clarification Prompts
# ============================================================================

class TestClarificationPrompts:
    """Tests for clarification prompt generation."""
    
    def test_promise_clarification_prompt(self, engine):
        """Prompt for promise clarification includes content."""
        ledger_key = LedgerKeyEvidence(
            promise_id="p1",
            content="finish the task",
            confidence=0.8
        )
        
        prompt = engine._generate_promise_clarification(ledger_key)
        
        assert "finish the task" in prompt
        assert "confirm" in prompt.lower()
    
    def test_context_clarification_prompt(self, engine):
        """Prompt for context clarification includes evidence."""
        violation_key = ViolationKeyEvidence(
            violation_type="contradiction",
            severity=0.8,
            evidence_text="I can't do this"
        )
        
        prompt = engine._generate_context_clarification(violation_key)
        
        assert "I can't do this" in prompt
        assert "context" in prompt.lower()


# ============================================================================
# Test Class 10: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases."""
    
    @pytest.mark.asyncio
    async def test_empty_event_text(self, engine, temp_db_path):
        """Empty event text handled gracefully."""
        await init_test_db(temp_db_path)
        await init_ledger(temp_db_path)
        
        class MockEvent:
            text = ""
        
        result = await engine.evaluate_betrayal(MockEvent(), "agent")
        
        # Should not crash, likely partial or neither
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_none_event_text(self, engine, temp_db_path):
        """None event text handled gracefully."""
        await init_test_db(temp_db_path)
        await init_ledger(temp_db_path)
        
        class MockEvent:
            text = None
        
        result = await engine.evaluate_betrayal(MockEvent(), "agent")
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_multiple_promises_selects_best(self, engine, temp_db_path):
        """When multiple promises exist, select most confident."""
        await init_test_db(temp_db_path)
        await init_ledger(temp_db_path)
        ledger = get_ledger()
        
        # Create multiple promises
        for i, conf in enumerate([0.5, 0.9, 0.6]):
            promise = Promise(
                promise_id=f"p{i}",
                promiser="user:test",
                promisee="agent",
                content=f"task {i}",
                created_at=1234567890.0,
                confidence=conf,
                evidence=f"Promise {i}",
                status="active"
            )
            await ledger.record_promise(promise)
        
        class MockEvent:
            text = "I can't do any of it"
        
        result = await engine.evaluate_betrayal(MockEvent(), "agent")
        
        # Should select the 0.9 confidence promise
        assert result.ledger_key is not None
        assert result.ledger_key.confidence == 0.9


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
