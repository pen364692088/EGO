#!/usr/bin/env python3
"""Generate evaluation report"""

def generate_markdown_report(eval_json: dict) -> str:
    """Convert evaluation JSON to markdown report"""
    report = f"""# Evaluation Report

**Evaluation ID:** {eval_json['evaluation_id']}
**Timestamp:** {eval_json['timestamp']}
**Status:** {'✅ PASSED' if eval_json['scenarios_failed'] == 0 else '❌ FAILED'}

## Summary

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Withdraw Accuracy | {eval_json['metrics']['withdraw_accuracy']:.1%} | ≥95% | {'✅' if eval_json['metrics']['withdraw_accuracy'] >= 0.95 else '❌'} |
| False Positive Rate | {eval_json['metrics']['false_positive_rate']:.1%} | ≤5% | {'✅' if eval_json['metrics']['false_positive_rate'] <= 0.05 else '❌'} |
| Identity Isolation | {eval_json['metrics']['identity_isolation_rate']:.1%} | 100% | {'✅' if eval_json['metrics']['identity_isolation_rate'] == 1.0 else '❌'} |
| Decision Latency | {eval_json['metrics']['decision_latency_ms']}ms | <100ms | {'✅' if eval_json['metrics']['decision_latency_ms'] < 100 else '❌'} |
| Hash Stability | {eval_json['metrics']['hash_stability']:.1%} | ≥99% | {'✅' if eval_json['metrics']['hash_stability'] >= 0.99 else '❌'} |

## Scenarios

| ID | Name | Expected | Actual | Latency | Status |
|----|------|----------|--------|---------|--------|
"""
    for r in eval_json['results']:
        status = '✅' if r['passed'] else '❌'
        report += f"| {r['scenario_id']} | {r['name']} | {r['expected_action']} | {r['actual_action']} | {r['latency_ms']}ms | {status} |\n"
    
    return report

if __name__ == "__main__":
    import sys, json
    eval_json = json.load(open(sys.argv[1]))
    print(generate_markdown_report(eval_json))
