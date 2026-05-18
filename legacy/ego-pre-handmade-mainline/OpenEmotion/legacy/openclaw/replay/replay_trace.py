#!/usr/bin/env python3
"""
Replay emotiond trace and verify learning curves.
"""

import json
import csv
import argparse
from pathlib import Path
from datetime import datetime
import requests

EMOTIOND_BASE_URL = "http://127.0.0.1:18080"


def load_trace(trace_path: str) -> list:
    """Load JSONL trace file."""
    events = []
    with open(trace_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def get_state(target_id: str = None) -> dict:
    """Get current emotiond state."""
    params = {}
    if target_id:
        params['target_id'] = target_id
    
    try:
        resp = requests.get(f"{EMOTIOND_BASE_URL}/state", params=params, timeout=5)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def get_decision(target_id: str = None) -> dict:
    """Get latest decision."""
    params = {}
    if target_id:
        params['target_id'] = target_id
    
    try:
        resp = requests.get(f"{EMOTIOND_BASE_URL}/decision", params=params, timeout=5)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def replay_trace(trace_path: str, output_csv: str = None, dry_run: bool = False):
    """Replay trace and generate learning curve."""
    events = load_trace(trace_path)
    
    if not events:
        print(f"No events in trace: {trace_path}")
        return
    
    target_id = events[0].get('target_id', 'unknown')
    
    if output_csv is None:
        output_csv = trace_path.replace('.jsonl', '_replay.csv')
    
    records = []
    
    print(f"Replaying {len(events)} events for target: {target_id}")
    
    for i, event in enumerate(events):
        print(f"\n[{i+1}/{len(events)}] Processing event...")
        
        # Get state before (if not dry_run)
        if not dry_run:
            state = get_state(target_id)
            decision = get_decision(target_id)
        else:
            state = {}
            decision = {}
        
        record = {
            'step': i + 1,
            'timestamp': event.get('timestamp', ''),
            'event_type': event.get('type', 'unknown'),
            'trust': state.get('trust', 'N/A'),
            'bond': state.get('bond', 'N/A'),
            'grudge': state.get('grudge', 'N/A'),
            'repair_bank': state.get('repair_bank', 'N/A'),
            'social_safety': state.get('social_safety', 'N/A'),
            'energy': state.get('energy', 'N/A'),
            'action': decision.get('action', 'N/A'),
            'alpha': state.get('alpha', 'N/A')
        }
        records.append(record)
        
        # Replay event to emotiond (if not dry_run)
        if not dry_run and event.get('sent_events'):
            for sent in event['sent_events']:
                try:
                    requests.post(
                        f"{EMOTIOND_BASE_URL}/event",
                        json=sent,
                        timeout=5
                    )
                except Exception as e:
                    print(f"  Error replaying event: {e}")
    
    # Write CSV
    with open(output_csv, 'w', newline='') as f:
        if records:
            writer = csv.DictWriter(f, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)
    
    print(f"\n✅ CSV written to: {output_csv}")
    
    # Generate summary
    generate_summary(records, target_id)


def generate_summary(records: list, target_id: str):
    """Generate summary text."""
    print(f"\n📊 Summary for {target_id}")
    print("=" * 50)
    
    if not records:
        print("No records to summarize")
        return
    
    # Count actions
    actions = {}
    for r in records:
        action = r.get('action', 'N/A')
        if action != 'N/A':
            actions[action] = actions.get(action, 0) + 1
    
    if actions:
        print("\nAction distribution:")
        for action, count in sorted(actions.items(), key=lambda x: -x[1]):
            print(f"  {action}: {count}")
    
    # Check for patterns
    print("\nPatterns:")
    
    # Check for ignored → withdraw/boundary pattern
    ignored_count = sum(1 for r in records if 'ignored' in str(r.get('sent_events', '')))
    if ignored_count > 0:
        withdraw_boundary_count = sum(1 for r in records if r.get('action') in ['withdraw', 'boundary'])
        print(f"  ignored events: {ignored_count}")
        print(f"  withdraw/boundary actions: {withdraw_boundary_count}")
    
    # Check alpha growth
    alphas = [r.get('alpha') for r in records if r.get('alpha') not in ['N/A', None]]
    if alphas:
        try:
            alphas = [float(a) for a in alphas]
            print(f"  alpha trend: {alphas[0]:.3f} → {alphas[-1]:.3f}")
        except:
            pass


def main():
    parser = argparse.ArgumentParser(description='Replay emotiond trace')
    parser.add_argument('trace', help='Path to trace JSONL file')
    parser.add_argument('--output', '-o', help='Output CSV path')
    parser.add_argument('--dry-run', action='store_true', help='Do not send events to emotiond')
    
    args = parser.parse_args()
    
    replay_trace(args.trace, args.output, args.dry_run)


if __name__ == '__main__':
    main()
