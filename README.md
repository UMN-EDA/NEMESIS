# NEMESIS

<p>
  <a href="#license"><kbd>License</kbd></a>
  <a href="docs/index.html"><kbd>WEBSITE</kbd></a>
</p>

NEMESIS is a framework for LLM-aided OTA circuit modeling with SPICE-based verification. The main driver, `llm_aided_modelling.sh`, generates compact performance equations, compiles them into executable Python models, sizes the circuit using gm/Id lookup-table logic, verifies the result with HSPICE, and feeds mismatch information back into the next LLM prompt until convergence.

The GitHub Pages documentation site is in `docs/`. After pushing the repository, configure GitHub Pages to publish from the `/docs` folder.

## Repository Layout

- `llm_aided_modelling.sh`: top-level NEMESIS workflow driver.
- `Universal/dut/`: source DUT netlists for supported OTA topologies.
- `Universal/otas/`: circuit figures used as LLM visual context.
- `Universal/testbenches/`: reusable HSPICE testbenches and the universal DUT wrapper.
- `Specs/`: reference spec JSON files for supported examples.
- `docs/`: website materials for GitHub Pages.
- `<WORK_DIR>/`: generated run directory, such as `5t_ota/`, containing prompts, LLM outputs, compiled models, sizing reports, SPICE reports, and logs.

## Requirements

- Python 3.
- Dependencies from `requirements.txt`.
- HSPICE available on `PATH`.
- API credentials/configuration required by `call_codex.py`.
- Valid foundry model paths referenced by the DUT netlists.

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
bash llm_aided_modelling.sh
```

Important: the driver deletes and recreates `WORK_DIR` at the start of each run. Preserve generated artifacts before rerunning with the same work-directory name.

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

License information has not been added to this repository yet.
