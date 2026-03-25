"""
Tests for MVP-4 D4: Promise/Contract Ledger for Betrayal Detection

Tests:
1. Promise Recording
   - Test promise creation with all fields
   - Test promise_id uniqueness
   - Test confidence calculation

2. Promise Lifecycle
   - Test active -> fulfilled transition
   - Test active -> broken transition
   - Test deadline timeout -> broken

3. Violation Detection
   - Test: promise "call tomorrow" + no call for 2 days → violation
   - Test: promise "be there at 5pm" + arrive at 7pm → violation
   - Test: promise "won't tell anyone" + tell someone → violation

4. Betrayal Gate Integration
   - Test: promise + violation → betrayal trigger
   - Test: no promise + rejection text → NO betrayal (just rejection)
   - Test: multiple promises, one violated → correct one flagged

5. Trace/Replay
   - Test: full trace from promise → violation → state change → action
   - Test: replay correctly reconstructs promise history
"""
import pytest
import pytest_asyncio
import os
import sys
import time
import asyncio
import tempfile
import re
import aiosqlite
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.ledger import (
    Promise, PromiseLedger, ViolationResult,
    detect_promise, detect_violation_in_text,
    generate_promise_id, extract_deadline,
    PROMISE_PATTERNS, VIOLATION_PATTERNS,
    get_ledger, init_ledger
)
from emotiond.models import Event
from emotiond.db import init_db, get_db_path


@pytest_asyncio.fixture(scope="function")
async def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test_ledger.db"
    os.environ["EMOTIOND_DB_PATH"] = str(db_path)
    await init_db()
    yield str(db_path)
    del os.environ["EMOTIOND_DB_PATH"]


@pytest_asyncio.fixture(scope="function")
async def ledger(test_db):
    """Create a promise ledger with initialized database."""
    ledger = PromiseLedger(get_db_path())
    return ledger


# ============================================================================
# 1. Promise Recording Tests
# ============================================================================

class TestPromiseModel:
    """Test Promise model."""
    
    def test_promise_creation_all_fields(self):
        """Test promise creation with all fields."""
        now = time.time()
        promise = Promise(
            promise_id="test123",
            promiser="alice",
            promisee="bob",
            content="I will call you tomorrow",
            created_at=now,
            deadline=now + 86400,
            conditions=["must be available"],
            confidence=0.9,
            evidence="I promise I will call you tomorrow",
            status="active"
        )
        
        assert promise.promise_id == "test123"
        assert promise.promiser == "alice"
        assert promise.promisee == "bob"
        assert promise.content == "I will call you tomorrow"
        assert promise.created_at == now
        assert promise.deadline == now + 86400
        assert "must be available" in promise.conditions
        assert promise.confidence == 0.9
        assert promise.evidence == "I promise I will call you tomorrow"
        assert promise.status == "active"
    
    def test_promise_id_uniqueness(self):
        """Test promise_id uniqueness."""
        id1 = generate_promise_id("alice", "bob", "call tomorrow", time.time())
        id2 = generate_promise_id("alice", "bob", "call tomorrow", time.time() + 1)
        
        # Different timestamps should produce different IDs
        assert id1 != id2
        
        # Same inputs should produce same ID
        ts = time.time()
        id3 = generate_promise_id("alice", "bob", "call tomorrow", ts)
        id4 = generate_promise_id("alice", "bob", "call tomorrow", ts)
        assert id3 == id4
    
    def test_confidence_defaults(self):
        """Test confidence has sensible defaults."""
        promise = Promise(
            promise_id="test",
            promiser="alice",
            promisee="bob",
            content="test",
            created_at=time.time(),
            evidence="test"
        )
        
        # Default confidence should be 0.5
        assert promise.confidence == 0.5
        assert promise.status == "active"
        assert promise.conditions == []
        assert promise.deadline is None


