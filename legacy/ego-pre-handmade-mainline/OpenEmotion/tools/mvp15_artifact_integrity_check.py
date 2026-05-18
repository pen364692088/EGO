#!/usr/bin/env python
"""
MVP15 Artifact Integrity Checker

Validates artifact content consistency and completeness.

Checks:
- id: Unique job_id present
- timestamp: Created_at timestamp valid
- source event reference: input_evidence.event_type present
- content length: findings/proposals present
- metadata completeness: All required fields present

Usage:
    python tools/mvp15_artifact_integrity_check.py
    python tools/mvp15_artifact_integrity_check.py --verbose
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


ARTIFACTS_DIR = Path("artifacts/mvp15")


# Required fields for a valid artifact
REQUIRED_FIELDS = {
    "job_id",
    "reflection_type",
    "status",
    "created_at",
    "input_evidence",
}

# Optional but recommended fields
RECOMMENDED_FIELDS = {
    "findings",
    "proposals",
    "confidence",
    "completed_at",
}

# Input evidence required fields
INPUT_EVIDENCE_REQUIRED = {
    "event_type",
}


def validate_artifact(artifact_path: Path) -> Tuple[bool, Dict[str, Any]]:
    """Validate a single artifact file."""
    
    result = {
        "path": str(artifact_path),
        "valid": True,
        "errors": [],
        "warnings": [],
        "checks": {},
    }
    
    try:
        with open(artifact_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result["valid"] = False
        result["errors"].append(f"JSON parse error: {e}")
        return False, result
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"Read error: {e}")
        return False, result
    
    # Check 1: ID (job_id)
    has_id = "job_id" in data and data["job_id"]
    result["checks"]["id_present"] = has_id
    if not has_id:
        result["errors"].append("Missing job_id")
        result["valid"] = False
    
    # Check 2: Timestamp (created_at)
    has_timestamp = "created_at" in data and isinstance(data["created_at"], (int, float))
    result["checks"]["timestamp_present"] = has_timestamp
    if not has_timestamp:
        result["errors"].append("Missing or invalid created_at timestamp")
        result["valid"] = False
    else:
        # Validate timestamp is reasonable (within last 30 days)
        try:
            ts = datetime.fromtimestamp(data["created_at"])
            now = datetime.now()
            age_days = (now - ts).days
            result["checks"]["timestamp_age_days"] = age_days
            if age_days < 0:
                result["warnings"].append(f"Timestamp in future: {ts}")
            elif age_days > 30:
                result["warnings"].append(f"Artifact is old: {age_days} days")
        except Exception as e:
            result["warnings"].append(f"Could not parse timestamp: {e}")
    
    # Check 3: Source event reference
    input_evidence = data.get("input_evidence", {})
    has_event_type = "event_type" in input_evidence
    result["checks"]["source_event_reference"] = has_event_type
    if not has_event_type:
        result["warnings"].append("Missing event_type in input_evidence")
    
    # Check 4: Content length
    findings = data.get("findings", [])
    proposals = data.get("proposals", [])
    findings_count = len(findings) if isinstance(findings, list) else 0
    proposals_count = len(proposals) if isinstance(proposals, list) else 0
    
    result["checks"]["findings_count"] = findings_count
    result["checks"]["proposals_count"] = proposals_count
    
    if findings_count == 0 and proposals_count == 0:
        result["warnings"].append("No findings or proposals generated")
    
    # Check 5: Metadata completeness
    missing_required = REQUIRED_FIELDS - set(data.keys())
    missing_recommended = RECOMMENDED_FIELDS - set(data.keys())
    
    result["checks"]["required_fields_present"] = len(missing_required) == 0
    result["checks"]["recommended_fields_missing"] = list(missing_recommended)
    
    if missing_required:
        result["errors"].append(f"Missing required fields: {missing_required}")
        result["valid"] = False
    
    # Additional checks
    result["checks"]["status"] = data.get("status", "unknown")
    result["checks"]["reflection_type"] = data.get("reflection_type", "unknown")
    result["checks"]["confidence"] = data.get("confidence", 0.0)
    
    # File size
    result["checks"]["file_size_bytes"] = artifact_path.stat().st_size
    
    return result["valid"], result


def generate_integrity_report(verbose: bool = False) -> str:
    """Generate artifact integrity report."""
    
    report = f"""# MVP15 Artifact Persistence Integrity Report

> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. Summary

