#!/bin/bash
set -e

# Target directory
EX_DIR=".agents/skills/ml-fairchem-finetune/examples/fairchem-wbm-finetune"
OUT_DIR="$EX_DIR"

mkdir -p "$OUT_DIR"

# 1. Prepare Data and Config
echo "Preparing FAIRCHEM Finetuning Data..."
conda run -n fairchem-agent python .agents/skills/ml-fairchem-finetune/scripts/prepare_fairchem_data.py \
    --data private_data/WBM_subset_200_configs.json \
    --vasp-stress-conversion \
    --output-dir "$OUT_DIR"

echo "Generating FAIRCHEM Config..."
conda run -n fairchem-agent python .agents/skills/ml-fairchem-finetune/scripts/generate_fairchem_config.py \
    --data-metadata "$OUT_DIR/dataset_metadata.json" \
    --model uma-s-1p1 \
    --task-name omat \
    --epochs 10 \
    --lr 1e-4 \
    --batch-size 2 \
    --freeze-backbone \
    --output-dir "$OUT_DIR"

# 2. Run FAIRCHEM Trainer
echo "Running FAIRCHEM Training (uma-s-1p1)..."
# FairChem needs to be in the folder where hydra config exists, and its module added to PYTHONPATH
export PYTHONPATH="$OUT_DIR/:$PYTHONPATH"
cd "$OUT_DIR/"

conda run --live-stream -n fairchem-agent fairchem -c uma_sm_finetune_template.yaml job.run_dir=runs/run_10ep +job.timestamp_id=run_10ep > train.log 2>&1
cd -

# 3. Extract Logs
echo "Extracting training metrics and generating plots..."
conda run -n fairchem-agent python .agents/skills/ml-fairchem-finetune/scripts/extract_fairchem_logs.py \
    --log "$OUT_DIR//train.log" \
    --output-dir "$OUT_DIR"

echo "FAIRCHEM Fine-tuning Example Completed Successfully."
