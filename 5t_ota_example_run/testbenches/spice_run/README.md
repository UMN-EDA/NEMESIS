# HSPICE Run Products

This is the scratch/output directory passed to `perform_hspice_simulations.py` through `--run-dir`. During a live run it receives generated HSPICE decks and raw products such as listing, sweep, AC, transient, and operating-point files.

The distributable example intentionally does not include foundry-dependent raw simulator products. The summarized results needed to understand the run are retained in `../../spice_performance/`, while per-stage sweep summaries are retained in `../../design_sweep_log.csv`.

`extract_op.py` normally reads `run_op.lis` here and creates `op_results.json` for the stage model's `.2` verification pass. When debugging a failed or suspicious metric, this directory is the first place to inspect simulator diagnostics and raw measurements.
