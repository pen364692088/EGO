#!/usr/bin/env python3
"""Analyze MVP-9 failures and output GitHub Step Summary."""
import json
import sys

def main():
    try:
        with open('reports/mvp9_eval.json') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("No evaluation report found")
        return
    
    categories = {}
    for scenario in data.get('scenarios', []):
        if not scenario.get('passed', True):
            for check in scenario.get('checks', []):
                if not check.get('passed', True):
                    cat = check.get('category', 'unknown')
                    categories[cat] = categories.get(cat, 0) + 1
    
    for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:5]:
        print(f'- **{cat}**: {count} failures')

if __name__ == '__main__':
    main()
