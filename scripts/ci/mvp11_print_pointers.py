#!/usr/bin/env python3
"""Print MVP11 run pointers for CI debug."""
import glob
import json

def main():
    files = sorted(glob.glob('artifacts/mvp11/mvp11_final_summary_*.json'))
    if not files:
        print('final_summary=NOT_FOUND')
    else:
        p = files[-1]
        print(f'final_summary={p}')
        d = json.load(open(p))
        print(f'pass={d.get("pass")}')
        print(f'science_eval={d.get("paths", {}).get("science_eval")}')
        print(f'replay_eval={d.get("paths", {}).get("replay_eval")}')
        print(f'full_soak_report={d.get("paths", {}).get("full_soak_report")}')

if __name__ == '__main__':
    main()
