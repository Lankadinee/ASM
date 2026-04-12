"""Parse STATS results for both batched and per-line ASM runs."""
import os
import pickle
import numpy as np


def load_ests(res_dir, prefix="result."):
    out = {}
    for f in os.listdir(res_dir):
        if not f.startswith(prefix) or f.endswith(".csv"):
            continue
        qname = f.split(".", 1)[1]
        ests = [float(ln.strip()) for ln in open(f"{res_dir}/{f}") if ln.strip()]
        out[qname] = ests
    return out


def qerror(est, true):
    est, true = max(est, 1.0), max(true, 1.0)
    return max(est / true, true / est)


def report(name, map_pkl, res_dir):
    mapping = pickle.load(open(map_pkl, "rb"))
    ests = load_ests(res_dir)
    rows = []
    for idx, (qname, spidx, true) in sorted(mapping.items()):
        q_ests = ests.get(qname)
        if q_ests is None:
            continue
        if spidx >= len(q_ests):
            continue
        rows.append(qerror(q_ests[spidx], true))
    qs = np.array(rows)
    print(f"\n{name}: {len(qs)} / 2749 sub-queries")
    for p in [30, 50, 80, 90, 95, 99]:
        print(f"  {p}%: {np.percentile(qs, p):.4f}")
    print(f"  max: {qs.max():.4f}")
    print(f"  mean: {qs.mean():.4f}")


if __name__ == "__main__":
    BASE = "/home/student.unimelb.edu.au/lrathuwadu/ASM"
    report("BATCHED",
           f"{BASE}/stats_jobl_queries/line_to_qname_spidx.pkl",
           f"{BASE}/stats_jobl_CE")
    report("PER-LINE",
           f"{BASE}/stats_perline_queries/line_to_qname_spidx.pkl",
           f"{BASE}/stats_perline_CE")
