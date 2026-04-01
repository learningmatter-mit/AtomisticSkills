#!/bin/bash
set -e

# Test script for ml-fairchem-finetune SKILL

echo "Creating research directory..."
RESEARCH_DIR="./research/fairchem_finetuning_test_$(date +%Y%m%d%H%M%S)"
mkdir -p "$RESEARCH_DIR"

echo "Running data preparation..."
conda run --live-stream -n fairchem-agent python .agents/skills/ml-fairchem-finetune/scripts/prepare_fairchem_data.py \
    --data private_data/WBM_high_energy_states.json \
    --model uma-s-1p1 \
    --epochs 2 \
    --lr 4e-4 \
    --batch-size 1 \
    --freeze-backbone \
    --output-dir "$RESEARCH_DIR/finetuning"

echo "Running Fairchem training via subprocess... (Ensure GPU memory available)"
export PYTHONPATH="$RESEARCH_DIR/finetuning/lmdb_output:$PYTHONPATH"
cd "$RESEARCH_DIR/finetuning/lmdb_output"
conda run --live-stream -n fairchem-agent fairchem -c uma_sm_finetune_template.yaml job.run_dir="../../runs" +job.timestamp_id=run_test

cd ../../../..

echo "Extracting training logs..."
conda run --live-stream -n fairchem-agent python .agents/skills/ml-fairchem-finetune/scripts/extract_fairchem_logs.py \
    --log "$RESEARCH_DIR/runs/run_test/logs/trainer.log" --output-dir "$RESEARCH_DIR/results" --task-name omat

echo "Test complete! Check $RESEARCH_DIR for outputs."
