#!/usr/bin/env python3
"""CLI entry point: python -m benchmarks.run"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.eval_suite import run_benchmark


def main():
    parser = argparse.ArgumentParser(description='AI-IQ retrieval benchmark')
    parser.add_argument('--json', action='store_true', help='Output JSON instead of table')
    parser.add_argument('--quiet', action='store_true', help='Suppress progress output')
    args = parser.parse_args()

    results = run_benchmark(verbose=not args.json and not args.quiet)

    if args.json:
        print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
