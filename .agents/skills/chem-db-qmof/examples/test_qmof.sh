#!/usr/bin/env bash
cd $(dirname "$0")

echo "=========================================================="
echo "Testing chem-db-qmof: Searching for a Zinc-based MOF"
echo "=========================================================="

# Create an output directory for the example
mkdir -p ./out_zn

# Run the query script in the correct environment
export PYTHONPATH=$(dirname $(dirname $(dirname $(dirname "$PWD"))))
conda run -n base-agent python ../scripts/query_qmof.py \
    --formula "Zn" \
    --max-results 1 \
    --output-dir ./out_zn

echo "Query finished. Check the output directory: out_zn"
