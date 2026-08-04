# Structured LLM Outputs

`llm_output_stage1.json` through `llm_output_stage9.json` are the structured equation proposals returned for the corresponding prompts. Each response includes reasoning context, a topology summary, device mapping, performance equations, and Python-generation material.

For each stage, `extract_equations.py` adds the equations to `../equation_history.json`, and `compile_ota_model_script.py` turns the JSON into `../ota_models/ota_model_stageN.py`. A malformed or incomplete response can therefore stop compilation or sizing and may trigger the automatic repair path described in the driver.

`vectorization_agent_stage9.json` retains the response used to create the final vectorized evaluator after stage 9 converged. Repair JSON and sizer-error logs may also appear here in runs where automatic model repair is required; none are retained in this successful example.
