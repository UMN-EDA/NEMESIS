#!/bin/bash

# ==============================================================================
# CONFIGURATION
# ==============================================================================
WORK_DIR="5t_ota" #CHANGE
PARENT_DUT_FILE="Universal/dut/$WORK_DIR.sp"  #CHANGE
DUT_FILE="$WORK_DIR/testbenches/$WORK_DIR.sp"
NETLIST_FILE="$WORK_DIR/netlist/$WORK_DIR.sp" #CHANGE
SPEC_FILE_TEST="$WORK_DIR/specs/$WORK_DIR.json" #CHANGE
FIGURE_FILE="Universal/otas/$WORK_DIR.png" #CHANGE
PARENT_TESTBENCH_DIR="Universal/testbenches/"
TEMP_TESTBENCH_DIR="$WORK_DIR/testbenches"
DESIGN_PARAMS="$WORK_DIR/testbenches/design_params.sp"
MAX_ITER=1000 #CHANGE
INITIAL_PROMPT="$WORK_DIR/prompts/prompt_stage1.txt"
EQUATION_LIBRARY="$WORK_DIR/equation_history.json"
gmid_agent_prompt="$WORK_DIR/prompts/gmid_agent_prompt_1.txt"

MODEL="gpt-5.5"
REASONING="high"
NMOS_LUT_FILE="${NMOS_LUT_FILE:-Testbenches/nmos_lut.csv}"
PMOS_LUT_FILE="${PMOS_LUT_FILE:-Testbenches/pmos_lut.csv}"

UPDATED_DESIGN_PARAMS="$WORK_DIR/testbenches/design_params_updated.sp"
OP_LIS="$WORK_DIR/testbenches/spice_run/run_op.lis"
OP_JSON="$WORK_DIR/testbenches/spice_run/op_results.json"
PDF_FILE="Pdfs/design_guide.pdf" #If any
TESTBENCH_PROMPT="Testbenches/testbench_prompt.txt"
SPICE_RUN_DIR="$WORK_DIR/testbenches/spice_run"
MAX_MODEL_REPAIR_ATTEMPTS=5
MAX_MODEL_VECTORIZATION_EFFORT_ITERS=5
VECTORIZATION_PROMPT="$WORK_DIR/prompts/vectorization_prompt.txt"
# Python Scripts
SCRIPT_GEN_NETLIST_FOR_LLM="generate_netlist_for_llm.py"
SCRIPT_LLM="call_codex.py"
SCRIPT_MERGE_PROMPTS="merge_prompt.py"
SCRIPT_COMPILE="compile_ota_model_script.py"
SCRIPT_SIZER="design_sizer.py"
SCRIPT_HSPICE="perform_hspice_simulations.py"
SCRIPT_FEEDBACK="feedback_manager.py"
SCRIPT_STAGE1_PROMPT_MANAGER="generate_stage1_prompt.py"
SCRIPT_GMID_AGENT_PROMPT_MANAGER="generate_gmid_estimator_agent_prompt.py"
SCRIPT_EQUATION_LIBRARY="extract_equations.py"
SCRIPT_DESIGN_PARAM="update_design_params.py"
SCRIPT_HSPICE_OP_TB="$WORK_DIR/testbenches/tb_op.sp"  #CHANGE
SCRIPT_HSPICE_OP_TB_TEMP="${WORK_DIR}/testbenches/tb_op_temp.sp"
SCRIPT_GEN_OP_HSPICE_TB="generate_op_hspice.py"
SCRIPT_GEN_DESIGN_PARAMS="generate_design_params.py"
SCRIPT_EXTRACT_OP_PARAMS="extract_op.py"
SCRIPT_REPAIR_MODEL="repair_model.py"
SCRIPT_VECTORIZATION_AGENT="vectorization_agent.py"
SCRIPT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# The technology-characterized gm/Id LUTs are external inputs. Validate them
# before deleting an existing work directory or making any LLM API calls.
python3 "$SCRIPT_ROOT/$SCRIPT_SIZER" \
    --validate-luts \
    --nmos-lut "$NMOS_LUT_FILE" \
    --pmos-lut "$PMOS_LUT_FILE"
