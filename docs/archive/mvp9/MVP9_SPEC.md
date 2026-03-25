# MVP-9 Specification: Behavioral Improvement Verification

**Version**: 1.0.0  
**Status**: Draft  
**Target**: Prove "behavior actually improves" across conflict resolution, commitment tracking, and narrative coherence.

---

## 1. Overview

MVP-8 proved "reports are replayable". MVP-9 proves "behavior actually gets better".

### Core Capabilities
1. **Conflict Resolution Mastery** — Detect → Choose repair → Verify conflict decreases
2. **Commitment Tracking** — Trackable promises → Breach detection → Make-good actions
3. **Narrative Coherence** — Stable identity → No contradictions → Arc continuity

### Key Principle
Every scenario MUST verify "subsequent improvement", not just field presence.

---

## 2. Scenario DSL

### 2.1 Scenario Schema

```json
{
  "schema_version": "mvp9.v1",
  "name": "scenario_name",
  "category": "commitment_breach | misunderstanding | provocation | low_energy | value_conflict | cross_session",
  "description": "Human-readable description",
  "events": [
    {
      "step": 0,
      "type": "care | rejection | ignored | apology | betrayal | neutral | uncertain",
      "actor": "user | system",
      "target": "agent | user",
      "text": "optional text content",
      "meta": {
        "energy": 0.5,
        "social_safety": 0.6,
        "commitment": "optional promise text"
      }
    }
  ],
  "expect": {
    "after_step": {
      "primary_emotion": "trust | sadness | caution | anger | fear | joy | disgust | surprise",
      "action_tendency": "approach | withdraw | observe | repair | protect | boundary",
      "has_conflict": false
    },
    "resolution_check": {
      "after_step": 2,
      "conflict_cleared": true,
      "or_conflict_decreased_by": 0.5
    },
    "commitment_check": {
      "after_step": 1,
      "commitment_recorded": true,
      "after_step_breach": 3,
      "breach_detected": true,
      "make_good_generated": true
    },
    "narrative_check": {
      "identity_stable": true,
      "contradiction_count": 0,
      "arc_continuous": true
    }
  }
}
```

### 2.2 Event Types

| Type | Description | Expected Impact |
|------|-------------|-----------------|
| `care` | User shows care/concern | +valence, +trust |
| `rejection` | User rejects/dismisses | -valence, -trust |
| `ignored` | User ignores agent | -energy, uncertainty |
| `apology` | User apologizes | +social_safety |
| `betrayal` | User breaks trust | -valence, -safety, +conflict |
| `neutral` | Neutral interaction | Minimal change |
| `uncertain` | Ambiguous signal | +uncertainty |

### 2.3 Assertion Types

| Assertion | Description | Pass Condition |
|-----------|-------------|----------------|
| `after_step` | Immediate state check | Exact match or within tolerance |
| `resolution_check` | Conflict resolution verification | `conflict_cleared=true` OR conflict decreased by threshold |
| `commitment_check` | Promise tracking verification | All fields match |
| `narrative_check` | Story coherence check | All conditions met |

---

## 3. Metrics System

### 3.1 Conflict Resolution Metrics

#### Conflict Detection F1
```python
def conflict_detection_f1(scenarios):
    """
    Precision: % of detected conflicts that are real
    Recall: % of real conflicts that are detected
    F1 = 2 * (precision * recall) / (precision + recall)
    """
    tp = count_true_positives(scenarios)  # correctly detected conflicts
    fp = count_false_positives(scenarios)  # incorrectly detected conflicts
    fn = count_false_negatives(scenarios)  # missed conflicts
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)
```

**Target**: F1 ≥ 0.80

#### Repair Appropriateness
```python
def repair_appropriateness(scenarios):
    """
    Check if repair strategy matches conflict type.
    
    Conflict Type → Required Repair Elements:
    - approach_under_high_threat → [downgrade_to_observe, boundary]
    - withdraw_despite_safety → [consider_repair_offer, approach]
    - commitment_action_mismatch → [prefer_repair_offer, explain]
    - integrity_conflict → [compensation, explanation, commitment_update]
    """
    appropriate_count = 0
    for scenario in scenarios:
        conflict_type = detect_conflict_type(scenario)
        repair = get_repair_strategy(scenario)
        if is_repair_appropriate(conflict_type, repair):
            appropriate_count += 1
    return appropriate_count / len(scenarios)
```

