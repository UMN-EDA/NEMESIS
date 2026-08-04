# 5T OTA Example Run

This directory is a preserved, successful NEMESIS run for the five-transistor OTA. It shows the artifacts produced by `llm_aided_modelling.sh` from workspace creation through convergence and final model vectorization. The run converged at stage 9.

> Do not use this directory as `WORK_DIR` without first copying it: the driver deletes an existing work directory at startup.

## Run at a glance

- DUT: six MOS instances (`m0` through `m5`) using a 1 V supply and 5 uA reference bias.
- Initial device template: 180 nm length and 1 um width for every device.
- Iterations retained: stages 1 through 9.
- Final scalar model: `ota_models/ota_model_stage9.py`.
- Final batch evaluator: `ota_models/ota_model_stage9_vectorized.py`.
- Final SPICE report: `spice_performance/spice_estimation_stage9.json`.
- Final operating-point-based model report: `ota_model_performance/ota_model_estimation_stage9.2.json`.

The stage-9 comparison is close on the main measured quantities. For example, the model reports 19.93 dB DC gain and 20.45 MHz UGB, while HSPICE reports 20.23 dB and 20.14 MHz, respectively. `Gain Margin (dB)` is recorded as `FAILED` in the SPICE report, so it must not be interpreted as a validated numeric result.

## Artifact flow

```text
netlist/ + topology image
        |
        v
specs/ and prompts/prompt_stage1.txt
        |
        v
llm_outputs/llm_output_stageN.json --> equation_history.json
        |                                      |
        v                                      |
ota_models/ota_model_stageN.py                 |
        |                                      |
        +--> ota_model_performance/*N.1.json   |  LUT sizing
        |             |                        |
        |             v                        |
        |      testbenches/design_params_updated.sp
        |             |
        |             v
        |      spice_performance/*N.json + testbenches/spice_run/
        |             |
        +--> ota_model_performance/*N.2.json   |  OP-based verification
                      |
                      v
              prompts/prompt_stage(N+1).txt
```

At convergence, the final scalar model is converted into the stage-9 vectorized model, and the vectorization agent response is retained in `llm_outputs/`.

## Directory guide

| Path | Purpose and effect on the flow |
| --- | --- |
| `netlist/` | Simplified DUT topology supplied to prompt generation and feedback. |
| `specs/` | LLM-generated topology analysis, primitive grouping, device guidance, and testbench context used by the sizer. |
| `prompts/` | Initial, feedback-refined, gm/Id, and vectorization instructions sent to the LLM. |
| `llm_outputs/` | Structured equation proposals for every stage and the final vectorization response. |
| `ota_models/` | Executable Python evaluators compiled from the structured LLM outputs. |
| `ota_model_performance/` | Per-stage predictions: `.1` is LUT-based sizing; `.2` re-evaluates with HSPICE operating points. |
| `spice_performance/` | Simulator-ground-truth performance reports used by the feedback manager. |
| `testbenches/` | Local DUT, parameter files, reusable characterization decks, and simulator run workspace. |
| `testbenches/spice_run/` | Runtime HSPICE inputs and raw outputs; intentionally empty in this distributable example except for its README. |
| `ota_models/__pycache__/` | Disposable Python bytecode created when compiled models are imported; it has no modeling significance. |

The root-level `equation_history.json` accumulates equations across stages so feedback does not lose earlier attempts. `design_sweep_log.csv` contains one HSPICE summary row per stage, plus its header, and is useful for plotting convergence or auditing regressions.

Each subdirectory contains its own README with file-level interpretation and guidance on what is reusable, generated, or disposable.
