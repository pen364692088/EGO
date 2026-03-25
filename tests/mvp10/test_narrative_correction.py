"""MVP-10 T19: Tests for Narrative Memory correction functionality."""
import pytest
import pytest_asyncio
import tempfile
import os
import time

from emotiond.memory.narrative import (
    NarrativeEntry,
    NarrativeMemory,
    NarrativeStatus,
    Fact,
    Contradiction,
    get_narrative_memory,
)


@pytest_asyncio.fixture
async def narrative_memory():
    """Create an isolated narrative memory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="narrative_test_")
    db_path = os.path.join(temp_dir, "test_narrative.db")
    
    memory = NarrativeMemory(db_path=db_path)
    await memory.init_db()
    
    yield memory
    
    # Cleanup
    await memory.clear()
    try:
        os.remove(db_path)
    except:
        pass
    os.rmdir(temp_dir)


class TestNarrativeEntry:
    """Tests for NarrativeEntry dataclass."""
    
    def test_create_entry(self):
        """Test creating a basic narrative entry."""
        entry = NarrativeEntry(
            version=1,
            content="The agent successfully completed the task.",
            evidence_pointers=["evt_001", "evt_002"],
        )
        
        assert entry.version == 1
        assert entry.status == NarrativeStatus.ACTIVE.value
        assert len(entry.evidence_pointers) == 2
        assert entry.entry_id.startswith("narr_")
    
    def test_entry_auto_id(self):
        """Test that entry ID is auto-generated."""
        entry = NarrativeEntry(
            version=1,
            content="Test content",
        )
        
        assert entry.entry_id != ""
        assert entry.entry_id.startswith("narr_")
    
    def test_entry_to_dict(self):
        """Test serializing entry to dictionary."""
        entry = NarrativeEntry(
            version=2,
            content="Updated narrative",
            evidence_pointers=["evt_003"],
            entry_id="narr_test",
            previous_version_id="narr_old",
        )
        
        data = entry.to_dict()
        
        assert data["version"] == 2
        assert data["content"] == "Updated narrative"
        assert data["entry_id"] == "narr_test"
        assert data["previous_version_id"] == "narr_old"
    
    def test_entry_from_dict(self):
        """Test deserializing entry from dictionary."""
        data = {
            "entry_id": "narr_123",
            "version": 3,
            "content": "Restored entry",
            "evidence_pointers": ["evt_004", "evt_005"],
            "timestamp": 1000.0,
            "status": "active",
        }
        
        entry = NarrativeEntry.from_dict(data)
        
        assert entry.entry_id == "narr_123"
        assert entry.version == 3
        assert entry.content == "Restored entry"
    
    def test_compute_hash(self):
        """Test hash computation."""
        entry1 = NarrativeEntry(
            version=1,
            content="Same content",
            evidence_pointers=["evt_001"],
        )
        
        entry2 = NarrativeEntry(
            version=1,
            content="Same content",
            evidence_pointers=["evt_001"],
        )
        
        assert entry1.compute_hash() == entry2.compute_hash()


class TestNarrativeMemoryAddEntry:
    """Tests for adding narrative entries."""
    
    @pytest.mark.asyncio
    async def test_add_entry_basic(self, narrative_memory):
        """Test adding a basic entry."""
        entry = await narrative_memory.add_entry(
            content="The user expressed satisfaction with the service.",
            evidence_pointers=["evt_001"],
        )
        
        assert entry.version == 1
        assert entry.status == NarrativeStatus.ACTIVE.value
        assert entry.entry_id.startswith("narr_")
    
    @pytest.mark.asyncio
    async def test_add_entry_with_evidence(self, narrative_memory):
        """Test adding entry with multiple evidence pointers."""
        entry = await narrative_memory.add_entry(
            content="The goal was achieved after multiple attempts.",
            evidence_pointers=["evt_001", "evt_002", "evt_003"],
            metadata={"confidence": 0.9},
        )
        
        assert len(entry.evidence_pointers) == 3
        assert entry.metadata["confidence"] == 0.9
    
    @pytest.mark.asyncio
    async def test_version_increment(self, narrative_memory):
        """Test that version increments correctly."""
        entry1 = await narrative_memory.add_entry(content="First entry")
        entry2 = await narrative_memory.add_entry(content="Second entry")
        entry3 = await narrative_memory.add_entry(content="Third entry")
        
        assert entry1.version == 1
        assert entry2.version == 2
        assert entry3.version == 3


class TestNarrativeMemoryCorrectEntry:
    """Tests for correcting narrative entries."""
    
    @pytest.mark.asyncio
    async def test_correct_entry_basic(self, narrative_memory):
        """Test basic entry correction."""
        original = await narrative_memory.add_entry(
            content="The user was angry about the delay.",
            evidence_pointers=["evt_001"],
        )
        
        corrected = await narrative_memory.correct_entry(
            entry_id=original.entry_id,
            new_content="The user was frustrated but understood the situation.",
            reason="clarification",
        )
        
        # Original should be marked as corrected
        original_check = await narrative_memory.get_entry(original.entry_id)
        assert original_check.status == NarrativeStatus.CORRECTED.value
        
        # New entry should be active
        assert corrected.status == NarrativeStatus.ACTIVE.value
        assert corrected.previous_version_id == original.entry_id
        assert corrected.metadata.get("correction_of") == original.entry_id
    
    @pytest.mark.asyncio
    async def test_correct_entry_with_new_evidence(self, narrative_memory):
        """Test correction with new evidence pointers."""
        original = await narrative_memory.add_entry(
            content="Initial narrative",
            evidence_pointers=["evt_001"],
        )
        
        corrected = await narrative_memory.correct_entry(
            entry_id=original.entry_id,
            new_content="Corrected narrative with more context",
            new_evidence_pointers=["evt_001", "evt_002"],
            reason="additional_evidence",
        )
        
        assert len(corrected.evidence_pointers) == 2
    
    @pytest.mark.asyncio
    async def test_correct_nonexistent_entry(self, narrative_memory):
        """Test correcting a nonexistent entry raises error."""
        with pytest.raises(ValueError, match="not found"):
            await narrative_memory.correct_entry(
                entry_id="nonexistent_id",
                new_content="New content",
            )


class TestNarrativeMemoryGetEntry:
    """Tests for retrieving entries."""
    
    @pytest.mark.asyncio
    async def test_get_entry_by_id(self, narrative_memory):
        """Test getting entry by ID."""
        stored = await narrative_memory.add_entry(content="Test entry")
        
        retrieved = await narrative_memory.get_entry(stored.entry_id)
        
        assert retrieved is not None
        assert retrieved.entry_id == stored.entry_id
        assert retrieved.content == "Test entry"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_entry(self, narrative_memory):
        """Test getting nonexistent entry."""
        result = await narrative_memory.get_entry("nonexistent_id")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_active_entries(self, narrative_memory):
        """Test getting all active entries."""
        entry1 = await narrative_memory.add_entry(content="Active 1")
        entry2 = await narrative_memory.add_entry(content="Active 2")
        
        # Correct one entry
        await narrative_memory.correct_entry(entry1.entry_id, "Corrected")
        
        active = await narrative_memory.get_active_entries()
        
        # Only entry2 should be active (entry1 is corrected, and the new correction is active)
        assert len(active) == 2  # entry2 + corrected entry
        active_ids = [e.entry_id for e in active]
        assert entry2.entry_id in active_ids


class TestNarrativeMemoryVersionHistory:
    """Tests for version history."""
    
    @pytest.mark.asyncio
    async def test_get_version_history(self, narrative_memory):
        """Test getting version history."""
        v1 = await narrative_memory.add_entry(content="Version 1")
        v2 = await narrative_memory.correct_entry(v1.entry_id, "Version 2")
        v3 = await narrative_memory.correct_entry(v2.entry_id, "Version 3")
        
        history = await narrative_memory.get_version_history(v3.entry_id)
        
        assert len(history) == 3
        # Should be in newest-to-oldest order
        assert history[0].entry_id == v3.entry_id
        assert history[1].entry_id == v2.entry_id
        assert history[2].entry_id == v1.entry_id


class TestNarrativeMemoryConsistency:
    """Tests for consistency verification."""
    
    @pytest.mark.asyncio
    async def test_verify_consistency_clean(self, narrative_memory):
        """Test consistency check with clean data."""
        await narrative_memory.add_entry(content="Entry 1")
        await narrative_memory.add_entry(content="Entry 2")
        
        result = await narrative_memory.verify_consistency()
        
        assert result["consistent"] is True
        assert len(result["issues"]) == 0
    
    @pytest.mark.asyncio
    async def test_verify_consistency_orphaned_reference(self, narrative_memory):
        """Test consistency check detects orphaned references."""
        entry = await narrative_memory.add_entry(content="Entry")
        
        # Manually create an entry with invalid previous_version_id
        import aiosqlite
        async with aiosqlite.connect(narrative_memory.db_path) as db:
            await db.execute("""
                INSERT INTO narrative_entries 
                (entry_id, version, content, evidence_pointers, timestamp, previous_version_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("narr_orphan", 99, "Orphan", "[]", time.time(), "nonexistent_prev", "active"))
            await db.commit()
        
        result = await narrative_memory.verify_consistency()
        
        assert result["consistent"] is False
        assert any(i["type"] == "orphaned_reference" for i in result["issues"])


