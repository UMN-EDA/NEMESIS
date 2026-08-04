# Local HSPICE Testbench Workspace

This directory is the run-local simulation environment assembled by `llm_aided_modelling.sh`. It isolates generated parameters and simulator outputs from the reusable templates in `Universal/testbenches/`.

- `5t_ota.sp` is the full DUT copied from `Universal/dut/` and is the netlist HSPICE simulates.
- `design_params.sp` is the generated baseline: supplies, bias, load, simulator options, and initial 180 nm by 1 um device parameters.
- `design_params_updated.sp` is overwritten from each stage's LUT-sizing result and drives the next HSPICE characterization.
- `dut_wrapper.sp` adapts the DUT to the universal testbench pin interface.
- `tb_ac.sp`, `tb_cmrr.sp`, `tb_icmr.sp`, `tb_ocmr.sp`, `tb_power.sp`, `tb_psrrp.sp`, `tb_psrrn.sp`, and `tb_sr.sp` measure the principal OTA performance views.
- `tb_op.sp` is the base operating-point deck; `tb_op_temp.sp` is the generated variant used for device operating-point extraction.
- `spice_run/` is the working directory for generated decks and raw simulator products.

These decks directly define the reference measurements used to judge the generated equations. Changes to stimuli, sweep ranges, loads, `.measure` statements, wrapper pin mapping, or model includes can change convergence behavior and must be reviewed together with the report parser.