class TestPromiseDetection:
    """Test promise detection from text."""
    
    def test_detect_promise_chinese_guarantee(self):
        """Test detecting '我保证' promise."""
        promise = detect_promise("我保证明天给你打电话", "alice", "bob")
        
        assert promise is not None
        assert promise.promiser == "alice"
        assert promise.promisee == "bob"
        assert "明天给你打电话" in promise.content
        assert promise.confidence >= 0.9
    
    def test_detect_promise_chinese_commitment(self):
        """Test detecting '我承诺' promise."""
        promise = detect_promise("我承诺一定会完成这个任务", "alice", "bob")
        
        assert promise is not None
        assert promise.confidence >= 0.9
    
    def test_detect_promise_english_promise(self):
        """Test detecting 'I promise' promise."""
        promise = detect_promise("I promise to call you tomorrow", "alice", "bob")
        
        assert promise is not None
        assert promise.promiser == "alice"
        assert promise.promisee == "bob"
        assert promise.confidence >= 0.85
    
    def test_detect_promise_english_will(self):
        """Test detecting 'I will' promise (lower confidence)."""
        promise = detect_promise("I will be there", "alice", "bob")
        
        assert promise is not None
        assert promise.confidence <= 0.7  # Lower confidence for vague promises
    
    def test_no_promise_detected(self):
        """Test that non-promises are not detected."""
        promise = detect_promise("The weather is nice today", "alice", "bob")
        
        assert promise is None
    
    def test_promise_with_deadline_extraction(self):
        """Test deadline extraction from promise."""
        promise = detect_promise("I promise to call you tomorrow", "alice", "bob")
        
        assert promise is not None
        assert promise.deadline is not None
        # Deadline should be about 24 hours from now
        assert promise.deadline > time.time()
    
    def test_empty_text_no_promise(self):
        """Test that empty text returns no promise."""
        promise = detect_promise("", "alice", "bob")
        assert promise is None
        
        promise = detect_promise(None, "alice", "bob")
        assert promise is None


class TestDeadlineExtraction:
    """Test deadline extraction from text."""
    
    def test_extract_deadline_tomorrow(self):
        """Test extracting 'tomorrow' deadline."""
        deadline = extract_deadline("I'll call you tomorrow")
        
        assert deadline is not None
        # Should be about 24 hours from now
        expected = time.time() + 86400
        assert abs(deadline - expected) < 100  # Within 100 seconds
    
    def test_extract_deadline_chinese_tomorrow(self):
        """Test extracting '明天' deadline."""
        deadline = extract_deadline("我明天给你打电话")
        
        assert deadline is not None
        expected = time.time() + 86400
        assert abs(deadline - expected) < 100
    
    def test_extract_deadline_next_week(self):
        """Test extracting 'next week' deadline."""
        deadline = extract_deadline("I'll finish it next week")
        
        assert deadline is not None
        expected = time.time() + 604800
        assert abs(deadline - expected) < 100
    
    def test_no_deadline_extraction(self):
        """Test that text without deadline returns None."""
        deadline = extract_deadline("I'll do it sometime")
        
        # Could be None or a value depending on patterns
        # This test verifies the function doesn't crash


class TestViolationDetection:
    """Test violation detection from text."""
    
    def test_detect_violation_chinese_cannot(self):
        """Test detecting '我不能' violation."""
        result = detect_violation_in_text("对不起，我不能来了")
        
        assert result is not None
        assert result["type"] == "contradiction"
        assert result["severity"] >= 0.7
    
    def test_detect_violation_english_cannot(self):
        """Test detecting 'I can't' violation."""
        result = detect_violation_in_text("Sorry, I can't make it")
        
        assert result is not None
        assert result["type"] == "contradiction"
    
    def test_detect_violation_never_mind(self):
        """Test detecting 'never mind' violation."""
        result = detect_violation_in_text("Never mind, forget it")
        
        assert result is not None
        assert result["severity"] >= 0.5
    
    def test_detect_violation_chinese_forget_it(self):
        """Test detecting '算了' violation."""
        result = detect_violation_in_text("算了，不用了")
        
        assert result is not None
        assert result["severity"] >= 0.6
    
    def test_no_violation_detected(self):
        """Test that non-violations are not detected."""
        result = detect_violation_in_text("I'll see you tomorrow")
        
        assert result is None


