"""MVP-10 T20: Tests for Commitments Ledger persistence functionality."""
import pytest
import pytest_asyncio
import tempfile
import os
import time
import json

from emotiond.memory.commitments import (
    Commitment,
    CommitmentsLedger,
    CommitmentStatus,
    get_commitments_ledger,
)


@pytest_asyncio.fixture
async def commitments_ledger():
    """Create an isolated commitments ledger for testing."""
    temp_dir = tempfile.mkdtemp(prefix="commitments_test_")
    db_path = os.path.join(temp_dir, "test_commitments.db")
    
    ledger = CommitmentsLedger(db_path=db_path)
    await ledger.init_db()
    
    yield ledger
    
    # Cleanup
    await ledger.clear()
    try:
        os.remove(db_path)
    except:
        pass
    os.rmdir(temp_dir)


class TestCommitment:
    """Tests for Commitment dataclass."""
    
    def test_create_commitment(self):
        """Test creating a basic commitment."""
        commit = Commitment(
            id="commit_001",
            description="Complete the feature by Friday",
            deadline=time.time() + 86400,
        )
        
        assert commit.id == "commit_001"
        assert commit.status == CommitmentStatus.PENDING.value
        assert commit.priority == 3
    
    def test_commitment_to_dict(self):
        """Test serializing commitment to dictionary."""
        commit = Commitment(
            id="commit_002",
            description="Review PR",
            deadline=2000.0,
            status=CommitmentStatus.COMPLETED.value,
            created_at=1000.0,
            completed_at=1500.0,
            priority=5,
        )
        
        data = commit.to_dict()
        
        assert data["id"] == "commit_002"
        assert data["status"] == "completed"
        assert data["priority"] == 5
    
    def test_commitment_from_dict(self):
        """Test deserializing commitment from dictionary."""
        data = {
            "id": "commit_003",
            "description": "Deploy service",
            "deadline": 3000.0,
            "status": "pending",
            "created_at": 2500.0,
            "priority": 4,
            "context": {"team": "backend"},
        }
        
        commit = Commitment.from_dict(data)
        
        assert commit.id == "commit_003"
        assert commit.priority == 4
        assert commit.context["team"] == "backend"
    
    def test_is_overdue_true(self):
        """Test overdue detection when overdue."""
        commit = Commitment(
            id="commit_overdue",
            description="Past deadline",
            deadline=time.time() - 100,  # 100 seconds ago
            status=CommitmentStatus.PENDING.value,
        )
        
        assert commit.is_overdue() is True
    
    def test_is_overdue_false_future(self):
        """Test overdue detection with future deadline."""
        commit = Commitment(
            id="commit_future",
            description="Future deadline",
            deadline=time.time() + 86400,  # 1 day from now
            status=CommitmentStatus.PENDING.value,
        )
        
        assert commit.is_overdue() is False
    
    def test_is_overdue_false_no_deadline(self):
        """Test overdue detection with no deadline."""
        commit = Commitment(
            id="commit_no_deadline",
            description="No deadline",
            deadline=None,
            status=CommitmentStatus.PENDING.value,
        )
        
        assert commit.is_overdue() is False
    
    def test_is_overdue_false_completed(self):
        """Test overdue detection when completed."""
        commit = Commitment(
            id="commit_done",
            description="Already done",
            deadline=time.time() - 100,
            status=CommitmentStatus.COMPLETED.value,
        )
        
        assert commit.is_overdue() is False
    
    def test_compute_score_weight_pending(self):
        """Test score weight for pending commitment."""
        commit = Commitment(
            id="commit_weight",
            description="Test weight",
            deadline=time.time() + 3600,  # 1 hour
            status=CommitmentStatus.PENDING.value,
            priority=5,
        )
        
        weight = commit.compute_score_weight()
        
        # High priority + close deadline = higher weight
        assert weight > 0
        assert weight <= 2.0
    
    def test_compute_score_weight_overdue(self):
        """Test score weight for overdue commitment."""
        commit = Commitment(
            id="commit_overdue_weight",
            description="Overdue",
            deadline=time.time() - 100,
            status=CommitmentStatus.PENDING.value,
            priority=5,
        )
        
        weight = commit.compute_score_weight()
        
        # Overdue = double weight
        assert weight >= 1.0  # base weight (1.0 for priority 5) * 2.0
    
    def test_compute_score_weight_completed(self):
        """Test score weight for completed commitment."""
        commit = Commitment(
            id="commit_done_weight",
            description="Completed",
            status=CommitmentStatus.COMPLETED.value,
            priority=5,
        )
        
        weight = commit.compute_score_weight()
        
        assert weight == 0.0


