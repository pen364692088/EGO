"""
Receipt History Store.

Manages receipt history with indexing and retention.
Capability Owner: OpenEmotion

v6k.2: Receipt History + Index + Retention
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .periodic_receipts import ReceiptMode


@dataclass
class ReceiptIndex:
    """Index entry for a receipt."""
    receipt_id: str
    mode: str
    generated_at: str
    artifact_path: str
    scenario_count: int
    whitelist_verdict: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "mode": self.mode,
            "generated_at": self.generated_at,
            "artifact_path": self.artifact_path,
            "scenario_count": self.scenario_count,
            "whitelist_verdict": self.whitelist_verdict,
        }


class ReceiptHistoryStore:
    """
    Manages receipt history with indexing and retention.
    
    v6k.2 specific:
    - Receipt indexing
    - History queries (latest, by-date, by-round)
    - Retention policy
    - Index rebuilding
    """

    # Retention defaults
    DAILY_RETENTION = 7  # Keep last 7 daily receipts
    ROUND_RETENTION = 5  # Keep last 5 round receipts

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("artifacts/eval/v6k_2")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.index: Dict[str, List[ReceiptIndex]] = {
            ReceiptMode.DAILY.value: [],
            ReceiptMode.ROUND_BASED.value: [],
            ReceiptMode.MANUAL.value: [],
        }
        self._load_index()

    def _load_index(self) -> None:
        """Load existing index from storage."""
        index_file = self.storage_path / "whitelist_receipt_index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text())
                for mode, entries in data.get("index", {}).items():
                    self.index[mode] = [
                        ReceiptIndex(
                            receipt_id=e.get("receipt_id", ""),
                            mode=e.get("mode", mode),
                            generated_at=e.get("generated_at", ""),
                            artifact_path=e.get("artifact_path", ""),
                            scenario_count=e.get("scenario_count", 0),
                            whitelist_verdict=e.get("whitelist_verdict", ""),
                        )
                        for e in entries
                    ]
            except Exception:
                pass

    def _save_index(self) -> None:
        """Save index to storage."""
        index_file = self.storage_path / "whitelist_receipt_index.json"
        data = {
            "index": {
                mode: [e.to_dict() for e in entries]
                for mode, entries in self.index.items()
            },
            "generated_at": datetime.now().isoformat(),
        }
        index_file.write_text(json.dumps(data, indent=2))

    def add_receipt(
        self,
        receipt_id: str,
        mode: ReceiptMode,
        generated_at: str,
        artifact_path: str,
        scenario_count: int,
        whitelist_verdict: str,
    ) -> None:
        """Add a receipt to the index."""
        entry = ReceiptIndex(
            receipt_id=receipt_id,
            mode=mode.value,
            generated_at=generated_at,
            artifact_path=artifact_path,
            scenario_count=scenario_count,
            whitelist_verdict=whitelist_verdict,
        )

        self.index[mode.value].append(entry)

        # Apply retention policy
        self._apply_retention(mode)

        self._save_index()

    def _apply_retention(self, mode: ReceiptMode) -> None:
        """Apply retention policy to a mode."""
        mode_value = mode.value
        max_keep = (
            self.DAILY_RETENTION if mode == ReceiptMode.DAILY
            else self.ROUND_RETENTION if mode == ReceiptMode.ROUND_BASED
            else 50  # Manual receipts
        )

        if len(self.index[mode_value]) > max_keep:
            # Remove oldest entries
            removed = self.index[mode_value][:-max_keep]
            self.index[mode_value] = self.index[mode_value][-max_keep:]

            # Optionally delete artifact files
            for entry in removed:
                try:
                    artifact = Path(entry.artifact_path)
                    if artifact.exists():
                        artifact.unlink()
                except Exception:
                    pass

    def get_latest(self, mode: Optional[ReceiptMode] = None) -> Optional[ReceiptIndex]:
        """Get the latest receipt."""
        if mode:
            entries = self.index.get(mode.value, [])
            return entries[-1] if entries else None

        # Get latest across all modes
        latest = None
        latest_time = ""

        for mode_entries in self.index.values():
            for entry in mode_entries:
                if entry.generated_at > latest_time:
                    latest_time = entry.generated_at
                    latest = entry

        return latest

    def get_by_date(self, date_str: str) -> List[ReceiptIndex]:
        """Get receipts by date (YYYY-MM-DD)."""
        results = []
        for mode_entries in self.index.values():
            for entry in mode_entries:
                if entry.generated_at.startswith(date_str):
                    results.append(entry)
        return results

    def get_by_round(self, round_id: int) -> List[ReceiptIndex]:
        """Get receipts by round ID."""
        results = []
        for entry in self.index.get(ReceiptMode.ROUND_BASED.value, []):
            if f"round_{round_id}" in entry.artifact_path:
                results.append(entry)
        return results

    def get_history(self, mode: Optional[ReceiptMode] = None, limit: int = 10) -> List[ReceiptIndex]:
        """Get receipt history."""
        if mode:
            entries = self.index.get(mode.value, [])
            return entries[-limit:]

        # Combine all modes
        all_entries = []
        for mode_entries in self.index.values():
            all_entries.extend(mode_entries)

        # Sort by generated_at
        all_entries.sort(key=lambda e: e.generated_at)
        return all_entries[-limit:]

    def rebuild_index(self, base_path: Path) -> int:
        """
        Rebuild index from existing receipt files.
        
        Args:
            base_path: Base path to scan for receipts
            
        Returns:
            Number of receipts indexed
        """
        count = 0

        # Reset index
        self.index = {
            ReceiptMode.DAILY.value: [],
            ReceiptMode.ROUND_BASED.value: [],
            ReceiptMode.MANUAL.value: [],
        }

        # Scan for receipt files
        for receipt_file in base_path.glob("whitelist_receipt_*.json"):
            try:
                data = json.loads(receipt_file.read_text())
                mode = ReceiptMode(data.get("mode", "manual"))

                self.add_receipt(
                    receipt_id=data.get("receipt_id", receipt_file.stem),
                    mode=mode,
                    generated_at=data.get("generated_at", ""),
                    artifact_path=str(receipt_file),
                    scenario_count=data.get("active_scenario_count", 0),
                    whitelist_verdict=data.get("whitelist_verdict", ""),
                )
                count += 1
            except Exception:
                continue

        return count

    def get_summary(self) -> Dict[str, Any]:
        """Get receipt history summary."""
        return {
            "daily_receipt_count": len(self.index.get(ReceiptMode.DAILY.value, [])),
            "round_receipt_count": len(self.index.get(ReceiptMode.ROUND_BASED.value, [])),
            "manual_receipt_count": len(self.index.get(ReceiptMode.MANUAL.value, [])),
            "latest_daily": self.get_latest(ReceiptMode.DAILY).to_dict() if self.get_latest(ReceiptMode.DAILY) else None,
            "latest_round": self.get_latest(ReceiptMode.ROUND_BASED).to_dict() if self.get_latest(ReceiptMode.ROUND_BASED) else None,
        }
