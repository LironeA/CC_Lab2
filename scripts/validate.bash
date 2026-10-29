#!/usr/bin/env bash
# Compare two final fields. Useful for N=1 versus N>1 validation.
set -Eeuo pipefail
[[ $# == 2 ]] || { echo "Usage: $0 RUN_DIR_1 RUN_DIR_2" >&2; exit 2; }
python3 - "$1/final_state.npz" "$2/final_state.npz" <<'PY'
import sys
import numpy as np
a, b = (np.load(path)['temperature'] for path in sys.argv[1:])
if a.shape != b.shape: raise SystemExit('Different mesh sizes')
print(f'max_abs_error={np.max(np.abs(a-b)):.12g}')
np.testing.assert_allclose(a, b, rtol=1e-11, atol=1e-11)
print('Validation passed')
PY