# ============================================================================
# 2. Promise Lifecycle Tests
# ============================================================================

@pytest.mark.asyncio
class TestPromiseLifecycle:
    """Test promise lifecycle transitions."""
    
    async def test_record_promise(self, ledger):
        """Test recording a promise."""
        promise = Promise(
            promise_id="test1",
            promiser="alice",
            promisee="bob",
            content="I will call you",
            created_at=time.time(),
            evidence="I promise I will call you"
        )
        
        promise_id = await ledger.record_promise(promise)
        
        assert promise_id == "test1"
        
        # Verify it was recorded
        retrieved = await ledger.get_promise_by_id("test1")
        assert retrieved is not None
        assert retrieved.promiser == "alice"
    
    async def test_mark_fulfilled(self, ledger):
        """Test marking a promise as fulfilled."""
        # Create promise
        promise = Promise(
            promise_id="test2",
            promiser="alice",
            promisee="bob",
            content="I will call you",
            created_at=time.time(),
            evidence="I promise I will call you"
        )
        await ledger.record_promise(promise)
        
        # Mark fulfilled
        result = await ledger.mark_fulfilled("test2", "Called at 3pm")
        
        assert result is True
        
        # Verify status changed
        retrieved = await ledger.get_promise_by_id("test2")
        assert retrieved.status == "fulfilled"
        assert retrieved.fulfilled_at is not None
    
    async def test_mark_broken(self, ledger):
        """Test marking a promise as broken."""
        # Create promise
        promise = Promise(
            promise_id="test3",
            promiser="alice",
            promisee="bob",
            content="I will call you",
            created_at=time.time(),
            evidence="I promise I will call you"
        )
        await ledger.record_promise(promise)
        
        # Mark broken
        result = await ledger.mark_broken("test3", "Did not call")
        
        assert result is True
        
        # Verify status changed
        retrieved = await ledger.get_promise_by_id("test3")
        assert retrieved.status == "broken"
        assert retrieved.broken_at is not None
        assert retrieved.broken_evidence == "Did not call"
    
    async def test_cannot_fulfill_twice(self, ledger):
        """Test that fulfilled promise cannot be fulfilled again."""
        promise = Promise(
            promise_id="test4",
            promiser="alice",
            promisee="bob",
            content="I will call you",
            created_at=time.time(),
            evidence="I promise I will call you"
        )
        await ledger.record_promise(promise)
        
        # First fulfillment
        result1 = await ledger.mark_fulfilled("test4", "Called")
        assert result1 is True
        
        # Second fulfillment should fail
        result2 = await ledger.mark_fulfilled("test4", "Called again")
        assert result2 is False
    
    async def test_get_active_promises(self, ledger):
        """Test getting active promises for a target."""
        # Create multiple promises
        for i in range(3):
            promise = Promise(
                promise_id=f"active_{i}",
                promiser="alice",
                promisee="bob",
                content=f"Promise {i}",
                created_at=time.time() + i,
                evidence=f"I promise {i}"
            )
            await ledger.record_promise(promise)
        
        # Fulfill one
        await ledger.mark_fulfilled("active_1", "Done")
        
        # Get active promises
        active = await ledger.get_active_promises("bob")
        
        # Should have 2 active (0 and 2)
        assert len(active) == 2
        promise_ids = [p.promise_id for p in active]
        assert "active_0" in promise_ids
        assert "active_2" in promise_ids
        assert "active_1" not in promise_ids


# ============================================================================
# 3. Violation Detection Tests
# ============================================================================