lut_validation_rc=$?
if [ "$lut_validation_rc" -ne 0 ]; then
    echo "Set NMOS_LUT_FILE and PMOS_LUT_FILE to valid user-provided LUT CSV files." >&2
    exit "$lut_validation_rc"
fi

# NEW: Cleanup existing WORK_DIR to ensure no cross-contamination from old runs
echo ">>[1] OPERATION: check if WORK_DIR exists: [ -d \"$WORK_DIR\" ]"
if [ -d "$WORK_DIR" ]; then
    echo ">> Cleaning up existing WORK_DIR: $WORK_DIR"
    echo ">> OPERATION: rm -rf \"$WORK_DIR\""
    rm -rf "$WORK_DIR"
fi

#Creating the work directory for the new OTA
echo "[INFO] Creating work directory: $WORK_DIR"
mkdir -p "$WORK_DIR"

echo "[INFO] Creating subdirectories inside $WORK_DIR"
mkdir -p "$WORK_DIR"/{testbenches,netlist,prompts,llm_outputs,ota_models,ota_model_performance,spice_performance,specs}

echo "[INFO] Copying files from $PARENT_TESTBENCH_DIR to $WORK_DIR"
cp -a "$PARENT_TESTBENCH_DIR"/. "$WORK_DIR/testbenches"/.

echo "[INFO] Copying spice DUT netlist from $PARENT_DUT_FILE to $DUT_FILE"
cp -a "$PARENT_DUT_FILE" "$DUT_FILE"

echo "[INFO] Directory setup complete."



echo ">> [2] Generating the simplified NETLIST File for the llm..."
echo ">> CMD: python3 \"$SCRIPT_GEN_NETLIST_FOR_LLM\" --input \"$DUT_FILE\" --output \"$NETLIST_FILE\""
python3 "$SCRIPT_GEN_NETLIST_FOR_LLM" \
    --input "$DUT_FILE" \
    --output "$NETLIST_FILE" 



echo ">> [3] Generating the design_params.sp file..."
echo ">> CMD: python3 \"$SCRIPT_GEN_DESIGN_PARAMS\" --netlist \"$DUT_FILE\" --params \"$DESIGN_PARAMS\" --length \"180\""
python3 "$SCRIPT_GEN_DESIGN_PARAMS" \
    --netlist "$DUT_FILE" \
    --params "$DESIGN_PARAMS" \
    --length "180"


echo ">> [4] Generating operating point simulation HSPICE testbench..."
echo ">> CMD: python3 \"$SCRIPT_GEN_OP_HSPICE_TB\" --netlist \"$DUT_FILE\" --testbench \"$SCRIPT_HSPICE_OP_TB\" --output \"$SCRIPT_HSPICE_OP_TB_TEMP\""
python3 "$SCRIPT_GEN_OP_HSPICE_TB" \
    --netlist "$DUT_FILE" \
    --testbench "$SCRIPT_HSPICE_OP_TB" \
    --output "$SCRIPT_HSPICE_OP_TB_TEMP"


#Generating gm/Id estimator agent prompts
echo ">> [5] Running gmId estimation agent promprt generator ..."
echo ">> CMD: python3 \"$SCRIPT_GMID_AGENT_PROMPT_MANAGER\" --netlist \"$NETLIST_FILE\" --output \"$SPEC_FILE_TEST\" --Vdd 1.0 --Vss 0.0 --ibias \"5u\" --Cload \"500f\" --SR \"20V/us\" --L \"180n\" --application \"general_purpose_balanced_ota\" --design-intent \"balanced\""
python3 "$SCRIPT_GMID_AGENT_PROMPT_MANAGER" \
    --netlist "$NETLIST_FILE" \
    --output "$gmid_agent_prompt" \
    --Vdd 1.0 \
    --Vss 0.0 \
    --ibias "5u" \
    --L "180n" \
    --application "general_purpose_balanced_ota" \
    --design-intent "balanced"


#Run gm/Id estimator agent
echo ">> [6] Running gmId estimation agent ..."
echo ">> CMD: python3 \"$SCRIPT_LLM\" --prompt \"$gmid_agent_prompt\" --images \"$FIGURE_FILE\" --output \"$SPEC_FILE_TEST\""
python3 "$SCRIPT_LLM" \
    -p "$gmid_agent_prompt" \
    -o "$SPEC_FILE_TEST" \
    -i "$FIGURE_FILE" \
    -m "$MODEL" \
    -r "$REASONING"

