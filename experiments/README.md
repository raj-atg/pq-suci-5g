# Experiments

Run from the repo root with `export OQS_INSTALL_PATH=$PWD/third_party/install/liboqs PYTHONPATH=src`.

## bench/e1_micro.py (E1, Python microbenchmarks)
- Purpose: keygen/conceal/deconceal timings for null, profile-a, profile-b, mlkem512/768/1024, hybrid.
- Command: `.venv/bin/python bench/e1_micro.py [--iterations 2000]`
- Inputs: `pqsuci.schemes`, liboqs. 200 warm-up calls, then N timed calls, GC disabled.
- Outputs: `results/raw/e1/python_timings.csv`, `results/raw/e1/env.txt`,
  `results/processed/e1_micro_python.csv`.

## bench/e1_native.sh and bench/parse_speed_kem.py (E1, native liboqs)
- Purpose: C reference timings for ML-KEM keygen/encaps/decaps.
- Command: `bash bench/e1_native.sh`
- Inputs: `third_party/liboqs/build/tests/speed_kem` (run once per algorithm, 3 s each).
- Outputs: `results/raw/e1/speed_kem.txt`, `results/processed/e1_native_liboqs.csv`.

## experiments/e2_sizes.py (E2, computed sizes)
- Purpose: key, scheme output, SUCI string and NAS mobile identity sizes per scheme.
- Command: `.venv/bin/python experiments/e2_sizes.py`
- Inputs: `pqsuci.schemes`.
- Outputs: `results/processed/e2_sizes_computed.csv`, `results/processed/e2_sizes_notes.txt`.

## experiments/e5_models.py (E5, analytical models)
- Purpose: M/M/c SIDF capacity from measured deconceal time; extra uplink airtime from sizes.
- Command: `.venv/bin/python experiments/e5_models.py`
- Inputs: `results/processed/e1_micro_python.csv`, `results/processed/e2_sizes_computed.csv`.
- Outputs: `results/processed/e5_sidf_capacity.csv`, `e5_sidf_saturation.csv`,
  `e5_airtime.csv`, `e5_airtime_notes.txt`. Assumptions are in the script docstring.