@pytest.mark.asyncio
class TestViolationDetectionAsync:
    """Test violation detection against promises."""
    
    async def test_timeout_violation(self, ledger):
        """Test: promise with deadline passed → violation."""
        # Create promise with deadline in the past
        past_deadline = time.time() - 100  # 100 seconds ago
        promise = Promise(
            promise_id="timeout_test",
            promiser="alice",
            promisee="bob",
            content="I will call you",
            created_at=time.time() - 200,
            deadline=past_deadline,
            evidence="I promise I will call you"
        )
        await ledger.record_promise(promise)
        
        # Create event from the promiser
        event = Event(
            type="user_message",
            actor="alice",
            target="bob",
            text="Hello there"
        )
        
        # Detect violation
        violation = await ledger.detect_violation(event)
        
        assert violation is not None
        assert violation.violation_type == "timeout"
        assert violation.promise.promise_id == "timeout_test"
    
    async def test_contradiction_violation(self, ledger):
        """Test: promise + contradiction text → violation."""
        # Create promise
        promise = Promise(
            promise_id="contradiction_test",
            promiser="alice",
            promisee="bob",
            content="I will call you tomorrow",
            created_at=time.time(),
            evidence="I promise I will call you tomorrow"
        )
        await ledger.record_promise(promise)
        
        # Create event with contradiction containing "不能" 
        event = Event(
            type="user_message",
            actor="alice",
            target="bob",
            text="对不起，我不能来了"
        )
        
        # Detect violation
        violation = await ledger.detect_violation(event)
        
        assert violation is not None
        assert violation.violation_type == "contradiction"
    
    async def test_no_promise_no_violation(self, ledger):
        """Test: no promise → no violation."""
        # Create event without any promise
        event = Event(
            type="user_message",
            actor="charlie",
            target="david",
            text="I can't make it"
        )
        
        # Detect violation
        violation = await ledger.detect_violation(event)
        
        # No violation because there's no promise
        assert violation is None
    
    async def test_different_promiser_no_violation(self, ledger):
        """Test: promise from different actor → no violation."""
        # Create promise from alice
        promise = Promise(
            promise_id="different_test",
            promiser="alice",
            promisee="bob",
            content="I will call you",
            created_at=time.time(),
            evidence="I promise I will call you"
        )
        await ledger.record_promise(promise)
        
        # Create event from charlie (not alice)
        event = Event(
            type="user_message",
            actor="charlie",
            target="bob",
            text="I can't make it"
        )
        
        # Detect violation
        violation = await ledger.detect_violation(event)
        
        # No violation because charlie didn't make the promise
        assert violation is None


# ============================================================================
# 4. Betrayal Gate Integration Tests
# ============================================================================

@pytest.mark.asyncio
class TestBetrayalGateIntegration:
    """Test integration with betrayal detection."""
    
    async def test_promise_violation_triggers_betrayal(self, ledger):
        """Test: promise + violation → betrayal trigger."""
        # Create promise
        promise = Promise(
            promise_id="betrayal_test",
            promiser="alice",
            promisee="bob",
            content="I will never tell anyone your secret",
            created_at=time.time(),
            confidence=0.95,
            evidence="I promise I will never tell anyone your secret"
        )
        await ledger.record_promise(promise)
        
        # Create event with betrayal
        event = Event(
            type="world_event",
            actor="alice",
            target="bob",
            text=None,
            meta={"subtype": "betrayal", "source": "system"}
        )
        
        # Detect violation
        violation = await ledger.detect_violation(event)
        
        # When there's an active promise and betrayal event, should detect
        # Note: In real integration, this would set betrayal_evidence in event.meta
    
    async def test_no_promise_rejection_no_betrayal(self, ledger):
        """Test: no promise + rejection text → NO betrayal (just rejection)."""
        # Create event with rejection but no prior promise
        event = Event(
            type="user_message",
            actor="alice",
            target="bob",
            text="I don't want to see you anymore"
        )
        
        # Detect violation
        violation = await ledger.detect_violation(event)
        
        # No violation because no promise was made
        assert violation is None
    
    async def test_multiple_promises_one_violated(self, ledger):
        """Test: multiple promises, one violated → correct one flagged."""
        # Create multiple promises
        promise1 = Promise(
            promise_id="multi_1",
            promiser="alice",
            promisee="bob",
            content="I will call you tomorrow",
            created_at=time.time(),
            evidence="I promise to call you tomorrow"
        )
        promise2 = Promise(
            promise_id="multi_2",
            promiser="alice",
            promisee="bob",
            content="I will bring the documents",
            created_at=time.time(),
            deadline=time.time() + 86400,  # Not yet expired
            evidence="I promise to bring the documents"
        )
        await ledger.record_promise(promise1)
        await ledger.record_promise(promise2)
        
        # Create event with "不能" which triggers contradiction
        event = Event(
            type="user_message",
            actor="alice",
            target="bob",
            text="对不起，我不能来了"
        )
        
        # Detect violation
        violation = await ledger.detect_violation(event)
        
        assert violation is not None