class TestCommitmentsLedgerAdd:
    """Tests for adding commitments."""
    
    @pytest.mark.asyncio
    async def test_add_basic(self, commitments_ledger):
        """Test adding a basic commitment."""
        commit = await commitments_ledger.add(
            description="Complete the documentation",
        )
        
        assert commit.id.startswith("commit_")
        assert commit.description == "Complete the documentation"
        assert commit.status == CommitmentStatus.PENDING.value
    
    @pytest.mark.asyncio
    async def test_add_with_deadline(self, commitments_ledger):
        """Test adding commitment with deadline."""
        deadline = time.time() + 86400
        
        commit = await commitments_ledger.add(
            description="Submit report",
            deadline=deadline,
        )
        
        assert commit.deadline == deadline
    
    @pytest.mark.asyncio
    async def test_add_with_goal_id(self, commitments_ledger):
        """Test adding commitment with goal ID."""
        commit = await commitments_ledger.add(
            description="Fix bug #123",
            goal_id="goal_fix_bugs",
        )
        
        assert commit.goal_id == "goal_fix_bugs"
    
    @pytest.mark.asyncio
    async def test_add_with_priority(self, commitments_ledger):
        """Test adding commitment with priority."""
        commit = await commitments_ledger.add(
            description="Critical task",
            priority=5,
        )
        
        assert commit.priority == 5
    
    @pytest.mark.asyncio
    async def test_priority_clamped(self, commitments_ledger):
        """Test that priority is clamped to 1-5 range."""
        commit_high = await commitments_ledger.add(
            description="Priority 10",
            priority=10,
        )
        assert commit_high.priority == 5
        
        commit_low = await commitments_ledger.add(
            description="Priority 0",
            priority=0,
        )
        assert commit_low.priority == 1


class TestCommitmentsLedgerComplete:
    """Tests for completing commitments."""
    
    @pytest.mark.asyncio
    async def test_complete_basic(self, commitments_ledger):
        """Test completing a commitment."""
        commit = await commitments_ledger.add(description="Task to complete")
        
        result = await commitments_ledger.complete(commit.id)
        
        assert result is not None
        assert result.status == CommitmentStatus.COMPLETED.value
        assert result.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_complete_with_timestamp(self, commitments_ledger):
        """Test completing with specific timestamp."""
        commit = await commitments_ledger.add(description="Task")
        custom_time = time.time() - 100
        
        result = await commitments_ledger.complete(commit.id, completed_at=custom_time)
        
        assert result.completed_at == custom_time
    
    @pytest.mark.asyncio
    async def test_complete_nonexistent(self, commitments_ledger):
        """Test completing nonexistent commitment."""
        result = await commitments_ledger.complete("nonexistent_id")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_complete_already_completed(self, commitments_ledger):
        """Test completing an already completed commitment."""
        commit = await commitments_ledger.add(description="Task")
        await commitments_ledger.complete(commit.id)
        
        # Try to complete again
        result = await commitments_ledger.complete(commit.id)
        assert result is None


class TestCommitmentsLedgerBreach:
    """Tests for breaching commitments."""
    
    @pytest.mark.asyncio
    async def test_breach_basic(self, commitments_ledger):
        """Test breaching a commitment."""
        commit = await commitments_ledger.add(description="Task to breach")
        
        result = await commitments_ledger.breach(
            commit.id, 
            reason="Deadline passed"
        )
        
        assert result is not None
        assert result.status == CommitmentStatus.BREACHED.value
        assert result.breach_reason == "Deadline passed"
        assert result.breached_at is not None
    
    @pytest.mark.asyncio
    async def test_breach_nonexistent(self, commitments_ledger):
        """Test breaching nonexistent commitment."""
        result = await commitments_ledger.breach("nonexistent_id")
        assert result is None