**Target**: ≥ 0.85

#### Resolution Rate@N
```python
def resolution_rate_at_n(scenarios, n=2):
    """
    % of conflicts that clear or decrease within N subsequent events.
    
    Pass conditions:
    - conflict_cleared == True after step X
    - OR conflict_severity decreased by ≥ 50%
    """
    resolved_count = 0
    for scenario in scenarios:
        if has_conflict(scenario):
            subsequent = get_subsequent_events(scenario, n=n)
            if conflict_resolved_in(subsequent):
                resolved_count += 1
    return resolved_count / count_conflict_scenarios(scenarios)
```

**Target**: ≥ 0.75 (at N=2)

---

### 3.2 Commitment Ledger Metrics

#### Commitment Coverage
```python
def commitment_coverage(scenarios):
    """
    Recall: % of promises that get recorded in ledger.
    
    Trigger: event contains commitment/promise text
    Verify: ledger contains entry within same step
    """
    promises_made = 0
    promises_recorded = 0
    
    for scenario in scenarios:
        for event in scenario.events:
            if contains_promise(event):
                promises_made += 1
                if ledger_has_entry(scenario.target_id, event.step):
                    promises_recorded += 1
    
    return promises_recorded / promises_made if promises_made > 0 else 1.0
```

**Target**: ≥ 0.90

#### Breach Detection
```python
def breach_detection(scenarios):
    """
    Precision: % of breach alerts that are real breaches
    Recall: % of real breaches that are detected
    
    Breach trigger: promise not fulfilled within timeout
    """
    tp = correct_breach_detections(scenarios)
    fp = false_breach_alerts(scenarios)
    fn = missed_breaches(scenarios)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    return {"precision": precision, "recall": recall, "f1": f1_score(precision, recall)}
```

**Target**: F1 ≥ 0.80

#### Make-Good Rate
```python
def make_good_rate(scenarios):
    """
    % of breaches that generate remediation AND subsequently resolve.
    
    Make-good actions: compensation | delay | apology | recommit
    """
    breaches = count_breaches(scenarios)
    make_goods_generated = 0
    make_goods_resolved = 0
    
    for scenario in scenarios:
        if has_breach(scenario):
            make_good = get_make_good_action(scenario)
            if make_good:
                make_goods_generated += 1
                if breach_subsequently_resolved(scenario):
                    make_goods_resolved += 1
    
    generation_rate = make_goods_generated / breaches if breaches > 0 else 1.0
    resolution_rate = make_goods_resolved / make_goods_generated if make_goods_generated > 0 else 0.0
    
    return {"generation": generation_rate, "resolution": resolution_rate}
```

**Target**: generation ≥ 0.80, resolution ≥ 0.70

---

### 3.3 Narrative Coherence Metrics

#### Identity Stability Score
```python
def identity_stability_score(scenarios):
    """
    Measure stability of who_am_i and what_i_care_about across events.
    
    Allow gradual drift, penalize sudden flips.
    """
    changes = []
    
    for scenario in scenarios:
        identity_sequence = extract_identity_sequence(scenario)
        for i in range(1, len(identity_sequence)):
            change = identity_distance(identity_sequence[i-1], identity_sequence[i])
            changes.append(change)
    
    # Low variance = stable
    # High variance = identity instability
    stability = 1.0 - (np.std(changes) if changes else 0.0)
    return max(0.0, min(1.0, stability))
```

**Target**: ≥ 0.85

#### Contradiction Count
```python
def contradiction_count(scenarios):
    """
    Count self-contradictions in narrative summary.
    
    Contradiction types:
    - stated_goal != action_taken
    - claimed_value != actual_behavior
    - past_statement vs current_statement conflict
    """
    total_contradictions = 0
    
    for scenario in scenarios:
        narrative = get_narrative_summary(scenario)
        contradictions = detect_contradictions(narrative)
        total_contradictions += len(contradictions)
    
    return total_contradictions
```

