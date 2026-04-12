"""Parse ASM JOB-light results, compute metrics against PRICE true cards."""
import os
import pickle
import numpy as np

ASM_DIR = "/home/student.unimelb.edu.au/lrathuwadu/ASM"
RES_DIR = f"{ASM_DIR}/jobl_CE"
MAP_PKL = f"{ASM_DIR}/jobl_queries/line_to_qname_spidx.pkl"


def load_all_estimates():
    """Return dict {qname: [est_0, est_1, ...]}."""
    out = {}
    for f in os.listdir(RES_DIR):
        if not f.startswith("result.q") or f.endswith(".csv"):
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
    mapping = pickle.load(open(MAP_PKL, "rb"))  # {line_idx: (qname, spidx, true_card)}
    ests = load_all_estimates()

    rows = []  # (line_idx, qname, spidx, true, est, qerr)
    for idx, (qname, spidx, true) in sorted(mapping.items()):
        q_ests = ests.get(qname)
        if q_ests is None:
            print(f"MISSING {qname}")
            continue
        if spidx >= len(q_ests):
            print(f"OOB {qname} spidx={spidx} len={len(q_ests)}")
            continue
        est = q_ests[spidx]
        qerr = qerror(est, true)
        rows.append((idx, qname, spidx, true, est, qerr))

    qs = np.array([r[5] for r in rows])
    print(f"sub-queries evaluated: {len(qs)} / 766")
    print(f"q-error percentiles:")
    for p in [30, 50, 80, 90, 95, 99]:
        print(f"  {p}%: {np.percentile(qs, p):.4f}")
    print(f"  max: {qs.max():.4f}")
    print(f"  mean: {qs.mean():.4f}")

    # also compute separately for parent queries (the 70 full-join queries)
    parent_rows = []
    seen_pids = set()
    for idx, qname, spidx, true, est, qerr in rows:
        pid = int(qname[1:])
        if pid in seen_pids:
            continue
        # the parent = last sub-plan in each group
        if spidx == len(ests[qname]) - 1:
            parent_rows.append(qerr)
            seen_pids.add(pid)
    print(f"\nparent-only q-error percentiles ({len(parent_rows)} parents):")
    pa = np.array(parent_rows)
    for p in [30, 50, 80, 90, 95, 99]:
        print(f"  {p}%: {np.percentile(pa, p):.4f}")
    print(f"  max: {pa.max():.4f}")
    print(f"  mean: {pa.mean():.4f}")


if __name__ == "__main__":
    main()