echo ">> OPERATION: Iteration=1"
iter=1
echo ">> OPERATION: current_prompt=\"$INITIAL_PROMPT\""
current_prompt="$INITIAL_PROMPT"

echo "=========================================================="
echo " Starting Analog Design Optimization Loop"
echo " Max Iterations: $MAX_ITER"
echo " Initial Prompt: $INITIAL_PROMPT"
echo "=========================================================="

# ==============================================================================
# STARTING PROMPT GENERATION
# ==============================================================================
echo ">> [7] Generating initial prompts..."
echo ">> CMD: python3 \"$SCRIPT_STAGE1_PROMPT_MANAGER\" --netlist \"$NETLIST_FILE\" -o \"$INITIAL_PROMPT\""
python3 "$SCRIPT_STAGE1_PROMPT_MANAGER" \
    --netlist "$NETLIST_FILE" \
    -o "$INITIAL_PROMPT"



echo ">> OPERATION: while [ $iter -le $MAX_ITER ]"
while [ $iter -le $MAX_ITER ]
do
    echo ""
    echo "----------------------------------------------------------"
    echo " [ITERATION $iter] Starting Flow..."
    echo "----------------------------------------------------------"

    # Define dynamic filenames for the CURRENT iteration
    file_gen_json="$WORK_DIR/llm_outputs/llm_output_stage${iter}.json"
    file_model_py="$WORK_DIR/ota_models/ota_model_stage${iter}.py"
    file_repaired_json="$WORK_DIR/llm_outputs/llm_output_stage${iter}_repair.json"
    file_sized_params_gmid="$WORK_DIR/ota_model_performance/ota_model_estimation_stage${iter}.1.json"
    file_sized_params_spice="$WORK_DIR/ota_model_performance/ota_model_estimation_stage${iter}.2.json"
    file_hspice_report="$WORK_DIR/spice_performance/spice_estimation_stage${iter}.json"
    file_vectorized_model_py="$WORK_DIR/ota_models/ota_model_stage${iter}_vectorized.py"
    # The prompt we will generate for the NEXT iteration
    file_next_prompt="$WORK_DIR/prompts/prompt_stage$((iter+1)).txt"



    echo ">> [8] Running LLM with the prompts and Figure..."
    echo ">> CMD: python3 \"$SCRIPT_LLM\" --prompt \"$current_prompt\" --images \"$FIGURE_FILE\" --output \"$file_gen_json\""
    python3 "$SCRIPT_LLM" \
        -p "$current_prompt" \
        -o "$file_gen_json" \
        -i "$FIGURE_FILE" \
        -m "$MODEL" \
        -r "$REASONING"



    echo ">> OPERATION: check llm output exists: [ ! -f \"$file_gen_json\" ]"
    if [ ! -f "$file_gen_json" ]; then
        echo "Error: LLM output not found. Retrying iteration $iter..."
        echo ">> OPERATION: continue"
        continue
    fi

    echo ">> [9] Updating equation history library..."
    echo ">> CMD: python3 \"$SCRIPT_EQUATION_LIBRARY\" --input \"$file_gen_json\" --output \"$EQUATION_LIBRARY\""
    python3 "$SCRIPT_EQUATION_LIBRARY" \
        --input "$file_gen_json" \
        --output "$EQUATION_LIBRARY"
    rc=$?
    


    echo ">> OPERATION: check [9] exit code: $rc"
    if [ $rc -ne 0 ]; then
        echo "!! Task [9] failed (exit code $rc). Restarting iteration $iter..."

        # Optional but recommended: cleanup current iteration artifacts
        echo ">> OPERATION: rm -f \"$file_gen_json\" \"$file_model_py\""
        rm -f "$file_gen_json" "$file_model_py"

        # Do not increment iter, restart same iteration from [4]
        echo ">> OPERATION: continue"
        continue
    fi

    echo ">> [10] Compiling Equation Model..."
    echo ">> CMD: python3 \"$SCRIPT_COMPILE\" --input_file \"$file_gen_json\" --output_file \"$file_model_py\""
    python3 "$SCRIPT_COMPILE" \
        --input_file "$file_gen_json" \
        --output_file "$file_model_py"
   


    repair_attempt=0
    while true
    do
        echo ">> [11] Running Design Sizer using GmId LUT..."
        echo ">> CMD: python3 \"$SCRIPT_SIZER\" --model \"$file_model_py\" --specs \"$SPEC_FILE_TEST\" --out \"$file_sized_params_gmid\""

        rm -f "$file_sized_params_gmid"

        sizer_output=$(python3 "$SCRIPT_SIZER" \
            --model "$file_model_py" \
            --specs "$SPEC_FILE_TEST" \
            --out "$file_sized_params_gmid" \
            --nmos-lut "$NMOS_LUT_FILE" \
            --pmos-lut "$PMOS_LUT_FILE" \
            --optimize 2>&1)

        sizer_rc=$?
        echo "$sizer_output"

        if [ $sizer_rc -eq 0 ] && [ -f "$file_sized_params_gmid" ]; then
            echo ">> Task [11] completed successfully."
            break
        fi

        echo "!! Task [11] failed."

        if [ $repair_attempt -ge $MAX_MODEL_REPAIR_ATTEMPTS ]; then
            echo "!! Reached max repair attempts for Task [11]."
            echo "!! Restarting current iteration from LLM generation."

            rm -f "$file_gen_json" "$file_model_py" "$file_repaired_json" "$file_sized_params_gmid"
            rm -f "$WORK_DIR/llm_outputs/sizer_error_stage${iter}_attempt"*.log
            rm -f "$WORK_DIR/llm_outputs/model_repair_stage${iter}_attempt"*.log
            continue 2
        fi

        repair_attempt_next=$((repair_attempt+1))
        file_sizer_error="$WORK_DIR/llm_outputs/sizer_error_stage${iter}_attempt${repair_attempt_next}.log"
        file_model_repair_log="$WORK_DIR/llm_outputs/model_repair_stage${iter}_attempt${repair_attempt_next}.log"

        echo "!! Automatic repair attempt $repair_attempt_next / $MAX_MODEL_REPAIR_ATTEMPTS"
        echo "!! Buggy model: $file_model_py"
        echo "!! Repaired JSON target: $file_repaired_json"
        echo "!! Sizer error log: $file_sizer_error"

        printf "%s\n" "$sizer_output" > "$file_sizer_error"
        rm -f "$file_repaired_json"

        # repair_model_py.py preserves the source JSON schema and writes repaired JSON.
        repair_cmd=(python3 "$SCRIPT_REPAIR_MODEL" \
            --model "$file_model_py" \
            --out-json "$file_repaired_json" \
            --error-file "$file_sizer_error" \
            --call-codex "$SCRIPT_LLM" \
            --llm-model "$MODEL" \
            --reasoning "$REASONING")

        if [ -f "$FIGURE_FILE" ]; then
            repair_cmd+=(-i "$FIGURE_FILE")
        fi

        echo ">> CMD: ${repair_cmd[*]}"
        "${repair_cmd[@]}" 2>&1 | tee "$file_model_repair_log"

        repair_rc=${PIPESTATUS[0]}
        repair_attempt=$repair_attempt_next

        if [ $repair_rc -ne 0 ] || [ ! -f "$file_repaired_json" ]; then
            echo "!! Automatic repair script failed or did not create repaired JSON."

            if [ $repair_attempt -ge $MAX_MODEL_REPAIR_ATTEMPTS ]; then
                echo "!! Reached max repair attempts for Task [11]."
                echo "!! Restarting current iteration from LLM generation."

                rm -f "$file_gen_json" "$file_model_py" "$file_repaired_json" "$file_sized_params_gmid" "$file_sizer_error" "$file_model_repair_log"
                continue 2
            fi

            echo ">> Retrying automatic repair..."
            continue
        fi

        echo ">> Compiling repaired JSON into Python model..."
        echo ">> CMD: python3 \"$SCRIPT_COMPILE\" --input_file \"$file_repaired_json\" --output_file \"$file_model_py\""
        python3 "$SCRIPT_COMPILE" \
            --input_file "$file_repaired_json" \
            --output_file "$file_model_py"

        compile_repair_rc=$?

        if [ $compile_repair_rc -ne 0 ] || [ ! -f "$file_model_py" ]; then
            echo "!! Compile failed after JSON repair."

            if [ $repair_attempt -ge $MAX_MODEL_REPAIR_ATTEMPTS ]; then
                echo "!! Reached max repair attempts for Task [11]."
                echo "!! Restarting current iteration from LLM generation."

                rm -f "$file_gen_json" "$file_model_py" "$file_repaired_json" "$file_sized_params_gmid" "$file_sizer_error" "$file_model_repair_log"
                continue 2
            fi

            echo ">> Retrying automatic repair..."
            continue
        fi

        echo ">> Repair JSON compiled successfully."
        echo ">> Repaired JSON: $file_repaired_json"
        echo ">> Overwritten Python model: $file_model_py"
        echo ">> Retrying Task [11]..."
    done

    echo ">> [12] Updating the Design Params..."
    echo ">> CMD: python3 \"$SCRIPT_DESIGN_PARAM\" --json_file \"$file_sized_params_gmid\" --sp_file \"$DESIGN_PARAMS\" --out_file \"$UPDATED_DESIGN_PARAMS\""
    python3 "$SCRIPT_DESIGN_PARAM" \
        --json_file "$file_sized_params_gmid" \
        --sp_file "$DESIGN_PARAMS" \
        --out_file "$UPDATED_DESIGN_PARAMS"
    
    echo ">> [13] Running HSPICE Simulation..."
    echo ">> CMD: python3 \"$SCRIPT_HSPICE\" --dut \"$DUT_FILE\" --params \"$UPDATED_DESIGN_PARAMS\" --report \"$file_hspice_report\""
    python3 "$SCRIPT_HSPICE" \
        --dut "$DUT_FILE" \
        --params "$UPDATED_DESIGN_PARAMS" \
        --report "$file_hspice_report" \
        --testbench-dir "$WORK_DIR/testbenches" \
        --wrapper "$WORK_DIR/testbenches/dut_wrapper.sp" \
        --csv "$WORK_DIR/design_sweep_log.csv" \
        --run-dir "$SPICE_RUN_DIR" 

    echo ">> OPERATION: check hspice report exists: [ ! -f \"$file_hspice_report\" ]"
    if [ ! -f "$file_hspice_report" ]; then
        echo "Error: HSPICE report not found."
        echo ">> OPERATION: exit 1"
        exit 1
    fi

    echo ">> [14] Extracting the .op parameters..."
    python3 "$SCRIPT_EXTRACT_OP_PARAMS" \
        --input "$OP_LIS" \
        --output "$OP_JSON"


    echo ">> [15] Running Design Sizer using the extracted .op params..."
    echo ">> CMD: python3 \"$SCRIPT_SIZER\" --model \"$file_model_py\" --specs \"$SPEC_FILE\" --out \"$file_sized_params_spice\" --opjson \"$OP_JSON\" --verify"
    python3 "$SCRIPT_SIZER" \
        --model "$file_model_py" \
        --specs "$SPEC_FILE_TEST" \
        --out "$file_sized_params_spice" \
        --verify \
        --opjson "$OP_JSON" \
        --optimize

    #read -p "Press Enter to Continue ..."

    # --- NEW: FALLBACK CHECK FOR TASK 11 ---
    echo ">> OPERATION: check verified spice params exist: [ ! -f \"$file_sized_params_spice\" ]"
    if [ ! -f "$file_sized_params_spice" ]; then
        echo "!! Task [15] Sizer failed to produce $file_sized_params_spice."
        echo "!! Falling back to Task [4] (Gemini Re-generation) for iteration $iter..."
        
        # Cleanup current iteration's failed artifacts to avoid reuse
        echo ">> OPERATION: rm -f \"$file_gen_json\" \"$file_model_py\""
        rm -f "$file_gen_json" "$file_model_py"
        
        # We do NOT increment iter, so 'continue' restarts the same iteration loop at Task [4]
        echo ">> OPERATION: continue"
        continue
    fi
        
    #read -p "Press Enter to Continue ..."
    echo ">> [16] Analyzing Mismatch & Generating Feedback..."
    echo ">> CMD: python3 \"$SCRIPT_FEEDBACK\" --hspice-performance \"$file_hspice_report\" --equation-performance \"$file_sized_params_spice\" --output-prompt \"$file_next_prompt\" --error-threshold 15.0 --netlist-path \"$NETLIST_FILE\" --past-equations \"$EQUATION_LIBRARY\""
    feedback_output=$(python3 "$SCRIPT_FEEDBACK" \
        --hspice-performance "$file_hspice_report" \
        --equation-performance "$file_sized_params_spice" \
        --output-prompt "$file_next_prompt" \
        --error-threshold 15.0 \
        --netlist-path "$NETLIST_FILE" \
        --past-equations "$EQUATION_LIBRARY")

    echo "$feedback_output"

    # Check for success
    echo ">> OPERATION: check convergence message via grep"
    if echo "$feedback_output" | grep -q "OUTPUT: All generated equations are accurate."; then
        echo ""
        echo "=========================================================="
        echo " SUCCESS! Convergence reached at Iteration $iter."
        echo " Final verified model: $file_model_py"
        echo " Final sized params:   $file_sized_params_spice"
        echo "=========================================================="

        # ==============================================================================
        # VECTORIZATION OF THE FINAL CONVERGED MODEL
        # ==============================================================================
        file_vectorized_model_py="$WORK_DIR/ota_models/ota_model_stage${iter}_vectorized.py"
        file_vectorization_agent_output="$WORK_DIR/llm_outputs/vectorization_agent_stage${iter}.json"

        echo ">> [17] Generating vectorized model..."
        echo ">> CMD: python3 \"$SCRIPT_VECTORIZATION_AGENT\" --scalar_evaluator \"$file_model_py\" --op_json \"$OP_JSON\" --call_codex \"$SCRIPT_LLM\" --model \"$MODEL\" --reasoning \"$REASONING\" --prompt_file \"$VECTORIZATION_PROMPT\" --agent_output_json \"$file_vectorization_agent_output\" --generated_script \"$file_vectorized_model_py\" --max_iters \"$MAX_MODEL_VECTORIZATION_EFFORT_ITERS\""

        python3 "$SCRIPT_VECTORIZATION_AGENT" \
            --scalar_evaluator "$file_model_py" \
            --op_json "$OP_JSON" \
            --call_codex "$SCRIPT_LLM" \
            --model "$MODEL" \
            --reasoning "$REASONING" \
            --prompt_file "$VECTORIZATION_PROMPT" \
            --agent_output_json "$file_vectorization_agent_output" \
            --generated_script "$file_vectorized_model_py" \
            --max_iters "$MAX_MODEL_VECTORIZATION_EFFORT_ITERS"

        vector_rc=$?

        if [ $vector_rc -ne 0 ]; then
            echo "!! Vectorization script failed with exit code $vector_rc."
            echo "!! Scalar model still exists: $file_model_py"
            echo ">> OPERATION: exit 1"
            exit 1
        fi

        if [ ! -f "$file_vectorized_model_py" ]; then
            echo "!! Vectorization script completed but did not create:"
            echo "   $file_vectorized_model_py"
            echo "!! Scalar model still exists: $file_model_py"
            echo ">> OPERATION: exit 1"
            exit 1
        fi

        echo ""
        echo "=========================================================="
        echo " FINAL SUCCESS!"
        echo " Final scalar model:     $file_model_py"
        echo " Final vectorized model: $file_vectorized_model_py"
        echo " Final sized params:     $file_sized_params_spice"
        echo " Vectorization JSON:     $file_vectorization_agent_output"
        echo "=========================================================="
        echo ">> OPERATION: exit 0"
        exit 0
    fi

    # ------------------------------------------------------------------
    # PREPARE FOR NEXT LOOP
    # ------------------------------------------------------------------
    echo ">> Mismatch detected. Looping..."

    echo ">> OPERATION: current_prompt=\"$file_next_prompt\""
    current_prompt="$file_next_prompt"

    echo ">> OPERATION: ((iter++))"
    ((iter++))

done


echo ""
echo "=========================================================="
echo " FAIL: Max iterations ($MAX_ITER) reached without convergence."
echo " No final vectorization was run because no converged model was found."
echo " Check the last debug logs."
echo "=========================================================="
echo ">> OPERATION: exit 1"
exit 1
