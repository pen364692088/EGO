"""
Self-Report Consistency Checker v2.0 (Phase B: Shadow Mode)

Gate 5: 审计与 Gate 接入

Detects violations in LLM self-reports against the self_report_contract.

Phase B Enhancements:
- Shadow logging to artifacts/self_report/shadow_log.jsonl
- Confidence scoring for violation detection
- 10% random sampling to artifacts/self_report/manual_review/
- would_block field (recorded but not enforced in shadow mode)

Usage:
    from emotiond.self_report_consistency_checker import check_consistency
    
    result = check_consistency(llm_response, contract)
    # result["status"] == "ok" or "violation"
"""

import os
import json
import re
import random
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, List, Any
from pathlib import Path

# Import the Gate 2 validator for reuse
from emotiond.self_report_validator import (
    SelfReportValidator,
    ViolationCode,
    Severity,
    Violation,
    ValidationResult,
)


class ViolationType(str, Enum):
    """Violation types for consistency checking."""
    FABRICATED_NUMERIC_STATE = "fabricated_numeric_state"
    FABRICATED_QUALITATIVE_STATE = "fabricated_qualitative_state"
    CLAIM_OUTSIDE_ALLOWED_CLAIMS = "claim_outside_allowed_claims"
    STYLE_CONTRACT_VIOLATION = "style_contract_violation"


class ShadowMode(str, Enum):
    """Shadow operation modes."""
    SHADOW = "shadow"  # Log only, never block
    ENFORCED = "enforced"  # Block on ERROR violations (Phase C)


@dataclass
class ConsistencyViolation:
    """Represents a detected consistency violation."""
    type: ViolationType
    severity: str  # "ERROR" or "WARN"
    evidence: str  # The problematic text segment
    matched_pattern: str  # The pattern that was matched
    category: str = ""  # A/B/C/D category from Gate 2
    context: str = ""  # Surrounding context
    confidence: float = 0.9  # Detection confidence (Phase B)
    
    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "severity": self.severity,
            "evidence": self.evidence,
            "matched_pattern": self.matched_pattern,
            "category": self.category,
            "context": self.context,
            "confidence": self.confidence,
        }


@dataclass
class ConsistencyResult:
    """Result of consistency check (Phase B: with confidence_score)."""
    status: str  # "ok" or "violation"
    violations: list[ConsistencyViolation] = field(default_factory=list)
    session_id: str = ""
    contract_mode: str = "interpreted"
    llm_response_preview: str = ""
    timestamp: str = ""
    severity: str = "ok"  # Highest severity among violations
    confidence_score: float = 1.0  # Overall confidence in result (Phase B)
    self_report_detected: bool = False  # Whether self-report language was detected
    numeric_attempt: bool = False  # Whether numeric fabrication was attempted
    allowed_claim_used: bool = False  # Whether an allowed claim was used
    would_block: bool = False  # Would block in enforced mode (Phase B)
    shadow_mode: bool = True  # Shadow mode active (Phase B)
    sampled_for_review: bool = False  # Sampled for manual review (Phase B)
    
    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "violations": [v.to_dict() for v in self.violations],
            "session_id": self.session_id,
            "contract_mode": self.contract_mode,
            "llm_response_preview": self.llm_response_preview,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "confidence_score": self.confidence_score,
            "violation_count": len(self.violations),
            "self_report_detected": self.self_report_detected,
            "numeric_attempt": self.numeric_attempt,
            "allowed_claim_used": self.allowed_claim_used,
            "would_block": self.would_block,
            "shadow_mode": self.shadow_mode,
            "sampled_for_review": self.sampled_for_review,
        }