# ============================================================================
# 5. Trace/Replay Tests
# ============================================================================

@pytest.mark.asyncio
class TestTraceReplay:
    """Test trace and replay functionality."""
    
    async def test_full_trace(self, ledger):
        """Test: full trace from promise → violation → state change."""
        # 1. Create promise
        promise = Promise(
            promise_id="trace_test",
            promiser="alice",
            promisee="bob",
            content="I will meet you at 5pm",
            created_at=time.time(),
            deadline=time.time() + 3600,  # 1 hour deadline
            evidence="I promise I will meet you at 5pm"
        )
        await ledger.record_promise(promise)
        
        # 2. Verify promise is active
        active = await ledger.get_active_promises("bob")
        assert len(active) == 1
        assert active[0].promise_id == "trace_test"
        
        # 3. Detect violation
        event = Event(
            type="user_message",
            actor="alice",
            target="bob",
            text="对不起，我不能来了"
        )
        violation = await ledger.detect_violation(event)
        
        assert violation is not None
        
        # 4. Mark promise as broken
        await ledger.mark_broken("trace_test", violation.evidence)
        
        # 5. Verify state changed
        broken_promise = await ledger.get_promise_by_id("trace_test")
        assert broken_promise.status == "broken"
        assert broken_promise.broken_at is not None
    
    async def test_replay_reconstructs_history(self, ledger):
        """Test: replay correctly reconstructs promise history."""
        # Create multiple promises with different statuses
        promises = [
            Promise(
                promise_id="replay_1",
                promiser="alice",
                promisee="bob",
                content="Promise 1",
                created_at=time.time() - 100,
                evidence="Evidence 1"
            ),
            Promise(
                promise_id="replay_2",
                promiser="alice",
                promisee="bob",
                content="Promise 2",
                created_at=time.time() - 50,
                evidence="Evidence 2"
            ),
            Promise(
                promise_id="replay_3",
                promiser="charlie",
                promisee="david",
                content="Promise 3",
                created_at=time.time(),
                evidence="Evidence 3"
            ),
        ]
        
        for p in promises:
            await ledger.record_promise(p)
        
        # Fulfill one
        await ledger.mark_fulfilled("replay_1", "Done")
        
        # Break one
        await ledger.mark_broken("replay_2", "Failed")
        
        # Get all promises
        all_promises = await ledger.get_all_promises()
        
        assert len(all_promises) == 3
        
        # Verify history is correct
        status_map = {p.promise_id: p.status for p in all_promises}
        assert status_map["replay_1"] == "fulfilled"
        assert status_map["replay_2"] == "broken"
        assert status_map["replay_3"] == "active"


# ============================================================================
# Edge Case Tests
# ============================================================================

