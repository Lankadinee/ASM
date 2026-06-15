"""Per-line ASM q-error report for IMDB.

Reads:
  - estimates from jobl_perline_CE/result.l<idx> (one float per sub-plan, last = full)
  - true cards from /home/student.unimelb.edu.au/lrathuwadu/cardinality-estimation-data/results/imdb_true_cardinality.txt
  - mapping from jobl_perline_queries/line_to_qname_spidx.pkl
"""
import os
import pickle
import time
import numpy as np

ASM = "/home/student.unimelb.edu.au/lrathuwadu/ASM"
RES_DIR = f"{ASM}/jobl_perline_CE"
MAP_PKL = f"{ASM}/jobl_perline_queries/line_to_qname_spidx.pkl"
TRUE_FILE = "/home/student.unimelb.edu.au/lrathuwadu/cardinality-estimation-data/results/imdb_true_cardinality.txt"
WORKLOAD = "/home/student.unimelb.edu.au/lrathuwadu/cardinality-estimation-data/processed_data/imdb/workloads.sql"


def qerror(est, true):
    est = max(float(est), 1.0)
    true = max(float(true), 1.0)
    return max(est / true, true / est)


def load_true_cards_by_tag():
    """Map @parent-sub@ tag -> true cardinality from the dedicated file."""
    out = {}
    with open(TRUE_FILE) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            tag = parts[0]
            true_c = float(parts[1])
            out[tag] = true_c
    return out


def load_workload_tag_order():
    """Return list of tags in workload line order, so we can map line idx -> tag."""
    tags = []
    with open(WORKLOAD) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("||")
            if len(parts) < 4:
                continue
            tag = parts[3].strip()
            tags.append(tag)
    return tags


def load_estimates():
    out = {}
    for f in os.listdir(RES_DIR):
        if not f.startswith("result.l") or f.endswith(".csv"):
            continue
        qname = f.split(".", 1)[1]  # 'l0', 'l1', ...
        ests = []
        with open(f"{RES_DIR}/{f}") as h:
            for ln in h:
                ln = ln.strip()
                if ln:
                    ests.append(float(ln))
        out[qname] = ests
    return out


def main():
    mapping = pickle.load(open(MAP_PKL, "rb"))  # line_idx -> (qname, spidx, recorded_true)
    tags = load_workload_tag_order()
    true_by_tag = load_true_cards_by_tag()
    ests = load_estimates()

    rows = []
    missing = 0
    for line_idx, (qname, spidx, recorded_true) in sorted(mapping.items()):
        q_ests = ests.get(qname)
        if q_ests is None or spidx >= len(q_ests):
            missing += 1
            continue
        tag = tags[line_idx]
        true_c = true_by_tag.get(tag, recorded_true)
        est = q_ests[spidx]
        rows.append((line_idx, tag, qname, true_c, est, qerror(est, true_c)))

    qs = np.array([r[5] for r in rows])
    print(f"per-line evaluated: {len(qs)} / {len(mapping)} (missing={missing})")
    print(f"true cards source: {TRUE_FILE}")
    print()
    print("Q-error percentiles:")
    for p in [50, 75, 90, 95, 99]:
        print(f"  {p:>3}%: {np.percentile(qs, p):.4f}")
    print(f"  max:  {qs.max():.4f}")
    print(f"  mean: {qs.mean():.4f}")

    # write per-row CSV for inspection
    out_csv = f"{RES_DIR}/perline_qerror.csv"
    with open(out_csv, "w") as f:
        f.write("line_idx,tag,qname,true,est,qerror\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")
    print(f"\nwrote per-row csv: {out_csv}")


if __name__ == "__main__":
    main()
