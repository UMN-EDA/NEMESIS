# LLM Prompts

This directory preserves every prompt that materially shaped the run.

- `gmid_agent_prompt_1.txt` asks the first agent to interpret the topology and produce `../specs/5t_ota.json`.
- `prompt_stage1.txt` is the initial equation-generation prompt built from the simplified DUT.
- `prompt_stage2.txt` through `prompt_stage9.txt` contain simulator-informed corrections from the preceding stage. `prompt_stageN` is therefore the input to stage `N`, not the report for that stage.
- `vectorization_prompt.txt` contains the final instructions used to convert the converged scalar evaluator into a batch-capable evaluator.

These files make the feedback trajectory auditable: compare adjacent stage prompts to see which equation mismatches HSPICE asked the next model generation to correct. They are generated artifacts and normally should not be edited during a run.
