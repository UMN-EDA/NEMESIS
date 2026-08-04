# Generated Design Specification

`5t_ota.json` is created by the gm/Id estimation agent before the iterative modeling loop. It records topology analysis, primitive groups, device-level guidance, current budget, and testbench context for this 1 V, 5 uA, 180 nm 5T OTA setup.

`design_sizer.py` reads this file during both sizing and operating-point verification. It therefore provides the shared design intent against which all stage models are evaluated. This file is generated from the simplified netlist, topology image, and design-context arguments in `llm_aided_modelling.sh`; changing those inputs can change the specification and all downstream sizing results.