"""
    
    # Find all artifact files
    artifact_files = list(ARTIFACTS_DIR.glob("ref_*.json"))
    
    if not artifact_files:
        report += "**No artifacts found.**\n\n"
        report += "Run the system with events to generate artifacts.\n"
        return report
    
    # Validate all artifacts
    results = []
    valid_count = 0
    invalid_count = 0
    warning_count = 0
    
    for artifact_path in sorted(artifact_files):
        is_valid, result = validate_artifact(artifact_path)
        results.append(result)
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
        if result["warnings"]:
            warning_count += 1
    
    report += f"""| Metric | Value |
|--------|-------|
| Total artifacts | {len(artifact_files)} |
| Valid | {valid_count} |
| Invalid | {invalid_count} |
| With warnings | {warning_count} |

---

## 2. Validation Checks

Each artifact is checked for:

| Check | Description |
|-------|-------------|
| ID | Unique job_id present |
| Timestamp | Valid created_at timestamp |
| Source event reference | input_evidence.event_type present |
| Content length | findings/proposals present |
| Metadata completeness | All required fields present |

---

## 3. Detailed Results

"""
    
    # Statistics
    total_findings = sum(r["checks"].get("findings_count", 0) for r in results)
    total_proposals = sum(r["checks"].get("proposals_count", 0) for r in results)
    avg_confidence = sum(r["checks"].get("confidence", 0) for r in results) / max(1, len(results))
    
    report += f"""### 3.1 Content Statistics

| Metric | Value |
|--------|-------|
| Total findings | {total_findings} |
| Total proposals | {total_proposals} |
| Average confidence | {avg_confidence:.2f} |

"""
    
    # Status distribution
    status_counts = Counter(r["checks"].get("status", "unknown") for r in results)
    report += "### 3.2 Status Distribution\n\n"
    for status, count in status_counts.most_common():
        report += f"- {status}: {count}\n"
    
    # Event type distribution
    event_types = []
    for r in results:
        # Try to get event_type from the raw data
        try:
            with open(r["path"]) as f:
                data = json.load(f)
                event_type = data.get("input_evidence", {}).get("event_type", "unknown")
                event_types.append(event_type)
        except:
            event_types.append("unknown")
    
    event_type_counts = Counter(event_types)
    report += "\n### 3.3 Event Type Distribution\n\n"
    for event_type, count in event_type_counts.most_common():
        report += f"- {event_type}: {count}\n"
    
    # Invalid artifacts
    invalid_results = [r for r in results if not r["valid"]]
    if invalid_results:
        report += "\n### 3.4 Invalid Artifacts\n\n"
        for r in invalid_results:
            report += f"**{Path(r['path']).name}:**\n"
            for error in r["errors"]:
                report += f"- ❌ {error}\n"
            report += "\n"
    
    # Warnings
    warning_results = [r for r in results if r["warnings"]]
    if warning_results:
        report += "\n### 3.5 Warnings\n\n"
        for r in warning_results[:5]:  # Limit to first 5
            report += f"**{Path(r['path']).name}:**\n"
            for warning in r["warnings"]:
                report += f"- ⚠️ {warning}\n"
            report += "\n"
    
    # Verbose output
    if verbose:
        report += "\n---\n\n## 4. All Artifacts (Verbose)\n\n"
        for r in results:
            report += f"### {Path(r['path']).name}\n\n"
            report += f"- Valid: {r['valid']}\n"
            for key, value in r["checks"].items():
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value) if value else "(none)"
                report += f"- {key}: {value}\n"
            report += "\n"
    
    # Integrity score
    integrity_score = valid_count / max(1, len(results))
    
    report += f"""---

## 5. Integrity Score

**{integrity_score:.1%}** ({valid_count}/{len(results)} artifacts valid)

"""
    
    if integrity_score >= 0.95:
        report += "✅ Excellent integrity. Artifacts are well-formed.\n"
    elif integrity_score >= 0.80:
        report += "⚠️ Good integrity. Some artifacts have issues.\n"
    else:
        report += "❌ Poor integrity. Many artifacts have issues.\n"
    
    return report


def main():
    parser = argparse.ArgumentParser(description="MVP15 Artifact Integrity Checker")
    parser.add_argument("--verbose", action="store_true", help="Show all artifact details")
    parser.add_argument("--save", action="store_true", help="Save report to file")
    args = parser.parse_args()
    
    report = generate_integrity_report(verbose=args.verbose)
    print(report)
    
    if args.save:
        report_path = ARTIFACTS_DIR / "MVP15_PERSISTENCE_INTEGRITY_REPORT.md"
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
