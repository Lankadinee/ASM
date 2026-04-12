"""Each PRICE sub-query becomes its own standalone ASM query.

Unlike convert_price_joblight.py which groups by parent (letting ASM cache
conditional_factors across sub-plans), this version emits one ASM `query`
per PRICE line. Each line gets its own qname, its own SQL, its own
predicate pkl, and its own sub_plan_list covering sizes 2..M with only
the final (size-M) estimate representing the target. ASM thus runs fresh
AR forwards for every line's aliases with no cross-line reuse.
"""
import os
import pickle
import re
from itertools import combinations
from convert_price_joblight import (
    PRICE_WORKLOAD,
    parse_line,
    build_predicate_dict,
)

OUT_DIR = "/home/student.unimelb.edu.au/lrathuwadu/ASM/jobl_perline_queries"
PRED_DIR = f"{OUT_DIR}/predicate"
os.makedirs(PRED_DIR, exist_ok=True)


def gen_sub_plan_chain(aliases):
    """For a query with aliases = (a1,...,aM), produce a left-deep sub-plan
    chain of ASM (left, right_str) tuples covering sizes 2..M."""
    als = sorted(aliases)
    M = len(als)
    if M < 2:
        return []
    chain = []
    cached = set()
    for k in range(2, M + 1):
        for combo in combinations(als, k):
            combo_sorted = list(combo)
            if k == 2:
                left, right = combo_sorted[-1], combo_sorted[0]
                chain.append((left, right))
                cached.add(" ".join(combo_sorted))
                continue
            # choose left so that right = sorted(combo - {left}) is in cache
            chosen = None
            for i in range(k - 1, -1, -1):
                cand_left = combo_sorted[i]
                cand_right_list = [a for j, a in enumerate(combo_sorted) if j != i]
                cand_right = " ".join(cand_right_list)
                if cand_right in cached:
                    chosen = (cand_left, cand_right)
                    break
            assert chosen is not None, f"no cached right for {combo_sorted}"
            chain.append(chosen)
            cached.add(" ".join(combo_sorted))
    return chain


def main():
    with open(PRICE_WORKLOAD) as f:
        lines = [ln for ln in f if ln.strip()]

    all_queries = {}
    all_sub_plan_queries_str = {}
    # line_idx -> (qname, target_sp_idx, true_card)
    line_to_qname_spidx = {}

    for i, ln in enumerate(lines):
        p = parse_line(ln)
        if p is None:
            continue
        aliases = p["aliases"]
        if len(aliases) < 2:
            continue
        qname = f"l{i}"
        chain = gen_sub_plan_chain(aliases)
        all_queries[qname] = p["sql"]
        all_sub_plan_queries_str[qname] = chain
        # target = final entry in chain (the size-M full join)
        target_idx = len(chain) - 1
        line_to_qname_spidx[i] = (qname, target_idx, p["true_card"])

        pred, _ = build_predicate_dict(p["sql"])
        with open(f"{PRED_DIR}/{qname}.pkl", "wb") as f:
            pickle.dump(pred, f, pickle.HIGHEST_PROTOCOL)

    with open(f"{OUT_DIR}/all_queries.pkl", "wb") as f:
        pickle.dump(all_queries, f, pickle.HIGHEST_PROTOCOL)
    with open(f"{OUT_DIR}/all_sub_plan_queries_str.pkl", "wb") as f:
        pickle.dump(all_sub_plan_queries_str, f, pickle.HIGHEST_PROTOCOL)
    with open(f"{OUT_DIR}/line_to_qname_spidx.pkl", "wb") as f:
        pickle.dump(line_to_qname_spidx, f, pickle.HIGHEST_PROTOCOL)

    n_forwards = sum(
        len(set(tuple(sorted([l] + r.split()))
                for (l, r) in chain)) + len(all_queries[qn].split(','))
        for qn, chain in all_sub_plan_queries_str.items()
    )
    total_sub = sum(len(v) for v in all_sub_plan_queries_str.values())
    print(f"wrote {len(all_queries)} standalone queries")
    print(f"total sub-plans across all queries: {total_sub}")
    print(f"mapped {len(line_to_qname_spidx)} PRICE lines")
    # sanity
    sample_q = "l0"
    print(f"sample {sample_q}: sql={all_queries[sample_q][:80]}...")
    print(f"sample {sample_q}: chain={all_sub_plan_queries_str[sample_q]}")


if __name__ == "__main__":
    main()
