"""
Tests for v6k.1 Periodic Receipts Automation.

v6k.1: Daily and Round-based Receipt Auto Generation
"""

import pytest
from pathlib import Path

from emotiond.memory.embedding.production_whitelist import ProductionWhitelistRegistry
from emotiond.memory.embedding.whitelist_governance import WhitelistGovernanceEvaluator
from emotiond.memory.embedding.periodic_receipts import (
    PeriodicReceiptGenerator,
    ReceiptMode,
)


class TestV6k1DailyReceipt:
    """Tests for daily receipt auto generation."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def governance(self, registry, tmp_path):
        return WhitelistGovernanceEvaluator(registry, storage_path=tmp_path)

    @pytest.fixture
    def generator(self, registry, governance, tmp_path):
        return PeriodicReceiptGenerator(registry, governance, storage_path=tmp_path)

    def test_daily_receipt_auto_generates(self, generator):
        """Daily receipt is automatically generated."""
        receipt = generator.generate_daily_receipt()

        assert receipt is not None
        assert receipt.mode == ReceiptMode.DAILY
        assert receipt.receipt_id.startswith("whitelist-receipt-daily")

    def test_daily_receipt_has_required_fields(self, generator):
        """Daily receipt contains all required fields."""
        receipt = generator.generate_daily_receipt()

        assert receipt.receipt_version == "v6k-v1"
        assert receipt.generated_at != ""
        assert receipt.period_start != ""
        assert receipt.period_end != ""
        assert receipt.active_scenario_count >= 0
        assert receipt.whitelist_verdict != ""

    def test_daily_receipt_artifact_created(self, generator, tmp_path):
        """Daily receipt artifact file is created."""
        receipt = generator.generate_daily_receipt()

        assert "daily_receipt" in receipt.artifact_refs
        artifact_path = Path(receipt.artifact_refs["daily_receipt"])
        assert artifact_path.exists()

    def test_daily_receipt_content_valid(self, generator):
        """Daily receipt content is valid JSON."""
        import json

        receipt = generator.generate_daily_receipt()

        receipt_dict = receipt.to_dict()
        assert json.dumps(receipt_dict)  # Should be JSON-serializable

        # Check required fields
        assert "receipt_version" in receipt_dict
        assert "scenario_metrics" in receipt_dict


class TestV6k1RoundReceipt:
    """Tests for round-based receipt auto generation."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def governance(self, registry, tmp_path):
        return WhitelistGovernanceEvaluator(registry, storage_path=tmp_path)

    @pytest.fixture
    def generator(self, registry, governance, tmp_path):
        return PeriodicReceiptGenerator(registry, governance, storage_path=tmp_path)

    def test_round_receipt_auto_generates(self, generator):
        """Round receipt is automatically generated."""
        receipt = generator.generate_round_receipt(round_id=1)

        assert receipt is not None
        assert receipt.mode == ReceiptMode.ROUND_BASED
        assert receipt.receipt_id.startswith("whitelist-receipt-round_based")

    def test_round_receipt_has_required_fields(self, generator):
        """Round receipt contains all required fields."""
        receipt = generator.generate_round_receipt(round_id=2)

        assert receipt.receipt_version == "v6k-v1"
        assert receipt.generated_at != ""
        assert receipt.active_scenario_count >= 0
        assert receipt.whitelist_verdict != ""

    def test_round_receipt_artifact_created(self, generator, tmp_path):
        """Round receipt artifact file is created."""
        receipt = generator.generate_round_receipt(round_id=1)

        assert "round_receipt" in receipt.artifact_refs
        artifact_path = Path(receipt.artifact_refs["round_receipt"])
        assert artifact_path.exists()

    def test_multiple_round_receipts(self, generator):
        """Multiple round receipts can be generated."""
        receipt1 = generator.generate_round_receipt(round_id=1)
        receipt2 = generator.generate_round_receipt(round_id=2)

        # Check artifact paths are different (round_1 vs round_2)
        assert "round_1" in receipt1.artifact_refs.get("round_receipt", "")
        assert "round_2" in receipt2.artifact_refs.get("round_receipt", "")


class TestV6k1ReceiptHistory:
    """Tests for receipt history tracking."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def governance(self, registry, tmp_path):
        return WhitelistGovernanceEvaluator(registry, storage_path=tmp_path)

    @pytest.fixture
    def generator(self, registry, governance, tmp_path):
        return PeriodicReceiptGenerator(registry, governance, storage_path=tmp_path)

    def test_receipts_history_tracked(self, generator):
        """Receipts are tracked in history."""
        generator.generate_daily_receipt()
        generator.generate_round_receipt(round_id=1)

        history = generator.get_receipt_history(limit=10)

        assert len(history) == 2

    def test_latest_receipt(self, generator):
        """Latest receipt can be retrieved."""
        generator.generate_daily_receipt()
        receipt2 = generator.generate_round_receipt(round_id=1)

        latest = generator.get_latest_receipt()

        assert latest.receipt_id == receipt2.receipt_id

    def test_receipts_by_mode(self, generator):
        """Receipts can be filtered by mode."""
        generator.generate_daily_receipt()
        generator.generate_round_receipt(round_id=1)
        generator.generate_round_receipt(round_id=2)

        daily_receipts = generator.get_receipts_by_mode(ReceiptMode.DAILY)
        round_receipts = generator.get_receipts_by_mode(ReceiptMode.ROUND_BASED)

        assert len(daily_receipts) == 1
        assert len(round_receipts) == 2


class TestV6k1GovernanceSummaryUpdate:
    """Tests for governance summary consuming receipts."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def governance(self, registry, tmp_path):
        return WhitelistGovernanceEvaluator(registry, storage_path=tmp_path)

    @pytest.fixture
    def generator(self, registry, governance, tmp_path):
        return PeriodicReceiptGenerator(registry, governance, storage_path=tmp_path)

    def test_governance_summary_includes_receipt_data(self, governance, generator):
        """Governance summary reflects receipt data."""
        generator.generate_daily_receipt()

        report = governance.generate_governance_report()

        assert "governance" in report
        assert report["governance"]["active_scenario_count"] >= 0

    def test_receipt_count_matches_scenario_count(self, governance, generator):
        """Receipt scenario count matches governance scenario count."""
        receipt = generator.generate_daily_receipt()
        report = governance.generate_governance_report()

        assert receipt.active_scenario_count == report["governance"]["active_scenario_count"]


class TestV6k1ManualReceiptFallback:
    """Tests for manual receipt as fallback."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def governance(self, registry, tmp_path):
        return WhitelistGovernanceEvaluator(registry, storage_path=tmp_path)

    @pytest.fixture
    def generator(self, registry, governance, tmp_path):
        return PeriodicReceiptGenerator(registry, governance, storage_path=tmp_path)

    def test_manual_receipt_still_works(self, generator):
        """Manual receipt can still be generated as fallback."""
        receipt = generator.generate_manual_receipt(reason="Ad-hoc check")

        assert receipt.mode == ReceiptMode.MANUAL
        assert receipt.receipt_id.startswith("whitelist-receipt-manual")

    def test_all_three_modes_available(self, generator):
        """All three receipt modes are available."""
        daily = generator.generate_daily_receipt()
        round_r = generator.generate_round_receipt(round_id=1)
        manual = generator.generate_manual_receipt(reason="Test")

        assert daily.mode == ReceiptMode.DAILY
        assert round_r.mode == ReceiptMode.ROUND_BASED
        assert manual.mode == ReceiptMode.MANUAL
