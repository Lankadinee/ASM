#!/bin/bash
set -e  # exit immediately if a command fails

dir=AR_models

mkdir -p $dir

gpu=1

for table in $(ls ./datasets/imdb/*csv); do
    y=${table%.*}
    z=${y##*/}
    echo $z
    log=$dir/train_imdb_${z}.log
    CUDA_VISIBLE_DEVICES=$gpu uv run AR/run.py --run imdb-single-${z}
    gpu=$(($gpu+1))
    gpu=$(($gpu%8))
done

wait
