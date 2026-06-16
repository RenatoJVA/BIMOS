#!/usr/bin/env python3
import os
import sys
import yaml
import torch
import json
import argparse
from pathlib import Path

# Explicitly import OpenFold
import openfold.model.primitives as primitives

# Improved CPU-compatible attention_core
def attention_core_cpu(q, k, v, *biases, **kwargs):
    """
    A pure PyTorch implementation of attention_core that handles multiple biases.
    This replaces the CUDA-only kernel in OpenFold.
    """
    d_k = q.shape[-1]
    q = q / (d_k ** 0.5)
    
    # [..., H, Q, K]
    logits = torch.matmul(q, k.transpose(-2, -1))
    
    # In OpenFold/ESMFold, all masks and positional biases are passed in *biases
    # and they are already scaled or inverted (0 for keep, -1e9 for mask).
    for b in biases:
        if b is not None:
            logits = logits + b
            
    weights = torch.nn.functional.softmax(logits, dim=-1)
    
    # [..., H, Q, V]
    return torch.matmul(weights, v)

# Apply the patch to ensure CPU compatibility
primitives.attention_core = attention_core_cpu

def to_numpy(x):
    if isinstance(x, torch.Tensor):
        return x.cpu().numpy()
    elif isinstance(x, dict):
        return {k: to_numpy(v) for k, v in x.items()}
    elif isinstance(x, list):
        return [to_numpy(v) for v in x]
    else:
        return x

def parse_args():
    parser = argparse.ArgumentParser(description="ESMFold Prediction Script (CPU-Optimized)")
    parser.add_argument("yaml_file", type=str, help="Path to input YAML file")
    parser.add_argument("--out_dir", type=str, default=".", help="Output directory")
    parser.add_argument("--num_recycles", type=int, default=3, help="Number of recycles")
    parser.add_argument("--chain_linker", type=int, default=25, help="Chain linker length")
    return parser.parse_args()

def parse_yaml(yaml_path):
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    
    sequences = []
    for entry in data.get('sequences', []):
        if 'protein' in entry:
            sequences.append(entry['protein']['sequence'].strip())
    
    return ":".join(sequences)

def main():
    args = parse_args()
    
    # Configure CPU parallelism
    num_cpus = os.cpu_count()
    torch.set_num_threads(num_cpus)
    print(f"Using {num_cpus} CPU threads.")
    
    # Create output directory
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse sequence from YAML
    sequence = parse_yaml(args.yaml_file)
    clean_seq = sequence.replace(':', '')
    total_len = len(clean_seq)
    print(f"Input sequence length: {total_len}")
    
    # Load model on CPU
    model_path = "/models/esmfold.model"
    if not os.path.exists(model_path):
        print(f"Error: Model not found at {model_path}.")
        sys.exit(1)
        
    print(f"Loading model on CPU from {model_path}...")
    model = torch.load(model_path, map_location=torch.device('cpu'), weights_only=True)
    model.eval().requires_grad_(False)
    
    # Chunk size management
    if total_len > 700:
        model.set_chunk_size(64)
    else:
        model.set_chunk_size(128)
        
    # Run inference
    print(f"Running inference on CPU (recycles={args.num_recycles})...")
    with torch.no_grad():
        output = model.infer(sequence,
                             num_recycles=args.num_recycles,
                             chain_linker="X" * args.chain_linker,
                             residue_index_offset=512)
    
    # Prepare outputs
    pdb_str = model.output_to_pdb(output)[0]
    output_np = to_numpy(output)
    
    ptm = float(output_np.get("ptm", [0])[0])
    
    # pLDDT calculation
    plddt_tensor = output_np["plddt"]
    if len(plddt_tensor.shape) == 3:
        # Standard ESMFold pLDDT bin expectation or the notebook's specific bin
        plddt_val = float(plddt_tensor[0, :, 1].mean())
    else:
        plddt_val = float(plddt_tensor.mean())
    
    print(f"Prediction complete. PTM: {ptm:.3f}, pLDDT: {plddt_val:.3f}")
    
    # Save PDB
    base_name = Path(args.yaml_file).stem
    pdb_path = out_dir / f"{base_name}.pdb"
    with open(pdb_path, "w") as f:
        f.write(pdb_str)
        
    # Save confidence JSON
    conf_data = {
        "confidence_score": plddt_val / 100.0 if plddt_val > 1.0 else plddt_val,
        "ptm": ptm,
        "plddt": plddt_val,
        "model_name": "ESMFold_CPU_Corrected"
    }
    
    conf_path = out_dir / f"confidence_{base_name}.json"
    with open(conf_path, "w") as f:
        json.dump(conf_data, f, indent=4)
        
    print(f"Results saved to {out_dir}")

if __name__ == "__main__":
    main()
