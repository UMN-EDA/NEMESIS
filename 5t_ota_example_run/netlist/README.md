# Simplified Netlist

`5t_ota.sp` is the prompt-oriented DUT netlist produced by `generate_netlist_for_llm.py` from the copied simulation DUT in `../testbenches/5t_ota.sp`.

It retains the `DUT` subcircuit interface, device names, terminal connectivity, MOS type, and symbolic width/length parameters while removing simulator detail that would add noise to an LLM prompt. NEMESIS uses this file when creating the initial model prompt and every feedback prompt, so incorrect connectivity here would affect every generated equation.

This is a generated derivative, not the authoritative simulation netlist. Change the source under `Universal/dut/` and regenerate the run rather than maintaining this file independently.
