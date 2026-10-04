#!/bin/bash
set -e
cd "$(dirname "$0")"   # run from the folder that holds exercises.jsonl / explanations.jsonl

echo "=== $(date) : coverage check ==="
python3 check_coverage.py

echo "=== $(date) : umlaut coverage fix (free, no LLM) ==="
python3 fix_umlaut_coverage.py

echo "=== $(date) : coverage fix ==="
python3 fix_coverage.py

echo "=== $(date) : case accuracy check ==="
python3 check_case_accuracy.py

echo "=== $(date) : case error fix ==="
python3 fix_case_errors.py

echo "=== $(date) : verb/negation/prefix order check ==="
python3 check_verb_order.py

echo "=== $(date) : order error fix ==="
python3 fix_order_errors.py

echo "=== $(date) : cycle done ==="