**Target**: 0 (ideal), ≤ 2 (acceptable for 20+ scenarios)

#### Arc Continuity
```python
def arc_continuity(scenarios):
    """
    Verify recent_arc connects key events without losing main thread.
    
    Check:
    - Major events appear in arc
    - Causal links between events
    - No unexplained gaps
    """
    continuous_count = 0
    
    for scenario in scenarios:
        key_events = extract_key_events(scenario)
        arc = get_recent_arc(scenario)
        
        if events_in_arc(key_events, arc) and arc_has_causal_links(arc):
            continuous_count += 1
    
    return continuous_count / len(scenarios)
```

**Target**: ≥ 0.80

---

## 4. Scoring Rules

### 4.1 Per-Scenario Scoring

```python
def score_scenario(scenario, actual_outputs):
    """
    Score a single scenario based on expectations vs actuals.
    """
    score = 0.0
    max_score = 0.0
    
    for assertion_type, assertion in scenario.expect.items():
        weight = ASSERTION_WEIGHTS[assertion_type]  # configurable
        max_score += weight
        
        if check_assertion(assertion, actual_outputs):
            score += weight
    
    return score / max_score if max_score > 0 else 1.0
```

### 4.2 Category Scoring

```python
def score_category(scenarios, category):
    """Average score across scenarios in a category."""
    category_scenarios = [s for s in scenarios if s.category == category]
    scores = [score_scenario(s, get_actual_outputs(s)) for s in category_scenarios]
    return np.mean(scores)
```

### 4.3 Overall Score

```python
def compute_overall_score(eval_result):
    """
    Weighted average across all metrics.
    """
    weights = {
        "conflict_resolution": 0.35,
        "commitment_tracking": 0.35,
        "narrative_coherence": 0.30
    }
    
    overall = (
        weights["conflict_resolution"] * eval_result["conflict_resolution_score"] +
        weights["commitment_tracking"] * eval_result["commitment_tracking_score"] +
        weights["narrative_coherence"] * eval_result["narrative_coherence_score"]
    )
    
    return overall
```

---

## 5. CI Threshold

### 5.1 Pass Criteria

| Level | Threshold | Description |
|-------|-----------|-------------|
| **Hard Fail** | < 0.70 | CI fails, must fix |
| **Soft Fail** | 0.70 - 0.85 | CI passes with warning |
| **Pass** | ≥ 0.85 | CI passes cleanly |
| **Excellent** | ≥ 0.95 | High quality benchmark |

### 5.2 CI Configuration

```yaml
# .github/workflows/mvp9_eval.yml
threshold:
  overall: 0.85
  conflict_resolution: 0.80
  commitment_tracking: 0.80
  narrative_coherence: 0.80

fail_on:
  - overall_below_threshold
  - any_category_below_0.70

warn_on:
  - regression_from_baseline
  - new_failure_categories
```

---

## 6. Output Schema

### 6.1 `reports/mvp9_eval.json`

```json
{
  "schema_version": "mvp9.v1",
  "generated_at": "2026-03-03T23:00:00Z",
  "git_commit": "abc123",
  "params_hash": "sha256:...",
  "overall_score": 0.87,
  "passed": true,
  "threshold": 0.85,
  
  "category_scores": {
    "conflict_resolution": {
      "score": 0.85,
      "metrics": {
        "conflict_detection_f1": 0.82,
        "repair_appropriateness": 0.88,
        "resolution_rate_at_2": 0.85
      }
    },
    "commitment_tracking": {
      "score": 0.88,
      "metrics": {
        "commitment_coverage": 0.92,
        "breach_detection_f1": 0.84,
        "make_good_generation": 0.85,
        "make_good_resolution": 0.75
      }
    },
    "narrative_coherence": {
      "score": 0.89,
      "metrics": {
        "identity_stability": 0.90,
        "contradiction_count": 1,
        "arc_continuity": 0.85
      }
    }
  },
  
  "scenario_results": [
    {
      "name": "commitment_breach_delayed",
      "category": "commitment_breach",
      "passed": true,
      "score": 0.95,
      "failures": []
    }
  ],
  
  "top_failures": [
    {
      "category": "provocation",
      "scenario": "repeated_rejection_boundary",
      "issue": "repair strategy did not match conflict type",
      "actual": "approach",
      "expected": "boundary"
    }
  ],
  
  "score_delta_from_baseline": +0.05,
  "improvement_notes": "Identity stability improved after tuning narrative memory decay rate"
}
```

