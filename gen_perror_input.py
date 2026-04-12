"""Generate PRICE-format perror_input files from ASM estimates.

Reads workloads_all.sql (which includes single-table sub-queries) and maps
ASM's multi-table estimates. Single-table queries get -1 (use true card).

Output format per line: SQL || TRUE_CARD || MODEL_EST_CARD || @pid-sid@
"""
import os
import pickle
import re

ASM_DIR = "/home/student.unimelb.edu.au/lrathuwadu/ASM"
PRICE_DIR = "/home/student.unimelb.edu.au/lrathuwadu/PRICE"

TAG_RE = re.compile(r"@(\d+)-(\d+)@")
SUBPLAN_COMMENT_RE = re.compile(r"/\*\s*\((.*?)\)\s*\*/")


def gen(dataset):
    workloads_all = f"{PRICE_DIR}/datas/workloads/test/{dataset}/workloads_all.sql"
    if dataset == "imdb":
        map_pkl = f"{ASM_DIR}/jobl_queries/line_to_qname_spidx.pkl"
        res_dir = f"{ASM_DIR}/jobl_CE"
        workloads_test = f"{PRICE_DIR}/datas/workloads/test/{dataset}/workloads.sql"
    else:
        map_pkl = f"{ASM_DIR}/stats_jobl_queries/line_to_qname_spidx.pkl"
        res_dir = f"{ASM_DIR}/stats_jobl_CE"
        workloads_test = f"{PRICE_DIR}/datas/workloads/test/{dataset}/workloads.sql"

    # Load ASM line mapping (test workload line idx -> (qname, sp_idx, true))
    mapping = pickle.load(open(map_pkl, "rb"))

    # Load ASM estimates per qname
    ests = {}
    for f in os.listdir(res_dir):
        if not f.startswith("result.q") or f.endswith(".csv"):
            continue
        qname = f.split(".", 1)[1]
        vals = [float(ln.strip()) for ln in open(f"{res_dir}/{f}") if ln.strip()]
        ests[qname] = vals

    # Build index: for each (pid, alias_set) -> ASM estimate
    # First, parse test workload to know which line idx corresponds to which @pid-sid@
    test_lines = [ln.strip() for ln in open(workloads_test) if ln.strip()]
    # tag -> test line index
    tag_to_test_idx = {}
    for i, ln in enumerate(test_lines):
        m = TAG_RE.search(ln.split("||")[-1] if "||" in ln else "")
        if m:
            tag_to_test_idx[(int(m.group(1)), int(m.group(2)))] = i

    # test line index -> ASM estimate
    test_idx_to_est = {}
    for idx, (qname, sp_idx, true_card) in mapping.items():
        q_ests = ests.get(qname)
        if q_ests and sp_idx < len(q_ests):
            test_idx_to_est[idx] = q_ests[sp_idx]

    # Now process workloads_all.sql (format: SQL||TRUE_CARD||@pid-sid@)
    all_lines = [ln.strip() for ln in open(workloads_all) if ln.strip()]
    out_lines = []
    for ln in all_lines:
        parts = ln.split("||")
        if len(parts) < 3:
            out_lines.append(ln)
            continue
        sql, true_card, tag_str = parts[0], parts[1], parts[-1]
        m = TAG_RE.search(tag_str)
        if not m:
            out_lines.append(ln)
            continue
        pid, sid = int(m.group(1)), int(m.group(2))

        # Look up in test workload
        test_idx = tag_to_test_idx.get((pid, sid))
        if test_idx is not None and test_idx in test_idx_to_est:
            model_est = test_idx_to_est[test_idx]
        else:
            model_est = -1  # single-table or missing -> use true card

        out_lines.append(f"{sql}||{true_card}||{model_est}||{tag_str}")

    out_path = f"{ASM_DIR}/results/{dataset}_perror_input.sql"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        for ln in out_lines:
            f.write(ln + "\n")
    print(f"{dataset}: wrote {len(out_lines)} lines to {out_path}")
    n_est = sum(1 for ln in out_lines if ln.count("||") >= 3 and ln.split("||")[2] != "-1")
    n_neg = sum(1 for ln in out_lines if ln.count("||") >= 3 and ln.split("||")[2] == "-1")
    print(f"  {n_est} lines with ASM estimates, {n_neg} with -1 (true card)")


if __name__ == "__main__":
    gen("imdb")
    gen("stats")
