[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE) [![docs](https://img.shields.io/badge/docs-passing-brightgreen.svg)](https://umn-eda.github.io/NEMESIS/)




# NEMESIS

NEMESIS is a framework for LLM-aided OTA circuit modeling with SPICE-based verification. The main driver, `llm_aided_modelling.sh`, generates compact performance equations, compiles them into executable Python models, sizes the circuit using gm/Id lookup-table logic, verifies the result with HSPICE, and feeds mismatch information back into the next LLM prompt until convergence.

The GitHub Pages documentation site is in `docs/`. After pushing the repository, configure GitHub Pages to publish from the `/docs` folder.

## Repository Layout

- `llm_aided_modelling.sh`: top-level NEMESIS workflow driver.
- `Universal/dut/`: source DUT netlists for supported OTA topologies.
- `Universal/otas/`: circuit figures used as LLM visual context.
- `Universal/testbenches/`: reusable HSPICE testbenches and the universal DUT wrapper.
- `Specs/`: reference spec JSON files for supported examples.
- `docs/`: website materials for GitHub Pages.
- `5t_ota_example_run/`: preserved nine-stage example showing the complete artifact trail of a successful 5T OTA run.
- `<WORK_DIR>/`: generated run directory, such as `5t_ota/`, containing prompts, LLM outputs, compiled models, sizing reports, SPICE reports, and logs.

## Requirements

- Python 3.
- Dependencies from `requirements.txt`.
- HSPICE available on `PATH`.
- API credentials/configuration required by `call_codex.py`.
- Valid foundry model paths referenced by the DUT netlists.
- Technology-characterized NMOS and PMOS gm/Id lookup-table CSV files.

## Basic Usage

Create a Python environment and install dependencies:

```bash
python3 -m venv llm_venv
source llm_venv/bin/activate
pip install -r requirements.txt
```

Check the configuration block at the top of `llm_aided_modelling.sh`. The default run uses:

```bash
WORK_DIR="5t_ota"
PARENT_DUT_FILE="Universal/dut/$WORK_DIR.sp"
FIGURE_FILE="Universal/otas/$WORK_DIR.png"
MAX_ITER=1000
MODEL="gpt-5.5"
REASONING="high"
```

Run the framework:

```bash
NMOS_LUT_FILE=/path/to/nmos_lut.csv \
PMOS_LUT_FILE=/path/to/pmos_lut.csv \
  bash llm_aided_modelling.sh
```

The LUT files are external technology inputs and are not included in this repository. The driver checks both paths
before recreating the work directory or making any LLM API calls. If the environment variables are omitted, the
legacy paths `Testbenches/nmos_lut.csv` and `Testbenches/pmos_lut.csv` are used.

Each CSV must contain at least one data row and the finite numeric columns `L`, `gmid`, `id`, and `W`. Consistent with
the existing sizing and specification SI convention, `L` and `W` are in metres, `gmid` is in 1/V, and `id` is in
amperes. Validate the inputs without starting the flow or creating `.pkl` caches with:

```bash
python3 design_sizer.py --validate-luts \
  --nmos-lut "/path/to/NMOS LUT.csv" \
  --pmos-lut "/path/to/PMOS LUT.csv"
```

Important: the driver deletes and recreates `WORK_DIR` at the start of each run. Preserve generated artifacts before rerunning with the same work-directory name.

## Worked 5T OTA Example

[`5t_ota_example_run/`](5t_ota_example_run/) is a read-only snapshot of a complete framework run. It is named differently from the driver's default `5t_ota` workspace so it can be published without being deleted by the next run. The example converged at stage 9 and preserves the full chain from simplified netlist and generated specification to prompts, structured LLM responses, compiled models, model estimates, HSPICE reports, and the final vectorized evaluator.

Start with [`5t_ota_example_run/README.md`](5t_ota_example_run/README.md) for the artifact flow and directory map. Every subdirectory also has a short README explaining its contents, its producer and consumer, and its effect on convergence. For a visual walkthrough, open the website's [Example Run](docs/example.html) page.

The final stage illustrates how to read the two model reports: `ota_model_estimation_stage9.1.json` is the LUT-based sizing pass, while `ota_model_estimation_stage9.2.json` is the same model evaluated using HSPICE-extracted operating points. The feedback manager compares the `.2` report against `spice_estimation_stage9.json`. The final scalar and vectorized evaluators are `ota_model_stage9.py` and `ota_model_stage9_vectorized.py`, respectively.

## What the Driver Produces

For a run such as `WORK_DIR="5t_ota"`, outputs are written under `5t_ota/`:

- `netlist/`: simplified DUT netlist for LLM prompting.
- `prompts/`: stage prompts and vectorization prompt.
- `llm_outputs/`: LLM JSON responses, repair outputs, and error logs.
- `ota_models/`: compiled scalar model files and final vectorized model.
- `ota_model_performance/`: model-based sizing and verification JSON.
- `spice_performance/`: HSPICE performance reports.
- `testbenches/spice_run/`: generated HSPICE decks and simulator outputs.
- `equation_history.json`: accumulated generated equation history.

## Adapting to Another Circuit

1. Add the netlist as `Universal/dut/<new_work_dir>.sp`.
2. Add a matching topology image as `Universal/otas/<new_work_dir>.png`.
3. Ensure the main SPICE subcircuit is named `DUT`.
4. Match the universal OTA pin convention: `vp vn vout vdd vss ibias`, or `vp vn vout vdd vss ibias vb2` for circuits with a second bias input.
5. Update `WORK_DIR`, `PARENT_DUT_FILE`, `NETLIST_FILE`, `SPEC_FILE_TEST`, and `FIGURE_FILE` in `llm_aided_modelling.sh`.
6. Update design context in the gm/Id prompt generation call, including supply voltage, bias current, length, application, and design intent.
7. Review `Universal/testbenches/` for supply naming, bias direction, load capacitance, common-mode range, output swing assumptions, and measurement names.

## Website

Open `docs/index.html` locally or enable GitHub Pages from `/docs`. The site explains the full high-level flow, every script operation, universal testbench usage, and how users can modify NEMESIS for new OTA circuits.

## License

This repository is distributed under the license in [`LICENSE`](LICENSE).

## Contact

For any questions, please contact:

**Subhadip Ghosh**  
University of Minnesota  
ghosh211@umn.edu

## Citation

COmPOSER has been accepted for publication in the Proceedings of the ACM/IEEE Design Automation Conference (DAC) 2026. If you use COmPOSER in your research, please cite our work:

```bibtex
@misc{ghosh2026nemesisnetlistdrivenmodelingequation,
      title={NEMESIS: NEtlist-Driven Modeling and Equation Synthesis with Inversion-Aware SPICE Anchoring}, 
      author={Subhadip Ghosh and Ramesh Harjani and Sachin S. Sapatnekar},
      year={2026},
      eprint={2607.05657},
      archivePrefix={arXiv},
      primaryClass={cs.AR},
      url={https://arxiv.org/abs/2607.05657}, 
}
```

Paper link: [https://arxiv.org/abs/2607.05657]
