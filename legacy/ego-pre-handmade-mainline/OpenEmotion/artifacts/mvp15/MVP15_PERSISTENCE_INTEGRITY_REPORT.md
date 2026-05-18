# MVP15 Artifact Persistence Integrity Report

> Generated: 2026-03-23 00:05:01

---

## 1. Summary

| Metric | Value |
|--------|-------|
| Total artifacts | 13 |
| Valid | 13 |
| Invalid | 0 |
| With warnings | 0 |

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

### 3.1 Content Statistics

| Metric | Value |
|--------|-------|
| Total findings | 13 |
| Total proposals | 0 |
| Average confidence | 0.70 |

### 3.2 Status Distribution

- completed: 13

### 3.3 Event Type Distribution

- None: 12
- user_message: 1
---

## 5. Integrity Score

**100.0%** (13/13 artifacts valid)

✅ Excellent integrity. Artifacts are well-formed.