class TestCommitmentsLedgerGet:
    """Tests for getting commitments."""
    
    @pytest.mark.asyncio
    async def test_get_by_id(self, commitments_ledger):
        """Test getting commitment by ID."""
        commit = await commitments_ledger.add(description="Get this")
        
        result = await commitments_ledger.get(commit.id)
        
        assert result is not None
        assert result.id == commit.id
    
    @pytest.mark.asyncio
    async def test_get_nonexistent(self, commitments_ledger):
        """Test getting nonexistent commitment."""
        result = await commitments_ledger.get("nonexistent_id")
        assert result is None


class TestCommitmentsLedgerGetPending:
    """Tests for getting pending commitments."""
    
    @pytest.mark.asyncio
    async def test_get_pending(self, commitments_ledger):
        """Test getting pending commitments."""
        await commitments_ledger.add(description="Pending 1")
        await commitments_ledger.add(description="Pending 2")
        commit = await commitments_ledger.add(description="To complete")
        await commitments_ledger.complete(commit.id)
        
        pending = await commitments_ledger.get_pending()
        
        assert len(pending) == 2
        for p in pending:
            assert p.status == CommitmentStatus.PENDING.value
    
    @pytest.mark.asyncio
    async def test_get_pending_empty(self, commitments_ledger):
        """Test getting pending when none exist."""
        pending = await commitments_ledger.get_pending()
        assert len(pending) == 0


class TestCommitmentsLedgerGetOverdue:
    """Tests for getting overdue commitments."""
    
    @pytest.mark.asyncio
    async def test_get_overdue(self, commitments_ledger):
        """Test getting overdue commitments."""
        # Overdue
        await commitments_ledger.add(
            description="Overdue task",
            deadline=time.time() - 100,
        )
        
        # Not overdue
        await commitments_ledger.add(
            description="Future task",
            deadline=time.time() + 86400,
        )
        
        # No deadline (not overdue)
        await commitments_ledger.add(
            description="No deadline task",
        )
        
        overdue = await commitments_ledger.get_overdue()
        
        assert len(overdue) == 1
        assert overdue[0].description == "Overdue task"
    
    @pytest.mark.asyncio
    async def test_get_overdue_empty(self, commitments_ledger):
        """Test getting overdue when none exist."""
        await commitments_ledger.add(
            description="Future task",
            deadline=time.time() + 86400,
        )
        
        overdue = await commitments_ledger.get_overdue()
        assert len(overdue) == 0


class TestCommitmentsLedgerGetByGoal:
    """Tests for getting commitments by goal."""
    
    @pytest.mark.asyncio
    async def test_get_by_goal(self, commitments_ledger):
        """Test getting commitments by goal ID."""
        await commitments_ledger.add(
            description="Goal task 1",
            goal_id="goal_001",
        )
        await commitments_ledger.add(
            description="Goal task 2",
            goal_id="goal_001",
        )
        await commitments_ledger.add(
            description="Other task",
            goal_id="goal_002",
        )
        
        commits = await commitments_ledger.get_by_goal("goal_001")
        
        assert len(commits) == 2
        for c in commits:
            assert c.goal_id == "goal_001"


class TestCommitmentsLedgerWorkspaceScoring:
    """Tests for workspace scoring integration."""
    
    @pytest.mark.asyncio
    async def test_compute_workspace_score_weight_empty(self, commitments_ledger):
        """Test workspace weight with no commitments."""
        weight = await commitments_ledger.compute_workspace_score_weight()
        assert weight == 0.0
    
    @pytest.mark.asyncio
    async def test_compute_workspace_score_weight(self, commitments_ledger):
        """Test workspace weight calculation."""
        await commitments_ledger.add(
            description="High priority task",
            priority=5,
            deadline=time.time() + 3600,
        )
        await commitments_ledger.add(
            description="Low priority task",
            priority=1,
            deadline=time.time() + 86400,
        )
        
        weight = await commitments_ledger.compute_workspace_score_weight()
        
        assert weight > 0
    
    @pytest.mark.asyncio
    async def test_compute_workspace_score_weight_completed_excluded(self, commitments_ledger):
        """Test that completed commitments don't affect weight."""
        commit = await commitments_ledger.add(
            description="Completed task",
            priority=5,
        )
        await commitments_ledger.complete(commit.id)
        
        weight = await commitments_ledger.compute_workspace_score_weight()
        assert weight == 0.0