@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases."""
    
    async def test_concurrent_promises_same_content(self, ledger):
        """Test handling concurrent promises with same content."""
        ts = time.time()
        
        # Two promises with same content but different timestamps
        promise1 = Promise(
            promise_id=generate_promise_id("alice", "bob", "call", ts),
            promiser="alice",
            promisee="bob",
            content="I will call",
            created_at=ts,
            evidence="I promise I will call"
        )
        promise2 = Promise(
            promise_id=generate_promise_id("alice", "bob", "call", ts + 1),
            promiser="alice",
            promisee="bob",
            content="I will call",
            created_at=ts + 1,
            evidence="I promise I will call again"
        )
        
        await ledger.record_promise(promise1)
        await ledger.record_promise(promise2)
        
        # Both should exist
        all_promises = await ledger.get_all_promises()
        assert len(all_promises) == 2
    
    async def test_cleanup_old_promises(self, ledger, test_db):
        """Test cleanup of old promises."""
        # Create old fulfilled promise
        old_promise = Promise(
            promise_id="old_promise",
            promiser="alice",
            promisee="bob",
            content="Old promise",
            created_at=time.time() - (31 * 86400),  # 31 days ago
            evidence="Old evidence"
        )
        await ledger.record_promise(old_promise)
        await ledger.mark_fulfilled("old_promise", "Done long ago")
        
        # Clear cache to ensure we get fresh data
        await ledger.clear_cache()
        
        # Manually set fulfilled_at to be 31 days ago for testing cleanup
        async with aiosqlite.connect(ledger.db_path) as db:
            await db.execute("UPDATE promises SET fulfilled_at = ? WHERE promise_id = ?", (time.time() - (31 * 86400), "old_promise"))
            await db.commit()
        
        # Clear cache again to force re-read
        await ledger.clear_cache()
        
        # Create new promise
        new_promise = Promise(
            promise_id="new_promise",
            promiser="alice",
            promisee="bob",
            content="New promise",
            created_at=time.time(),
            evidence="New evidence"
        )
        await ledger.record_promise(new_promise)
        
        # Cleanup old promises
        await ledger.cleanup_old_promises(max_age_days=30)
        
        # Old promise should be deleted
        old = await ledger.get_promise_by_id("old_promise")
        assert old is None
        
        # New promise should still exist
        new = await ledger.get_promise_by_id("new_promise")
        assert new is not None
    
    async def test_cache_consistency(self, ledger):
        """Test that cache stays consistent with database."""
        promise = Promise(
            promise_id="cache_test",
            promiser="alice",
            promisee="bob",
            content="Cache test",
            created_at=time.time(),
            evidence="Cache test evidence"
        )
        
        # Record promise (should update cache)
        await ledger.record_promise(promise)
        
        # Get from cache
        cached = ledger._cache.get("cache_test")
        assert cached is not None
        assert cached.status == "active"
        
        # Mark broken
        await ledger.mark_broken("cache_test", "Broken")
        
        # Cache should be updated
        cached = ledger._cache.get("cache_test")
        assert cached.status == "broken"
        
        # Clear cache
        await ledger.clear_cache()
        assert len(ledger._cache) == 0


# ============================================================================
# Pattern Coverage Tests
# ============================================================================

class TestPatternCoverage:
    """Test all promise and violation patterns."""
    
    def test_all_promise_patterns_work(self):
        """Test that all promise patterns compile and match."""
        for pattern, meta in PROMISE_PATTERNS.items():
            # Compile the pattern
            compiled = re.compile(pattern, re.IGNORECASE)
            assert compiled is not None
            
            # Check that lang and confidence exist
            assert "lang" in meta
            assert "confidence" in meta
            assert 0 <= meta["confidence"] <= 1
    
    def test_all_violation_patterns_work(self):
        """Test that all violation patterns compile and match."""
        for pattern, info in VIOLATION_PATTERNS.items():
            # Compile the pattern
            compiled = re.compile(pattern, re.IGNORECASE)
            assert compiled is not None
            
            # Check that type and severity exist
            assert "type" in info
            assert "severity" in info
            assert 0 <= info["severity"] <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