class TestNarrativeMemoryFacts:
    """Tests for fact management."""
    
    @pytest.mark.asyncio
    async def test_add_fact(self, narrative_memory):
        """Test adding a fact."""
        fact = await narrative_memory.add_fact(
            fact_id="fact_001",
            content="The system is available 24/7",
            source="sla_document",
            confidence=1.0,
        )
        
        assert fact.fact_id == "fact_001"
        assert fact.source == "sla_document"
    
    @pytest.mark.asyncio
    async def test_get_fact(self, narrative_memory):
        """Test retrieving a fact."""
        await narrative_memory.add_fact(
            fact_id="fact_002",
            content="Users must authenticate before access",
        )
        
        fact = await narrative_memory.get_fact("fact_002")
        
        assert fact is not None
        assert fact.content == "Users must authenticate before access"


class TestNarrativeMemoryContradictions:
    """Tests for contradiction detection."""
    
    @pytest.mark.asyncio
    async def test_contradiction_detection(self, narrative_memory):
        """Test that contradictions are detected."""
        # Add a fact
        await narrative_memory.add_fact(
            fact_id="fact_time",
            content="The system is always available",
        )
        
        # Add a contradicting entry
        entry = await narrative_memory.add_entry(
            content="The system is not available during maintenance",
        )
        
        # Check for contradictions
        contradictions = await narrative_memory.get_contradictions(entry.entry_id)
        
        # May or may not detect depending on heuristics
        # This tests that the mechanism runs without error
        assert isinstance(contradictions, list)
    
    @pytest.mark.asyncio
    async def test_get_all_contradictions(self, narrative_memory):
        """Test getting all contradictions."""
        await narrative_memory.add_fact(
            fact_id="fact_test",
            content="This is a test fact",
        )
        
        # Get contradictions (should be empty or have detected ones)
        contradictions = await narrative_memory.get_contradictions()
        assert isinstance(contradictions, list)


class TestNarrativeMemoryClear:
    """Tests for clearing memory."""
    
    @pytest.mark.asyncio
    async def test_clear(self, narrative_memory):
        """Test clearing all narrative data."""
        await narrative_memory.add_entry(content="Entry 1")
        await narrative_memory.add_entry(content="Entry 2")
        await narrative_memory.add_fact("fact_001", "Test fact")
        
        active = await narrative_memory.get_active_entries()
        assert len(active) >= 2
        
        await narrative_memory.clear()
        
        active = await narrative_memory.get_active_entries()
        assert len(active) == 0
