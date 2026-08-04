# HSPICE Performance Reports

`spice_estimation_stage1.json` through `spice_estimation_stage9.json` are the simulator-ground-truth reports produced after each candidate sizing is written into the local SPICE parameters.

Each report groups extracted characterization metrics—such as ICMR, DC gain, UGF, phase margin, output swing, power, CMRR, PSRR, and slew rate—with global parameters and a timestamp. `feedback_manager.py` compares a stage report with the matching `../ota_model_performance/ota_model_estimation_stageN.2.json` to decide whether to converge or generate another corrective prompt.

A nonnumeric value such as the stage-9 `Gain Margin (dB): "FAILED"` indicates an unsuccessful measurement, not a valid performance number. Consult the raw simulator outputs when diagnosing such a field.
