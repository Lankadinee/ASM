"""Summarize ASM run on tpch_skewed: q-error, training time, inference time, model size."""
from __future__ import annotations
import csv
import os
import pickle
import re
from pathlib import Path

ASM = Path("/home/student.unimelb.edu.au/lrathuwadu/ASM")
CE_DIR = ASM / "tpch_skewed_CE"
QDIR = ASM / "tpch_skewed_queries"
META_MODEL = ASM / "meta_models/model_tpch_skewed.pkl"


def parse_time(p):
    out = {}
    if not Path(p).exists():
        return out
    for line in open(p):
        line = line.strip()
        if line.startswith("Elapsed"):
            out["elapsed"] = line.split(": ", 1)[1]
        if line.startswith("Maximum resident"):
            out["rss_kb"] = int(line.split(": ", 1)[1])
    return out


# load true cards
true_cards = {}
with open(QDIR / "true_cardinalities.csv") as f:
    r = csv.DictReader(f)
    for row in r:
        true_cards[row["qname"]] = int(row["true_card"])

with open(QDIR / "all_sub_plan_queries_str.pkl", "rb") as f:
    chains = pickle.load(f)

# load per-query estimates: each result.<qname> has one est per sub-plan
q_errors = []
missing = 0
zero_true = 0
results_dir = CE_DIR
files = sorted(results_dir.glob("result.q*"))
for fpath in files:
    qname = fpath.name.split(".", 1)[1]
    if qname not in chains or qname not in true_cards:
        missing += 1
        continue
    ests = [float(x) for x in open(fpath) if x.strip()]
    if not ests:
        missing += 1
        continue
    full_est = max(ests[-1], 1.0)
    true_c = true_cards[qname]
    if true_c == 0:
        zero_true += 1
        continue
    true_c = max(float(true_c), 1.0)
    q = max(full_est / true_c, true_c / full_est)
    q_errors.append((qname, true_c, full_est, q))

q_errors.sort(key=lambda x: x[3])
errs = [q[3] for q in q_errors]


def pct(p):
    return errs[int(round(p * (len(errs) - 1)))] if errs else float("nan")


print(f"q-error population: {len(errs)} (zero-true skipped: {zero_true}, missing: {missing})")
print()
print("Q-error percentiles (true_card > 0):")
for p in (0, 50, 90, 95, 99, 100):
    print(f"  p{p:>3}: {pct(p/100):.4f}")
if errs:
    print(f"  mean: {sum(errs)/len(errs):.4f}")

print()
print("Stage wall-clock + peak RSS:")
for stage in ("tpch_skewed_gen_model", "tpch_skewed_gen_ar", "tpch_skewed_evaluate"):
    p = ASM / f"logs/{stage}.time"
    d = parse_time(p)
    if d:
        print(f"  {stage:<28} elapsed={d.get('elapsed')}  peak_rss={d.get('rss_kb', 0)/1024:.0f} MB")

# inference time from evaluate log
eval_log = CE_DIR / "evaluate.log"
inf_total = inf_init = inf_sample = None
if eval_log.exists():
    txt = eval_log.read_text()
    m = re.search(r"total estimation latency is:\s+([0-9.]+)", txt)
    if m:
        inf_total = float(m.group(1))
    m = re.search(r"total initialize model latency is:\s+([0-9.]+)", txt)
    if m:
        inf_init = float(m.group(1))
    m = re.search(r"total initialize sample latency is:\s+([0-9.]+)", txt)
    if m:
        inf_sample = float(m.group(1))

if inf_total is not None:
    print()
    print("Inference time (from evaluate.log):")
    print(f"  total estimation latency  : {inf_total:.2f} s")
    print(f"  total init model latency  : {inf_init:.2f} s")
    print(f"  total init sample latency : {inf_sample:.2f} s")
    if errs:
        print(f"  per-query mean est latency: {1000*inf_total/len(errs):.2f} ms")

# model size: meta-model + AR checkpoints + per-table tuples_np.pkl + min_count.pkl
print()
print("Model size:")
total = 0
mm = META_MODEL.stat().st_size
total += mm
print(f"  meta_models/model_tpch_skewed.pkl  : {mm:>14,} B  ({mm/1024/1024:.2f} MB)")
ar_dir = ASM / "AR_models"
ar_total = 0
for tar in sorted(ar_dir.glob("tpch_skewed-single-*.tar")):
    s = tar.stat().st_size
    ar_total += s
    print(f"  {tar.name:<36} : {s:>14,} B  ({s/1024/1024:.2f} MB)")
total += ar_total
aux = 0
for table_dir in sorted((ASM / "datasets/tpch_skewed").iterdir()):
    if not table_dir.is_dir():
        continue
    for f in ("tuples_np.pkl", "min_count.pkl"):
        p = table_dir / f
        if p.exists():
            aux += p.stat().st_size
print(f"  AR checkpoints (8 tables) total    : {ar_total:>14,} B  ({ar_total/1024/1024:.2f} MB)")
print(f"  per-table tuples_np + min_count    : {aux:>14,} B  ({aux/1024/1024:.2f} MB)")
total += aux
print(f"  TOTAL                              : {total:>14,} B  ({total/1024/1024:.2f} MB)")