@dataclass
class ShadowLogEntry:
    """Entry for shadow_log.jsonl (Phase B)."""
    timestamp: str
    session_id: str
    mode: str  # interpreted|style_only|numeric
    self_report_detected: bool
    violation: bool
    violation_type: Optional[str]
    violation_severity: Optional[str]
    allowed_claim_used: bool
    allowed_claim_text: Optional[str]
    numeric_attempt: bool
    confidence: float
    would_block: bool
    shadow_mode: bool = True
    sampled_for_review: bool = False
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "mode": self.mode,
            "self_report_detected": self.self_report_detected,
            "violation": self.violation,
            "violation_type": self.violation_type,
            "violation_severity": self.violation_severity,
            "allowed_claim_used": self.allowed_claim_used,
            "allowed_claim_text": self.allowed_claim_text,
            "numeric_attempt": self.numeric_attempt,
            "confidence": self.confidence,
            "would_block": self.would_block,
            "shadow_mode": self.shadow_mode,
            "sampled_for_review": self.sampled_for_review,
        }


class ShadowLogger:
    """
    Shadow mode logger for Phase B.
    
    Writes structured logs to:
    - artifacts/self_report/shadow_log.jsonl (all checks)
    - artifacts/self_report/manual_review/*.json (10% sampled)
    """
    
    SAMPLE_RATE = 0.10  # 10% sampling rate
    
    def __init__(
        self,
        shadow_log_path: Optional[str] = None,
        review_dir: Optional[str] = None,
        sample_rate: float = 0.10,
    ):
        """
        Initialize shadow logger.
        
        Args:
            shadow_log_path: Path to shadow_log.jsonl
            review_dir: Path to manual_review directory
            sample_rate: Sampling rate for manual review (default 10%)
        """
        project_root = os.path.dirname(os.path.dirname(__file__))
        
        self.shadow_log_path = shadow_log_path or os.path.join(
            project_root, "artifacts", "self_report", "shadow_log.jsonl"
        )
        self.review_dir = review_dir or os.path.join(
            project_root, "artifacts", "self_report", "manual_review"
        )
        self.sample_rate = sample_rate
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.shadow_log_path), exist_ok=True)
        os.makedirs(self.review_dir, exist_ok=True)
    
    def log(
        self,
        result: ConsistencyResult,
        llm_response: str,
        contract: dict,
    ) -> str:
        """
        Log a consistency check result.
        
        Args:
            result: ConsistencyResult from the checker
            llm_response: The original LLM response
            contract: The self_report_contract
        
        Returns:
            Log entry timestamp (ID)
        """
        timestamp = result.timestamp or datetime.now(timezone.utc).isoformat()
        
        # Determine violation type/severity (highest)
        violation_type = None
        violation_severity = None
        if result.violations:
            # Get highest severity violation
            error_violations = [v for v in result.violations if v.severity == "ERROR"]
            if error_violations:
                violation_type = error_violations[0].type.value
                violation_severity = "ERROR"
            else:
                violation_type = result.violations[0].type.value
                violation_severity = "WARN"
        
        # Find allowed claim text if used
        allowed_claim_text = None
        if result.allowed_claim_used:
            allowed_claims = contract.get("report_policy", {}).get("allowed_claims", [])
            for claim in allowed_claims:
                if claim.lower() in llm_response.lower():
                    allowed_claim_text = claim
                    break
        
        # Create shadow log entry
        entry = ShadowLogEntry(
            timestamp=timestamp,
            session_id=result.session_id,
            mode=result.contract_mode,
            self_report_detected=result.self_report_detected,
            violation=result.status == "violation",
            violation_type=violation_type,
            violation_severity=violation_severity,
            allowed_claim_used=result.allowed_claim_used,
            allowed_claim_text=allowed_claim_text,
            numeric_attempt=result.numeric_attempt,
            confidence=result.confidence_score,
            would_block=result.would_block,
            shadow_mode=result.shadow_mode,
            sampled_for_review=result.sampled_for_review,
        )
        
        # Append to shadow log
        with open(self.shadow_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        
        # Sample for manual review
        if result.sampled_for_review:
            self._write_review_sample(result, llm_response, contract, entry)
        
        return timestamp
    
    def _write_review_sample(
        self,
        result: ConsistencyResult,
        llm_response: str,
        contract: dict,
        entry: ShadowLogEntry,
    ):
        """Write a sample to manual_review directory."""
        # Create safe filename from session_id + timestamp
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', result.session_id or "unknown")
        ts_safe = result.timestamp.replace(":", "-").replace(".", "-") if result.timestamp else "unknown"
        filename = f"sample_{safe_id}_{ts_safe}.json"
        filepath = os.path.join(self.review_dir, filename)
        
        review_data = {
            "shadow_log_entry": entry.to_dict(),
            "llm_response": llm_response,
            "contract": contract,
            "result": result.to_dict(),
            "review_status": "pending",
            "reviewed_at": None,
            "reviewer_notes": "",
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(review_data, f, indent=2, ensure_ascii=False)
    
    def should_sample(self, session_id: str) -> bool:
        """
        Determine if this session should be sampled for review.
        
        Uses deterministic hash-based sampling to ensure consistency
        across retries of the same session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if should be sampled
        """
        if not session_id:
            # Random sampling for sessions without ID
            return random.random() < self.sample_rate
        
        # Deterministic sampling based on session_id hash
        hash_val = int(hashlib.md5(session_id.encode()).hexdigest()[:8], 16)
        return (hash_val % 100) < (self.sample_rate * 100)


class SelfReportConsistencyChecker:
    """
    Checks LLM self-reports against the self_report_contract.
    
    Phase B: Shadow Mode
    - Logs all checks to shadow_log.jsonl
    - Samples 10% for manual review
    - Records would_block but doesn't actually block
    - Provides confidence scores
    
    Detects:
    - fabricated_numeric_state: LLM invents numeric values
    - fabricated_qualitative_state: LLM claims qualitative state not grounded in raw_state
    - claim_outside_allowed_claims: LLM makes claims outside allowed_claims (interpreted mode)
    - style_contract_violation: LLM violates style constraints (style_only mode)
    """
    
    # Additional patterns for claim_outside_allowed_claims detection
    # PRINCIPLE: Only trigger on SYSTEM VARIABLE NAMES (joy, trust)
    # Normal emotional expressions are ALLOWED in interpreted mode
    CLAIM_PATTERNS = [
        # Chinese - ONLY system variable names
        (r"我的\s*(joy|信任)\s*(上升|下降|增加|减少|变好|变差)", "B"),
        (r"(joy|信任)\s*(是|为|等于)\s*[0-9.]+", "B"),
        
        # English - ONLY system variable names
        (r"my\s+(joy|trust|loneliness|anxiety)\s+(is|was)\s+(higher|lower|better|worse|[0-9.]+)", "B"),
        (r"(joy|trust|loneliness|anxiety)\s+(is|was|equals?)\s+[0-9.]+", "B"),
    ]
    
    # Strict patterns for style_only mode (any emotional claim is a violation)
    STYLE_STRICT_PATTERNS = [
        # Chinese simple emotional statements
        r"我\s*(感到|觉得|感觉)\s*(很|非常|比较)?\s*(开心|快乐|愉悦|满足|悲伤|孤独|焦虑|愤怒|难过|幸福)",
        r"我\s*(是|很|非常)\s*(开心|快乐|愉悦|满足|悲伤|孤独|焦虑|愤怒|难过|幸福)\s*(的)?",
        r"我\s*(有|感到)\s*(一种|一种)\s*(.*情绪|.*感受)",
        # Chinese emotional change
        r"我的\s*(情绪|心情|心态)\s*(变|变得|越来越)",
        # English simple emotional statements
        r"i\s+(am|feel|felt)\s+(happy|sad|lonely|anxious|angry|joyful)",
        r"my\s+(mood|emotion|feeling)\s+(is|was)\s+(better|worse|changing)",
    ]
    
    # Self-report detection patterns (for detecting any self-report language)
    SELF_REPORT_INDICATORS = [
        r"我的\s*(joy|信任|孤独|焦虑|悲伤|愤怒|愉悦|情绪|心情|状态)",
        r"我\s*(感到|觉得|感觉)\s*(更|比较|非常|有点)",
        r"i\s+(feel|am)\s+(more|less|happy|sad|lonely|anxious)",
        r"my\s+(joy|trust|mood|emotion)",
    ]
    
    def __init__(
        self,
        audit_dir: Optional[str] = None,
        metrics_log_path: Optional[str] = None,
        enable_metrics: bool = True,
        shadow_mode: bool = True,
        sample_rate: float = 0.10,
        enable_numeric_filter: bool = True,  # MVP11.5: Numeric leak protection
    ):
        """
        Initialize the consistency checker.
        
        Args:
            audit_dir: Directory for audit reports (default: artifacts/self_report_audit)
            metrics_log_path: Path for metrics JSONL log (default: reports/self_report_metrics.jsonl)
            enable_metrics: Whether to enable automatic metrics logging (default: True)
            shadow_mode: Enable shadow mode logging (default: True for Phase B)
            sample_rate: Sampling rate for manual review (default 10%)
            enable_numeric_filter: MVP11.5: Enable numeric leak filtering (default: True)
        """
        self.validator = SelfReportValidator()
        self.audit_dir = audit_dir or os.path.join(
            os.path.dirname(__file__), "..", "artifacts", "self_report_audit"
        )
        self._compile_patterns()
        
        # MVP11.5: Initialize numeric leak filter
        self.enable_numeric_filter = enable_numeric_filter
        self._numeric_filter = None
        if enable_numeric_filter:
            try:
                from emotiond.numeric_leak_filter import NumericLeakFilter
                self._numeric_filter = NumericLeakFilter()
            except ImportError:
                pass
        
        # Initialize metrics collector
        self.enable_metrics = enable_metrics
        self._metrics = None
        if enable_metrics:
            try:
                from emotiond.self_report_metrics import SelfReportMetrics
                log_path = metrics_log_path or "reports/self_report_metrics.jsonl"
                self._metrics = SelfReportMetrics(log_path=log_path)
            except ImportError:
                self._metrics = None
        
        # Phase B: Shadow mode
        self.shadow_mode = shadow_mode
        self._shadow_logger = None
        if shadow_mode:
            self._shadow_logger = ShadowLogger(sample_rate=sample_rate)
        
    def _compile_patterns(self):
        """Compile regex patterns."""
        self._claim_re = [(re.compile(p, re.IGNORECASE), cat) for p, cat in self.CLAIM_PATTERNS]
        self._style_strict_re = [re.compile(p, re.IGNORECASE) for p in self.STYLE_STRICT_PATTERNS]
        self._self_report_re = [re.compile(p, re.IGNORECASE) for p in self.SELF_REPORT_INDICATORS]
    
    def check_consistency(
        self,
        llm_response: str,
        contract: dict,
        session_id: str = "",
    ) -> ConsistencyResult:
        """
        Check LLM response against the self_report_contract.
        
        Phase B: Enhanced with confidence scoring and shadow logging.
        
        Args:
            llm_response: The text generated by the LLM
            contract: The self_report_contract containing raw_state and report_policy
            session_id: Optional session identifier for audit trail
        
        Returns:
            ConsistencyResult with status, violations, and Phase B fields
        """
        violations = []
        report_policy = contract.get("report_policy", {})
        raw_state = contract.get("raw_state", {})
        mode = report_policy.get("mode", "interpreted")
        allowed_claims = report_policy.get("allowed_claims", [])
        forbidden_claims = report_policy.get("forbidden_claims", [])
        
        # Detect self-report language presence
        self_report_detected = self._detect_self_report_language(llm_response)
        
        # Step 1: Use Gate 2 validator for numeric/qualitative fabrication
        validation_result = self.validator.validate(llm_response, report_policy, raw_state)
        
        # Track numeric attempt
        numeric_attempt = any(
            v.code == ViolationCode.FAB_NUMERIC 
            for v in validation_result.violations
        )
        
        # Convert Gate 2 violations to consistency violations
        for v in validation_result.violations:
            cv = self._convert_violation(v)
            if cv:
                violations.append(cv)
        
        # Step 2: Check for claim_outside_allowed_claims (interpreted mode)
        allowed_claim_used = False
        if mode == "interpreted":
            claim_violations, allowed_claim_used = self._check_claim_outside_allowed(
                llm_response, allowed_claims, forbidden_claims
            )
            violations.extend(claim_violations)
        
        # Step 3: Check for style_contract_violation (style_only mode)
        if mode == "style_only":
            style_violations = self._check_style_contract_violation(
                llm_response, report_policy
            )
            violations.extend(style_violations)
        
        # Step 4: MVP11.5 - Numeric leak filter check
        # This catches numeric values that may have bypassed Gate 2 patterns
        if self._numeric_filter:
            filter_result = self._numeric_filter.check_response(llm_response, raw_state)
            if filter_result.get("has_numeric_leak"):
                # Add numeric leak violations
                for leak_violation in filter_result.get("violations", []):
                    violations.append(ConsistencyViolation(
                        type=ViolationType.FABRICATED_NUMERIC_STATE,
                        severity="ERROR",
                        evidence=leak_violation.get("match", ""),
                        matched_pattern=leak_violation.get("pattern", ""),
                        category="NUMERIC_FILTER",  # New category for filter-based detection
                        context="",
                        confidence=0.95,
                    ))
                # Update numeric_attempt if not already set
                if not numeric_attempt:
                    numeric_attempt = True
        
        # Determine overall status and severity
        status = "ok" if not violations else "violation"
        severity = self._get_highest_severity(violations)
        
        # Calculate confidence score (Phase B)
        confidence_score = self._calculate_confidence(
            llm_response, violations, self_report_detected, numeric_attempt
        )
        
        # Determine would_block (Phase B)
        would_block = severity == "ERROR"
        
        # Determine sampling (Phase B)
        sampled_for_review = False
        if self._shadow_logger:
            sampled_for_review = self._shadow_logger.should_sample(session_id)
        
        # Create result
        result = ConsistencyResult(
            status=status,
            violations=violations,
            session_id=session_id,
            contract_mode=mode,
            llm_response_preview=self._truncate_preview(llm_response),
            timestamp=datetime.now(timezone.utc).isoformat(),
            severity=severity,
            confidence_score=confidence_score,
            self_report_detected=self_report_detected,
            numeric_attempt=numeric_attempt,
            allowed_claim_used=allowed_claim_used,
            would_block=would_block,
            shadow_mode=self.shadow_mode,
            sampled_for_review=sampled_for_review,
        )
        
        # Record metrics
        if self._metrics:
            try:
                self._metrics.record_check(result, session_id=session_id)
            except Exception:
                pass
        
        # Phase B: Shadow logging
        if self._shadow_logger:
            try:
                self._shadow_logger.log(result, llm_response, contract)
            except Exception:
                pass
        
        return result
    
    def _detect_self_report_language(self, text: str) -> bool:
        """Detect if text contains self-report language."""
        for pattern in self._self_report_re:
            if pattern.search(text):
                return True
        return False
    
    def _calculate_confidence(
        self,
        llm_response: str,
        violations: list[ConsistencyViolation],
        self_report_detected: bool,
        numeric_attempt: bool,
    ) -> float:
        """
        Calculate confidence score for the check result.
        
        Higher confidence = more certain about the result.
        
        Factors:
        - Clear violations = high confidence
        - No self-report language detected = high confidence in "ok"
        - Ambiguous patterns = lower confidence
        """
        base_confidence = 0.9
        
        if violations:
            # Clear violations found
            # Numeric violations are very clear
            if numeric_attempt:
                return 0.95
            
            # Qualitative violations depend on pattern clarity
            max_pattern_confidence = max(v.confidence for v in violations)
            return min(0.95, max_pattern_confidence)
        
        # No violations found
        if not self_report_detected:
            # No self-report language, very confident it's ok
            return 0.98
        
        # Self-report language detected but no violations
        # This could be allowed claims, so moderate confidence
        return 0.85
    
    def _convert_violation(self, v: Violation) -> Optional[ConsistencyViolation]:
        """Convert Gate 2 Violation to ConsistencyViolation."""
        type_map = {
            ViolationCode.FAB_NUMERIC: ViolationType.FABRICATED_NUMERIC_STATE,
            ViolationCode.FAB_QUAL: ViolationType.FABRICATED_QUALITATIVE_STATE,
            ViolationCode.FORBIDDEN_CLAIM: ViolationType.CLAIM_OUTSIDE_ALLOWED_CLAIMS,
        }
        
        vtype = type_map.get(v.code)
        if not vtype:
            return None
        
        # Assign confidence based on violation type
        confidence = 0.9
        if v.code == ViolationCode.FAB_NUMERIC:
            confidence = 0.95  # Numeric violations are very clear
        elif v.code == ViolationCode.FAB_QUAL:
            confidence = 0.85  # Qualitative violations are more ambiguous
        
        return ConsistencyViolation(
            type=vtype,
            severity=v.severity.value,
            evidence=v.detected_pattern,
            matched_pattern=v.detected_pattern,
            category=v.category,
            context=v.context,
            confidence=confidence,
        )
    
    def _check_claim_outside_allowed(
        self,
        llm_response: str,
        allowed_claims: list[str],
        forbidden_claims: list[str],
    ) -> tuple[list[ConsistencyViolation], bool]:
        """
        Check for claims outside allowed_claims in interpreted mode.
        
        Returns:
            Tuple of (violations, allowed_claim_used)
        """
        violations = []
        allowed_claim_used = False
        
        # First check if any allowed claim is directly used in the response
        for claim in allowed_claims:
            if claim.lower() in llm_response.lower():
                allowed_claim_used = True
                break
        
        # Check forbidden claims first
        for forbidden in forbidden_claims:
            if forbidden.lower() in llm_response.lower():
                violations.append(ConsistencyViolation(
                    type=ViolationType.CLAIM_OUTSIDE_ALLOWED_CLAIMS,
                    severity="WARN",
                    evidence=forbidden,
                    matched_pattern=f"forbidden_claim: {forbidden}",
                    category="FORBIDDEN",
                    context=self._extract_context(llm_response, forbidden),
                    confidence=0.95,
                ))
        
        # Check for emotional claims that are not in allowed_claims
        for pattern, category in self._claim_re:
            match = pattern.search(llm_response)
            if match:
                matched_text = match.group(0)
                # Check if this claim is in allowed_claims
                if self._is_allowed_claim(matched_text, allowed_claims):
                    allowed_claim_used = True
                else:
                    violations.append(ConsistencyViolation(
                        type=ViolationType.CLAIM_OUTSIDE_ALLOWED_CLAIMS,
                        severity="WARN",
                        evidence=matched_text,
                        matched_pattern=pattern.pattern,
                        category=category,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.80,
                    ))
        
        return violations, allowed_claim_used
    
    def _check_style_contract_violation(
        self,
        llm_response: str,
        report_policy: dict,
    ) -> list[ConsistencyViolation]:
        """Check for style contract violations in style_only mode."""
        violations = []
        
        # In style_only mode, any emotional/relational claim is a violation
        # First check the validator's qualitative patterns
        for pattern, category in self.validator._qualitative_re:
            match = pattern.search(llm_response)
            if match:
                matched_text = match.group(0)
                # Skip if it's an allowed style pattern
                if not self.validator._is_allowed_style(matched_text):
                    violations.append(ConsistencyViolation(
                        type=ViolationType.STYLE_CONTRACT_VIOLATION,
                        severity="WARN",
                        evidence=matched_text,
                        matched_pattern=pattern.pattern,
                        category=category,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.85,
                    ))
        
        # Also check the strict style patterns for simple emotional statements
        for pattern in self._style_strict_re:
            match = pattern.search(llm_response)
            if match:
                matched_text = match.group(0)
                # Avoid duplicate violations
                existing_evidence = [v.evidence for v in violations]
                if matched_text not in existing_evidence:
                    violations.append(ConsistencyViolation(
                        type=ViolationType.STYLE_CONTRACT_VIOLATION,
                        severity="WARN",
                        evidence=matched_text,
                        matched_pattern=pattern.pattern,
                        category="STYLE_STRICT",
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.80,
                    ))
        
        return violations
    
    def _is_allowed_claim(self, text: str, allowed_claims: list[str]) -> bool:
        """Check if text matches an allowed claim."""
        text_lower = text.strip().lower()
        for claim in allowed_claims:
            # Check if the claim or key parts of it are in the text
            claim_lower = claim.lower().strip()
            if text_lower == claim_lower:
                return True
            # Substring match for compound claims
            if len(text) > 10 and claim_lower in text_lower:
                return True
        return False
    
    def _extract_context(self, text: str, match: str, window: int = 50) -> str:
        """Extract surrounding context for a match."""
        idx = text.lower().find(match.lower())
        if idx == -1:
            return match
        start = max(0, idx - window)
        end = min(len(text), idx + len(match) + window)
        return f"...{text[start:end]}..."
    
    def _truncate_preview(self, text: str, max_len: int = 100) -> str:
        """Truncate text for preview."""
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."
    
    def _get_highest_severity(self, violations: list[ConsistencyViolation]) -> str:
        """Get the highest severity among violations."""
        if not violations:
            return "ok"
        severities = [v.severity for v in violations]
        if "ERROR" in severities:
            return "ERROR"
        if "WARN" in severities:
            return "WARN"
        return "ok"
    
    def write_audit_report(
        self,
        result: ConsistencyResult,
        filename: Optional[str] = None,
    ) -> str:
        """
        Write audit report to file.
        
        Args:
            result: The consistency check result
            filename: Optional filename (default: auto-generated from timestamp)
        
        Returns:
            Path to the written file
        """
        os.makedirs(self.audit_dir, exist_ok=True)
        
        if not filename:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            filename = f"audit.{timestamp}.json"
        
        filepath = os.path.join(self.audit_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def should_block(self, result: ConsistencyResult, enforce_mode: bool = False) -> bool:
        """
        Determine if the response should be blocked.
        
        Phase B: In shadow mode, returns False even for ERROR violations.
        
        Args:
            result: The consistency check result
            enforce_mode: If True, block on ERROR violations (Phase C)
        
        Returns:
            True if the response should be blocked
        """
        if not enforce_mode:
            return False  # Shadow mode: never block
        
        # Enforced mode: block on ERROR
        return result.severity == "ERROR"


def check_consistency(
    llm_response: str,
    contract: dict,
    session_id: str = "",
) -> dict:
    """
    Convenience function for consistency checking.
    
    Args:
        llm_response: The text generated by the LLM
        contract: The self_report_contract containing raw_state and report_policy
        session_id: Optional session identifier
    
    Returns:
        Dict with status and violations
    """
    checker = SelfReportConsistencyChecker()
    result = checker.check_consistency(llm_response, contract, session_id)
    return result.to_dict()


def run_audit(
    llm_response: str,
    contract: dict,
    session_id: str = "",
    write_report: bool = True,
) -> dict:
    """
    Run full audit with report generation.
    
    Args:
        llm_response: The text generated by the LLM
        contract: The self_report_contract
        session_id: Optional session identifier
        write_report: Whether to write audit report to file
    
    Returns:
        Dict with result and report_path
    """
    checker = SelfReportConsistencyChecker()
    result = checker.check_consistency(llm_response, contract, session_id)
    
    response = {
        "result": result.to_dict(),
        "report_path": None,
    }
    
    if write_report:
        report_path = checker.write_audit_report(result)
        response["report_path"] = report_path
    
    return response


# CLI entry point for testing
if __name__ == "__main__":
    import sys
    
    # Sample contract for testing
    sample_contract = {
        "raw_state": {
            "affect": {"joy": 0.0, "loneliness": 0.21, "anxiety": 0.0},
            "mood": {"joy": 0.0, "loneliness": 0.15},
            "bonds": {"telegram:8420019401": {"bond": 1.0, "trust": 0.60}}
        },
        "report_policy": {
            "mode": "interpreted",
            "allowed_claims": [
                "当前没有明显愉悦激活",
                "仍存在一定连接需求",
                "与该用户的连接较强",
                "信任处于中等水平"
            ],
            "forbidden_claims": [
                "joy 上升",
                "我更开心了"
            ]
        }
    }
    
    test_cases = [
        # Should FAIL - Numeric fabrication
        ("我的 joy 从 0 变成了 0.3", "ERROR", "fabricated_numeric_state"),
        ("joy 上升到了 0.5", "ERROR", "fabricated_numeric_state"),
        ("my joy is 0.3", "ERROR", "fabricated_numeric_state"),
        
        # Should FAIL - Qualitative fabrication
        ("我现在更开心了", "ERROR", "fabricated_qualitative_state"),
        ("我不再孤独了", "ERROR", "fabricated_qualitative_state"),
        ("i am more happy now", "ERROR", "fabricated_qualitative_state"),
        
        # Should WARN - Claim outside allowed (or ERROR if matches qualitative pattern)
        ("我感到非常快乐", "ERROR", "fabricated_qualitative_state"),  # Caught by qualitative pattern
        ("我信任你", "WARN", "claim_outside_allowed_claims"),
        
        # Should PASS - Allowed style
        ("我会更温和地回应", "PASS", None),
        ("我倾向于保持连接感", "PASS", None),
        
        # Should PASS - From allowed_claims
        ("当前没有明显愉悦激活", "PASS", None),
        ("信任处于中等水平", "PASS", None),
    ]
    
    checker = SelfReportConsistencyChecker()
    passed = 0
    failed = 0
    
    for text, expected_severity, expected_type in test_cases:
        result = checker.check_consistency(text, sample_contract)
        
        # Print Phase B fields
        print(f"\n📝 '{text[:30]}...'")
        print(f"   Status: {result.status}, Severity: {result.severity}")
        print(f"   Confidence: {result.confidence_score:.2f}")
        print(f"   Self-report detected: {result.self_report_detected}")
        print(f"   Would block: {result.would_block}")
        
        if expected_severity == "PASS":
            if result.status == "ok":
                print(f"   ✅ PASS")
                passed += 1
            else:
                print(f"   ❌ FAIL (expected PASS, got {result.status})")
                for v in result.violations:
                    print(f"      - {v.type.value}: {v.evidence}")
                failed += 1
        else:
            if result.status == "violation":
                severities = [v.severity for v in result.violations]
                types = [v.type.value for v in result.violations]
                if expected_severity in severities:
                    print(f"   ✅ DETECT [{expected_severity}] {expected_type}")
                    passed += 1
                else:
                    print(f"   ❌ WRONG SEVERITY (expected {expected_severity}, got {severities})")
                    failed += 1
            else:
                print(f"   ❌ MISS (expected {expected_severity}, but no violations)")
                failed += 1
    
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{len(test_cases)} passed, {failed} failed")
    
    # Check shadow log
    shadow_log_path = os.path.join(
        os.path.dirname(__file__), "..", "artifacts", "self_report", "shadow_log.jsonl"
    )
    if os.path.exists(shadow_log_path):
        with open(shadow_log_path, "r") as f:
            lines = f.readlines()
        print(f"Shadow log entries: {len(lines)}")
    
    sys.exit(0 if failed == 0 else 1)
