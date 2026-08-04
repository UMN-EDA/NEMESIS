# Equation-Model Performance

This directory contains two model reports for every stage `N`:

- `ota_model_estimation_stageN.1.json` is produced by LUT-based gm/Id sizing. It contains the candidate device solution and predicted performance used to write `../testbenches/design_params_updated.sp`.
- `ota_model_estimation_stageN.2.json` is produced after HSPICE. It re-evaluates the same stage model with transistor operating points parsed from the simulator and is the equation-side input to mismatch analysis.

The `.1` and `.2` suffixes identify two evaluations within one stage; they are not fractional stage numbers. `feedback_manager.py` compares the `.2` report with `../spice_performance/spice_estimation_stageN.json`. If the compared equations exceed the configured error threshold, it creates the next stage prompt. The stage-9 `.2` report is the final verified model view for this run.
