# Test Governance Framework

## Purpose
Establish clear policies and processes for managing skipped tests in the OpenEmotion MVP-7 codebase.

## Policies

### 1. Quarantine Policy
- **Total Count Constraint**: The total number of skipped tests in quarantine.yml can only decrease
- **New Additions**: Require explicit approval with documented justification
- **Review Cadence**: Weekly review of quarantine status

### 2. Categories

#### Integration Tests
- **Definition**: Tests requiring external services (emotiond, databases, APIs)
- **Current Count**: 10 tests requiring emotiond service
- **Target**: All integration tests should have mock alternatives by MVP-7.2

#### Performance Tests
- **Definition**: Tests with long execution times (>30s)
- **Policy**: Move to separate performance suite

#### Flaky Tests
- **Definition**: Tests with non-deterministic outcomes
- **Policy**: Fix or remove; do not quarantine

### 3. Remediation Process

#### Step 1: Triage
- Assign owner and target unblock version
- Create issue for tracking if not exists
- Classify by category and complexity

#### Step 2: Implementation
- Create mock services for integration dependencies
- Add test fixtures for external state
- Implement retry logic for network flakiness

#### Step 3: Validation
- Test must pass consistently (5 consecutive runs)
- No regressions in related functionality
- Documentation updated

### 4. CI Integration

#### Pre-commit Checks
- Verify quarantine count does not increase
- Validate YAML syntax
- Check required fields are present

#### Post-commit Monitoring
- Alert on quarantine count increase
- Weekly report on remediation progress
- Automated test for governance compliance

### 5. Review Process

#### Weekly Review (Stakeholders: Tech Lead, QA Engineer)
- Review new quarantine requests
- Assess remediation progress
- Adjust target versions based on capacity

#### Monthly Review (Stakeholders: All Engineers)
- Quarantine trend analysis
- Process improvements
- Resource allocation for remediation

## Implementation Status

### Completed
- [x] quarantine.yml with 10 integration tests documented
- [x] Category classification (integration)
- [x] Target unblock versions set (MVP-7.2)
- [x] CI gate enforcement (max 10 tests)

### Next Actions
- [ ] Create mock emotiond service for integration tests
- [ ] Add pre-commit hook for quarantine validation
- [ ] Implement weekly remediation tracking
- [ ] Create performance test suite

## Metrics

### Current Status
- Total Quarantined: 10 tests
- Integration: 10 tests
- Target Unblocked: MVP-7.2
- Last Review: 2026-03-02

### Success Criteria
- Quarantine count ≤ 5 by MVP-7.1
- Quarantine count = 0 by MVP-7.2
- No new quarantines without explicit approval
- 100% remediation documentation completeness
