#!/bin/bash
# Example script to demonstrate mat-htvs-cutcleansurface usage
# Usage: bash run_example.sh
# Ensure your htvs-agent environment is active first

echo "Creating a dummy bulk_ids.pkl..."
python -c "import pickle; pickle.dump([1], open('bulk_ids.pkl', 'wb'))"

echo "Running mat-htvs-cutcleansurface with --dry_run..."
python ../scripts/run.py \
    --group example_project \
    --bulk_pkl bulk_ids.pkl \
    --MI 1 1 1 \
    --settings djangochem.settings.orgel \
    --dry_run \
    --layers 4 \
    --vacuum 10.0 \
    --scale 2 2 \
    --rotation 0.0

echo "Cleaning up..."
rm bulk_ids.pkl
