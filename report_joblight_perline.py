"""Parse per-line ASM results for the 766 standalone-query setup."""
import os
import pickle
import numpy as np

ASM_DIR = "/home/student.unimelb.edu.au/lrathuwadu/ASM"
RES_DIR = f"{ASM_DIR}/jobl_perline_CE"
MAP_PKL = f"{ASM_DIR}/jobl_perline_queries/line_to_qname_spidx.pkl"


def load_all():
    out = {}
    for f in os.listdir(RES_DIR):
        if not f.startswith("result.l") or f.endswith(".csv"):
            continue
        qname = f.split(".", 1)[1]
        ests = []
        with open(f"{RES_DIR}/{f}") as h:
            for ln in h:
                ln = ln.strip()
                if ln:
                    ests.append(float(ln))
        out[qname] = ests
    return out


def qerror(est, true):
    est = max(est, 1.0)
    true = max(true, 1.0)
    return max(est / true, true / est)


def main():
    mapping = pickle.load(open(MAP_PKL, "rb"))
    ests = load_all()
    rows = []
    for idx, (qname, spidx, true) in sorted(mapping.items()):
        q_ests = ests.get(qname)
        if q_ests is None:
            continue
        if spidx >= len(q_ests):
            continue
        est = q_ests[spidx]
        rows.append((idx, qname, spidx, true, est, qerror(est, true)))
    qs = np.array([r[5] for r in rows])
    print(f"per-line evaluated: {len(qs)} / 766")
    for p in [30, 50, 80, 90, 95, 99]:
        print(f"  {p}%: {np.percentile(qs, p):.4f}")
    print(f"  max: {qs.max():.4f}")
    print(f"  mean: {qs.mean():.4f}")


if __name__ == "__main__":
    main()
