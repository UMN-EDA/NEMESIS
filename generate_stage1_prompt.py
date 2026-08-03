import argparse
import prompt_manager as pmt
import os

def main():
    # 1. Setup Argument Parser
    parser = argparse.ArgumentParser(
        description="Generate a Designer Prompt for Analog IC Modeling."
    )
    
    # Required positional argument: Netlist path
    parser.add_argument(
        "--netlist", 
        type=str, 
        help="Path to the SPICE netlist file (e.g., circuit.net)"
    )
    
    # Optional argument: Output file
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="llm_input_prompt.txt",
        help="Filename to save the generated prompt (default: llm_input_prompt.txt)"
    )

    # Optional argument: Role selection
    parser.add_argument(
        "--role", 
        type=str, 
        default="analog_architect",
        help="The persona to use for the prompt generation"
    )

    args = parser.parse_args()

    # 2. Check if netlist exists
    if not os.path.exists(args.netlist):
        print(f"Error: Netlist file '{args.netlist}' not found.")
        return

    try:
        # 3. Generate the STARTING prompt
        # We pass the file path directly as pmt.generate_prompt handles the 'open()'
        initial_prompt = pmt.generate_prompt(
            role=args.role,
            task_type="generate_model",
            netlist=args.netlist
        )

        # 4. Save to the specified output file
        with open(args.output, "w") as f:
            f.write(initial_prompt)
            
        print("-" * 50)
        print(f"SUCCESS!")
        print(f"Target Netlist: {args.netlist}")
        print(f"Role used     : {args.role}")
        print(f"Prompt saved to: {args.output}")
        print("-" * 50)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