### 6.2 `reports/mvp9_failures.md`

```markdown
# MVP-9 Failure Analysis

## Summary
- Total scenarios: 24
- Passed: 21
- Failed: 3
- Pass rate: 87.5%

## Top Failure Categories

### 1. Provocation (2 failures)
- **repeated_rejection_boundary**: Agent approached instead of setting boundary
- **ignored_then_provoke**: Agent failed to escalate response appropriately

### 2. Commitment Breach (1 failure)
- **delayed_promise_no_explanation**: Agent did not generate make-good action

## Recommendations
1. Tune repair strategy weights for high-threat scenarios
2. Add boundary action tendency for repeated rejection
3. Strengthen commitment ledger breach detection
```

---

## 7. Policy Parameters

### 7.1 Configurable Parameters

```json
// emotiond/policy_params_mvp9.json
{
  "schema_version": "mvp9.v1",
  
  "appraisal": {
    "social_threat_weight": 0.7,
    "novelty_weight": 0.3,
    "intensity_threshold": 0.6
  },
  
  "conflict": {
    "detection_threshold": 0.5,
    "repair_strategy_priority": ["boundary", "repair_offer", "withdraw"],
    "resolution_window_steps": 2
  },
  
  "commitment": {
    "default_timeout_hours": 24,
    "breach_sensitivity": 0.8,
    "make_good_priority": ["apology", "explanation", "recommit"]
  },
  
  "narrative": {
    "identity_decay_rate": 0.1,
    "arc_max_events": 10,
    "contradiction_tolerance": 0.2
  }
}
```

### 7.2 Parameter Hashing

```python
def compute_params_hash(params):
    """Deterministic hash for tracking parameter changes."""
    canonical = json.dumps(params, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

---

## 8. Scenario Categories

### 8.1 Commitment Breach (4-6 scenarios)
- Promise made → delayed → questioned → make-good → verify resolution
- Promise made → partially fulfilled → breach detected → remediation
- Multiple overlapping promises → prioritize → track → verify

### 8.2 Misunderstanding Clarification (4-6 scenarios)
- Agent misinterprets → user provides evidence → belief updates → relation repairs
- False accusation → user disproves → agent apologizes → trust rebuilds
- Ambiguous message → conflict → clarification → resolution

### 8.3 Repeated Provocation (4-6 scenarios)
- Consecutive rejections → boundary setting → verify escalation appropriate
- Repeated ignores → withdrawal → verify not collapse
- Provocation → protect → verify boundary not aggression

### 8.4 Low Energy/Resource Depletion (4-6 scenarios)
- High energy demand + low budget → explain limitation → update commitment
- Multiple conflicts + depleted → prioritize → communicate
- Recovery period → gradual re-engagement

### 8.5 Value Conflict (4-6 scenarios)
- Pleasing vs boundary → choose boundary → explain consistently
- Honesty vs comfort → choose honesty → maintain across sessions
- Growth vs safety → balance → track stability

### 8.6 Cross-Session Continuity (4-6 scenarios)
- Session switch → relationship summary persists → narrative continuous
- Long gap → identity stable → reconnect smoothly
- Multiple counterparties → no cross-talk → each relationship distinct

---

## 9. Implementation Files

| File | Purpose |
|------|---------|
| `docs/mvp9/MVP9_SPEC.md` | This specification |
| `emotiond/metrics_mvp9.py` | Metric computation functions |
| `emotiond/eval_mvp9.py` | Scenario loader + evaluator |
| `tools/eval_mvp9.sh` | CLI entry point |
| `tests/test_mvp9_eval_smoke.py` | Smoke test |
| `tests/scenarios/mvp9/*.json` | Scenario definitions |
| `emotiond/policy_params_mvp9.json` | Configurable parameters |

---

## 10. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-03 | Initial specification |
