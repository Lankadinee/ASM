dir=meta_models

mkdir -p $dir

log=$dir/train_imdb.log

uv run run_experiment.py --dataset imdb --generate_models --data_path datasets/imdb/{}.csv --model_path $dir