class TestCommitmentsLedgerStatistics:
    """Tests for statistics."""
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, commitments_ledger):
        """Test getting statistics."""
        await commitments_ledger.add(description="Task 1")
        await commitments_ledger.add(description="Task 2")
        commit = await commitments_ledger.add(description="Task 3")
        await commitments_ledger.complete(commit.id)
        
        stats = await commitments_ledger.get_statistics()
        
        assert stats["total"] == 3
        assert stats["by_status"]["pending"] == 2
        assert stats["by_status"]["completed"] == 1
        assert "workspace_weight" in stats


class TestCommitmentsLedgerAutoBreach:
    """Tests for auto-breaching overdue commitments."""
    
    @pytest.mark.asyncio
    async def test_check_overdue_and_breach(self, commitments_ledger):
        """Test auto-breaching overdue commitments."""
        await commitments_ledger.add(
            description="Overdue task",
            deadline=time.time() - 100,
        )
        await commitments_ledger.add(
            description="Future task",
            deadline=time.time() + 86400,
        )
        
        breached = await commitments_ledger.check_overdue_and_breach()
        
        assert len(breached) == 1
        assert breached[0].description == "Overdue task"
        assert breached[0].status == CommitmentStatus.BREACHED.value


class TestCommitmentsLedgerPersistence:
    """Tests for cross-run persistence."""
    
    @pytest.mark.asyncio
    async def test_export_for_persistence(self, commitments_ledger):
        """Test exporting commitments for persistence."""
        await commitments_ledger.add(description="Task 1")
        await commitments_ledger.add(description="Task 2")
        
        exported = await commitments_ledger.export_for_persistence()
        
        assert len(exported) == 2
        assert all("id" in c and "description" in c for c in exported)
    
    @pytest.mark.asyncio
    async def test_import_from_persistence(self, commitments_ledger):
        """Test importing commitments from persistence."""
        commitments_data = [
            {
                "id": "commit_imported_1",
                "description": "Imported task 1",
                "status": "pending",
                "created_at": time.time(),
                "priority": 3,
            },
            {
                "id": "commit_imported_2",
                "description": "Imported task 2",
                "status": "completed",
                "created_at": time.time() - 100,
                "completed_at": time.time(),
                "priority": 4,
            },
        ]
        
        count = await commitments_ledger.import_from_persistence(commitments_data)
        
        assert count == 2
        
        # Verify imported
        commit = await commitments_ledger.get("commit_imported_1")
        assert commit is not None
        assert commit.description == "Imported task 1"
    
    @pytest.mark.asyncio
    async def test_export_import_roundtrip(self, commitments_ledger):
        """Test export-import roundtrip preserves data."""
        # Add some commitments
        c1 = await commitments_ledger.add(
            description="Original task",
            deadline=time.time() + 3600,
            priority=5,
        )
        c2 = await commitments_ledger.add(
            description="Another task",
            goal_id="goal_test",
        )
        await commitments_ledger.complete(c2.id)
        
        # Export
        exported = await commitments_ledger.export_for_persistence()
        
        # Clear
        await commitments_ledger.clear()
        
        # Import
        await commitments_ledger.import_from_persistence(exported)
        
        # Verify
        restored = await commitments_ledger.get(c1.id)
        assert restored is not None
        assert restored.description == "Original task"
        assert restored.priority == 5
        
        restored2 = await commitments_ledger.get(c2.id)
        assert restored2 is not None
        assert restored2.status == CommitmentStatus.COMPLETED.value


class TestCommitmentsLedgerClear:
    """Tests for clearing ledger."""
    
    @pytest.mark.asyncio
    async def test_clear(self, commitments_ledger):
        """Test clearing all commitments."""
        await commitments_ledger.add(description="Task 1")
        await commitments_ledger.add(description="Task 2")
        
        stats = await commitments_ledger.get_statistics()
        assert stats["total"] == 2
        
        await commitments_ledger.clear()
        
        stats = await commitments_ledger.get_statistics()
        assert stats["total"] == 0
