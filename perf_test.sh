#!/bin/bash

docker cp results/estimations/imdb_colse.txt ce-benchmark:/var/lib/pgsql/13.1/data/imdb_colse.txt

uv run send_query.py --dataset imdb --method_name imdb_colse.txt --query_file ./imdb_queries/workloads.sql --save_folder ./job_result_plans_price_pretrained

# docker cp /home/ubuntu/data_CE/stats_CEB/