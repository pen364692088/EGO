#!/usr/bin/env python3
"""Check MVP-9 evaluation threshold and exit with error if not met."""
import json
import sys

def main():
    try:
        with open('reports/mvp9_eval.json') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("No evaluation report found!")
        sys.exit(1)
    
    passed = data.get('passed', False)
    score = data.get('overall_score', 0)
    threshold = data.get('threshold', 0.85)
    
    print(f'Overall Score: {score:.4f}')
    print(f'Threshold: {threshold}')
    print(f'Status: {"PASS" if passed else "FAIL"}')
    
    if not passed:
        print()
        print('MVP-9 evaluation did not meet threshold.')
        print('Please review reports/mvp9_failures.md for details.')
        sys.exit(1)

if __name__ == '__main__':
    main()
